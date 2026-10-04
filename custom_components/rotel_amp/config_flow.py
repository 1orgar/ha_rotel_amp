"""Config flow for the Rotel Amplifier integration.

Setup:   user (address) -> sources (inputs + general) -> one "input" step per
         selected input -> announce -> entry created.
Options: menu -> general | inputs (list -> one input) | announce | save.
Per-input step: name + linked player first; the player-related options
(follow, fixed volume) are only shown on a second pass when a player is set.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er, selector
import voluptuous as vol

from .client import NoResponseError, async_test_connection
from .const import (
    CONF_ANNOUNCE_SOURCE,
    CONF_ANNOUNCE_VOLUME,
    CONF_AUTO_OFF,
    CONF_MAX_VOLUME,
    CONF_POLL_INTERVAL,
    CONF_SOURCE_FIXED_VOLUME,
    CONF_SOURCE_FOLLOW,
    CONF_SOURCE_KEEP_ON,
    CONF_SOURCE_NAMES,
    CONF_SOURCE_PLAYERS,
    CONF_SOURCE_REF_VOLUME,
    CONF_SOURCES,
    DEFAULT_AUTO_OFF,
    DEFAULT_MAX_VOLUME,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
    SOURCES,
)

_LOGGER = logging.getLogger(__name__)

NO_ANNOUNCE = "none"
# field names inside the per-input step
F_NAME = "name"
F_PLAYER = "player"
F_FOLLOW = "follow"
F_FIXVOL = "fixed_volume"
F_REFVOL = "ref_volume"
F_KEEPON = "keep_on"
SEC_PLAYER = "player_options"
SEC_POWER = "power_volume"
SEC_VOLUME = "volume"
SEC_ADVANCED = "advanced"


def _box(lo: int, hi: int, unit: str | None = None) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=lo, max=hi, step=1, mode=selector.NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _input_label(key: str, opts: dict[str, Any]) -> str:
    """'Стример (Coax 2)' or just 'Coax 2'."""
    default = SOURCES[key][2]
    name = opts.get(CONF_SOURCE_NAMES, {}).get(key)
    return f"{name} ({default})" if name and name != default else default


# ---- general settings -------------------------------------------------------
def _general_schema(opts: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_SOURCES, default=opts.get(CONF_SOURCES, list(SOURCES))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=key, label=default)
                        for key, (_, _, default) in SOURCES.items()
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(SEC_VOLUME): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_MAX_VOLUME,
                            default=int(opts.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)),
                        ): _box(1, 96),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required(SEC_POWER): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_AUTO_OFF,
                            default=int(opts.get(CONF_AUTO_OFF, DEFAULT_AUTO_OFF)),
                        ): _box(0, 720, "min"),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required(SEC_ADVANCED): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_POLL_INTERVAL,
                            default=int(
                                opts.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
                            ),
                        ): _box(0, 3600, "s"),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _apply_general(opts: dict[str, Any], user_input: dict[str, Any]) -> dict[str, str]:
    """Copy general settings into opts; return errors."""
    if not user_input.get(CONF_SOURCES):
        return {CONF_SOURCES: "no_sources"}
    sources = [k for k in SOURCES if k in user_input[CONF_SOURCES]]
    opts[CONF_SOURCES] = sources
    opts[CONF_MAX_VOLUME] = int(user_input[SEC_VOLUME][CONF_MAX_VOLUME])
    opts[CONF_AUTO_OFF] = int(user_input[SEC_POWER][CONF_AUTO_OFF])
    opts[CONF_POLL_INTERVAL] = int(user_input[SEC_ADVANCED][CONF_POLL_INTERVAL])
    _drop_removed_inputs(opts)
    return {}


def _drop_removed_inputs(opts: dict[str, Any]) -> None:
    """Forget per-input settings of inputs that were deselected."""
    keep = set(opts.get(CONF_SOURCES, []))
    for conf in (CONF_SOURCE_NAMES, CONF_SOURCE_PLAYERS, CONF_SOURCE_REF_VOLUME):
        opts[conf] = {k: v for k, v in opts.get(conf, {}).items() if k in keep}
    for conf in (CONF_SOURCE_FOLLOW, CONF_SOURCE_FIXED_VOLUME, CONF_SOURCE_KEEP_ON):
        opts[conf] = [k for k in opts.get(conf, []) if k in keep]
    if opts.get(CONF_ANNOUNCE_SOURCE) not in opts.get(CONF_SOURCE_PLAYERS, {}):
        opts[CONF_ANNOUNCE_SOURCE] = None


# ---- one input -------------------------------------------------------------
def _input_schema(key: str, opts: dict[str, Any], player: str | None) -> vol.Schema:
    """Name + linked player; player options only when a player is chosen."""
    names = opts.get(CONF_SOURCE_NAMES, {})
    fields: dict[Any, Any] = {
        vol.Required(F_NAME, default=names.get(key, SOURCES[key][2])): (
            selector.TextSelector()
        ),
        # suggested_value (not default) so the player can be cleared
        vol.Optional(
            F_PLAYER,
            description={"suggested_value": player} if player else None,
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player")),
    }
    if player:
        # Optional: when the player is cleared the form is submitted without it
        fields[vol.Optional(SEC_PLAYER)] = section(
            vol.Schema(
                {
                    vol.Optional(
                        F_FOLLOW, default=key in opts.get(CONF_SOURCE_FOLLOW, [])
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        F_FIXVOL, default=key in opts.get(CONF_SOURCE_FIXED_VOLUME, [])
                    ): selector.BooleanSelector(),
                }
            ),
            {"collapsed": False},
        )
    fields[vol.Optional(SEC_POWER)] = section(
        vol.Schema(
            {
                vol.Optional(
                    F_REFVOL,
                    default=int(opts.get(CONF_SOURCE_REF_VOLUME, {}).get(key, 0)),
                ): _box(0, 96),
                vol.Optional(
                    F_KEEPON, default=key in opts.get(CONF_SOURCE_KEEP_ON, [])
                ): selector.BooleanSelector(),
            }
        ),
        {"collapsed": True},
    )
    return vol.Schema(fields)


def _set_flag(opts: dict[str, Any], conf: str, key: str, value: bool) -> None:
    items = [k for k in opts.get(conf, []) if k != key]
    if value:
        items.append(key)
    opts[conf] = [k for k in SOURCES if k in items]


def _apply_input(
    opts: dict[str, Any], key: str, user_input: dict[str, Any], own: set[str]
) -> dict[str, str]:
    """Validate and store one input; return errors."""
    name = (user_input.get(F_NAME) or "").strip() or SOURCES[key][2]
    others = {
        v.casefold()
        for k, v in opts.get(CONF_SOURCE_NAMES, {}).items()
        if k != key and k in opts.get(CONF_SOURCES, [])
    }
    if name.casefold() in others:
        return {F_NAME: "duplicate_name"}
    player = user_input.get(F_PLAYER) or None
    if player and player in own:
        return {F_PLAYER: "self_player"}

    opts.setdefault(CONF_SOURCE_NAMES, {})[key] = name
    players = dict(opts.get(CONF_SOURCE_PLAYERS, {}))
    if player:
        players[key] = player
    else:
        players.pop(key, None)
    opts[CONF_SOURCE_PLAYERS] = players

    pl = user_input.get(SEC_PLAYER, {})
    _set_flag(opts, CONF_SOURCE_FOLLOW, key, bool(player and pl.get(F_FOLLOW)))
    _set_flag(opts, CONF_SOURCE_FIXED_VOLUME, key, bool(player and pl.get(F_FIXVOL)))
    power = user_input.get(SEC_POWER, {})
    refvol = dict(opts.get(CONF_SOURCE_REF_VOLUME, {}))
    if int(power.get(F_REFVOL) or 0) > 0:
        refvol[key] = int(power[F_REFVOL])
    else:
        refvol.pop(key, None)
    opts[CONF_SOURCE_REF_VOLUME] = refvol
    _set_flag(opts, CONF_SOURCE_KEEP_ON, key, bool(power.get(F_KEEPON)))
    if not player and opts.get(CONF_ANNOUNCE_SOURCE) == key:
        opts[CONF_ANNOUNCE_SOURCE] = None
    return {}


def _own_entities(hass: HomeAssistant, entry_id: str | None) -> set[str]:
    if entry_id is None:
        return set()
    return {
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry_id)
    }



# ---- announcements ----------------------------------------------------------
def _announce_schema(opts: dict[str, Any]) -> vol.Schema:
    players = opts.get(CONF_SOURCE_PLAYERS, {})
    choices = [selector.SelectOptionDict(value=NO_ANNOUNCE, label="—")] + [
        selector.SelectOptionDict(
            value=k, label=f"{_input_label(k, opts)} → {players[k]}"
        )
        for k in opts.get(CONF_SOURCES, [])
        if k in players
    ]
    return vol.Schema(
        {
            vol.Optional(
                CONF_ANNOUNCE_SOURCE,
                default=opts.get(CONF_ANNOUNCE_SOURCE) or NO_ANNOUNCE,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=choices, mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(
                CONF_ANNOUNCE_VOLUME, default=int(opts.get(CONF_ANNOUNCE_VOLUME, 0))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=1, unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _apply_announce(opts: dict[str, Any], user_input: dict[str, Any]) -> None:
    source = user_input.get(CONF_ANNOUNCE_SOURCE) or NO_ANNOUNCE
    valid = source in opts.get(CONF_SOURCE_PLAYERS, {})
    opts[CONF_ANNOUNCE_SOURCE] = source if valid else None
    opts[CONF_ANNOUNCE_VOLUME] = int(user_input.get(CONF_ANNOUNCE_VOLUME) or 0)


def _defaults() -> dict[str, Any]:
    return {
        CONF_SOURCES: list(SOURCES),
        CONF_SOURCE_NAMES: {},
        CONF_SOURCE_PLAYERS: {},
        CONF_SOURCE_FOLLOW: [],
        CONF_SOURCE_FIXED_VOLUME: [],
        CONF_SOURCE_REF_VOLUME: {},
        CONF_SOURCE_KEEP_ON: [],
        CONF_ANNOUNCE_SOURCE: None,
        CONF_ANNOUNCE_VOLUME: 0,
        CONF_MAX_VOLUME: DEFAULT_MAX_VOLUME,
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_AUTO_OFF: DEFAULT_AUTO_OFF,
    }


class _InputStepMixin:
    """Per-input step shared by the config and options flows.

    When a player is picked for the first time the same step is shown once
    more, now with the player options (follow / fixed volume) visible.
    """

    hass: HomeAssistant
    _opts: dict[str, Any]
    _key: str = ""
    _pending_player: str | None = None
    _entry_id: str | None = None

    def _show_input(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        key = self._key
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="input",
            data_schema=_input_schema(key, self._opts, self._pending_player),
            errors=errors or {},
            description_placeholders={
                "input": SOURCES[key][2],
                "label": _input_label(key, self._opts),
            },
            last_step=False,
        )

    def _start_input(self, key: str) -> ConfigFlowResult:
        self._key = key
        self._pending_player = self._opts.get(CONF_SOURCE_PLAYERS, {}).get(key)
        return self._show_input()

    def _handle_input(self, user_input: dict[str, Any]) -> ConfigFlowResult | None:
        """Return a form to show again, or None once the input is saved."""
        player = user_input.get(F_PLAYER) or None
        if player and player != self._pending_player:
            # a player was just selected: reveal its options before saving
            self._pending_player = player
            name = (user_input.get(F_NAME) or "").strip()
            if name:
                self._opts.setdefault(CONF_SOURCE_NAMES, {})[self._key] = name
            return self._show_input()
        errors = _apply_input(
            self._opts, self._key, user_input, _own_entities(self.hass, self._entry_id)
        )
        if errors:
            self._pending_player = player
            return self._show_input(errors)
        return None



async def _async_check(host: str, port: int) -> dict[str, str]:
    """Test the address; return form errors."""
    try:
        await async_test_connection(host, port)
    except (OSError, TimeoutError):
        return {"base": "cannot_connect"}
    except NoResponseError:
        return {"base": "no_response"}
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error")
        return {"base": "unknown"}
    return {}


def _address_schema(host: str | None, port: int, name: str | None) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(CONF_HOST, default=host or vol.UNDEFINED): str,
        vol.Required(CONF_PORT, default=port): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
    if name is not None:
        fields[vol.Required(CONF_NAME, default=name)] = str
    return vol.Schema(fields)


def _input_menu_label(key: str, opts: dict[str, Any]) -> str:
    """'Стример (Coax 2) — media_player.x · auto · 100 %'."""
    extras: list[str] = []
    if player := opts.get(CONF_SOURCE_PLAYERS, {}).get(key):
        extras.append(player)
    if key in opts.get(CONF_SOURCE_FOLLOW, []):
        extras.append("auto")
    if key in opts.get(CONF_SOURCE_FIXED_VOLUME, []):
        extras.append("100 %")
    if ref := opts.get(CONF_SOURCE_REF_VOLUME, {}).get(key):
        extras.append(f"≈{ref}")
    if key in opts.get(CONF_SOURCE_KEEP_ON, []):
        extras.append("⏻")
    label = _input_label(key, opts)
    return f"{label} — {' · '.join(extras)}" if extras else label


def _summary(opts: dict[str, Any]) -> str:
    """Markdown list of the configured inputs for the menu description."""
    return "\n".join(f"- {_input_menu_label(k, opts)}" for k in opts.get(CONF_SOURCES, []))



class RotelConfigFlow(_InputStepMixin, ConfigFlow, domain=DOMAIN):
    """Initial setup: address -> general -> each input -> announcements."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._opts = _defaults()
        self._queue: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Host / port / name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            # an entry moved here by reconfigure keeps its old unique_id
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
            errors = await _async_check(host, port)
            if not errors:
                self._data = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_NAME: user_input[CONF_NAME],
                }
                return await self.async_step_sources()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _address_schema(None, DEFAULT_PORT, DEFAULT_NAME), user_input
            ),
            errors=errors,
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Inputs in use + volume / power / polling."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _apply_general(self._opts, user_input)
            if not errors:
                self._queue = list(self._opts[CONF_SOURCES])
                return self._start_input(self._queue.pop(0))
        return self.async_show_form(
            step_id="sources", data_schema=_general_schema(self._opts), errors=errors
        )

    async def async_step_input(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One input (repeated for every selected input)."""
        if user_input is None:
            return self._show_input()
        if (form := self._handle_input(user_input)) is not None:
            return form
        if self._queue:
            return self._start_input(self._queue.pop(0))
        if self._opts.get(CONF_SOURCE_PLAYERS):
            return await self.async_step_announce()
        return self._finish()

    async def async_step_announce(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Announcement input and volume."""
        if user_input is not None:
            _apply_announce(self._opts, user_input)
            return self._finish()
        return self.async_show_form(
            step_id="announce", data_schema=_announce_schema(self._opts)
        )

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._data[CONF_NAME], data=self._data, options=self._opts
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host / port; inputs, links and entity IDs are kept."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            errors = await _async_check(host, port)
            if not errors:
                for other in self._async_current_entries(include_ignore=False):
                    if (
                        other.entry_id != entry.entry_id
                        and other.data.get(CONF_HOST) == host
                        and other.data.get(CONF_PORT) == port
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host, CONF_PORT: port}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _address_schema(entry.data[CONF_HOST], entry.data[CONF_PORT], None),
                user_input,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RotelOptionsFlow:
        """Return the options flow."""
        return RotelOptionsFlow()



class RotelOptionsFlow(_InputStepMixin, OptionsFlow):
    """Menu: general settings, one input at a time, announcements, save."""

    def __init__(self) -> None:
        self._opts: dict[str, Any] = {}
        self._dirty = False

    @property
    def _entry_id(self) -> str:  # type: ignore[override]
        return self.config_entry.entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main menu."""
        if not self._opts:
            self._opts = {**_defaults(), **dict(self.config_entry.options)}
        menu = ["general", "inputs"]
        if self._opts.get(CONF_SOURCE_PLAYERS):
            menu.append("announce")
        menu.append("save")
        return self.async_show_menu(
            step_id="init",
            menu_options=menu,
            description_placeholders={
                "summary": _summary(self._opts),
                "unsaved": "\n\n⚠️ " if self._dirty else "",
            },
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Inputs in use, volume, auto off, polling."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _apply_general(self._opts, user_input)
            if not errors:
                self._dirty = True
                return await self.async_step_init()
        return self.async_show_form(
            step_id="general", data_schema=_general_schema(self._opts), errors=errors
        )

    async def async_step_inputs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick an input to edit."""
        sources = self._opts.get(CONF_SOURCES, [])
        if user_input is not None:
            return self._start_input(user_input[CONF_SOURCES])
        return self.async_show_form(
            step_id="inputs",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCES, default=sources[0]): (
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(
                                        value=k, label=_input_menu_label(k, self._opts)
                                    )
                                    for k in sources
                                ],
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        )
                    )
                }
            ),
            last_step=False,
        )

    async def async_step_input(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit one input, then back to the menu."""
        if user_input is None:
            return self._show_input()
        if (form := self._handle_input(user_input)) is not None:
            return form
        self._dirty = True
        return await self.async_step_init()

    async def async_step_announce(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Announcement input and volume."""
        if user_input is not None:
            _apply_announce(self._opts, user_input)
            self._dirty = True
            return await self.async_step_init()
        return self.async_show_form(
            step_id="announce", data_schema=_announce_schema(self._opts)
        )

    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store the options (the entry reloads)."""
        return self.async_create_entry(data=self._opts)

