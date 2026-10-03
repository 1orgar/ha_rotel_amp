"""Config flow for the Rotel Amplifier integration."""
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
from homeassistant.core import callback
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
    SOURCE_FIXVOL_PREFIX,
    SOURCE_FOLLOW_PREFIX,
    SOURCE_KEEPON_PREFIX,
    SOURCE_NAME_PREFIX,
    SOURCE_PLAYER_PREFIX,
    SOURCE_REFVOL_PREFIX,
    SOURCES,
)

_LOGGER = logging.getLogger(__name__)


def _sources_schema(
    selected: list[str],
    max_volume: int,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    auto_off: int = DEFAULT_AUTO_OFF,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SOURCES, default=selected): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=key, label=default)
                        for key, (_, _, default) in SOURCES.items()
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(CONF_MAX_VOLUME, default=max_volume): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=96, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_POLL_INTERVAL, default=poll_interval
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3600,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_AUTO_OFF, default=auto_off): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=720,
                    step=1,
                    unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


NO_ANNOUNCE = "none"


def _names_schema(sources: list[str], opts: dict[str, Any]) -> vol.Schema:
    """Per input: name, linked player, flags, reference volume; announce settings."""
    names: dict[str, str] = opts.get(CONF_SOURCE_NAMES, {})
    players: dict[str, str] = opts.get(CONF_SOURCE_PLAYERS, {})
    follow: list[str] = opts.get(CONF_SOURCE_FOLLOW, [])
    fixvol: list[str] = opts.get(CONF_SOURCE_FIXED_VOLUME, [])
    refvol: dict[str, int] = opts.get(CONF_SOURCE_REF_VOLUME, {})
    keepon: list[str] = opts.get(CONF_SOURCE_KEEP_ON, [])
    fields: dict[Any, Any] = {}
    for key in sources:
        fields[
            vol.Required(
                f"{SOURCE_NAME_PREFIX}{key}",
                default=names.get(key, SOURCES[key][2]),
            )
        ] = selector.TextSelector()
        player_key = f"{SOURCE_PLAYER_PREFIX}{key}"
        # suggested_value (not default) so the field can be cleared
        marker = vol.Optional(
            player_key,
            description={"suggested_value": players.get(key)} if players.get(key) else None,
        )
        fields[marker] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        )
        fields[
            vol.Optional(f"{SOURCE_FOLLOW_PREFIX}{key}", default=key in follow)
        ] = selector.BooleanSelector()
        fields[
            vol.Optional(f"{SOURCE_FIXVOL_PREFIX}{key}", default=key in fixvol)
        ] = selector.BooleanSelector()
        fields[
            vol.Optional(f"{SOURCE_REFVOL_PREFIX}{key}", default=int(refvol.get(key, 0)))
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=96, step=1, mode=selector.NumberSelectorMode.BOX
            )
        )
        fields[
            vol.Optional(f"{SOURCE_KEEPON_PREFIX}{key}", default=key in keepon)
        ] = selector.BooleanSelector()
    fields[
        vol.Optional(
            CONF_ANNOUNCE_SOURCE,
            default=opts.get(CONF_ANNOUNCE_SOURCE) or NO_ANNOUNCE,
        )
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=NO_ANNOUNCE, label="—")]
            + [
                selector.SelectOptionDict(value=k, label=names.get(k, SOURCES[k][2]))
                for k in sources
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    fields[
        vol.Optional(
            CONF_ANNOUNCE_VOLUME, default=int(opts.get(CONF_ANNOUNCE_VOLUME, 0))
        )
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=1,
            unit_of_measurement="%",
            mode=selector.NumberSelectorMode.SLIDER,
        )
    )
    return vol.Schema(fields)


def _names_options(
    sources: list[str], user_input: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Parse the per-input step into options and validation errors."""
    names = _names_from_input(sources, user_input)
    players = _players_from_input(sources, user_input)
    errors = _validate_names(names)
    announce = user_input.get(CONF_ANNOUNCE_SOURCE) or NO_ANNOUNCE
    if announce != NO_ANNOUNCE and announce not in players:
        errors[CONF_ANNOUNCE_SOURCE] = "announce_needs_player"
    refvol = {
        k: int(v)
        for k in sources
        if (v := user_input.get(f"{SOURCE_REFVOL_PREFIX}{k}")) and int(v) > 0
    }
    options = {
        CONF_SOURCE_NAMES: names,
        CONF_SOURCE_PLAYERS: players,
        CONF_SOURCE_FOLLOW: _flags_from_input(players, user_input, SOURCE_FOLLOW_PREFIX),
        CONF_SOURCE_FIXED_VOLUME: _flags_from_input(
            players, user_input, SOURCE_FIXVOL_PREFIX
        ),
        CONF_SOURCE_REF_VOLUME: refvol,
        CONF_SOURCE_KEEP_ON: [
            k for k in sources if user_input.get(f"{SOURCE_KEEPON_PREFIX}{k}")
        ],
        CONF_ANNOUNCE_SOURCE: None if announce == NO_ANNOUNCE else announce,
        CONF_ANNOUNCE_VOLUME: int(user_input.get(CONF_ANNOUNCE_VOLUME) or 0),
    }
    return options, errors


def _flags_from_input(
    players: dict[str, str], user_input: dict[str, Any], prefix: str
) -> list[str]:
    """Inputs with a per-player flag enabled (only those that have a player)."""
    return [k for k in players if user_input.get(f"{prefix}{k}")]


def _names_from_input(sources: list[str], user_input: dict[str, Any]) -> dict[str, str]:
    """Build {source_key: name}; empty names fall back to defaults."""
    return {
        key: (user_input.get(f"{SOURCE_NAME_PREFIX}{key}") or "").strip()
        or SOURCES[key][2]
        for key in sources
    }


def _players_from_input(
    sources: list[str], user_input: dict[str, Any]
) -> dict[str, str]:
    """Build {source_key: media_player entity_id} for inputs that have one."""
    return {
        key: player
        for key in sources
        if (player := user_input.get(f"{SOURCE_PLAYER_PREFIX}{key}"))
    }


def _validate_names(names: dict[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    seen: set[str] = set()
    for key, name in names.items():
        if name.casefold() in seen:
            errors[f"{SOURCE_NAME_PREFIX}{key}"] = "duplicate_name"
        seen.add(name.casefold())
    return errors


def _parse_sources(user_input: dict[str, Any]) -> list[str]:
    """Keep the canonical order of sources."""
    return [k for k in SOURCES if k in user_input[CONF_SOURCES]]


class RotelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rotel."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._sources: list[str] = []
        self._max_volume: int = DEFAULT_MAX_VOLUME
        self._poll: int = DEFAULT_POLL_INTERVAL
        self._auto_off: int = DEFAULT_AUTO_OFF

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
            # an entry moved to this address by reconfigure keeps its old unique_id
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
            try:
                info = await async_test_connection(host, port)
            except (OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except NoResponseError:
                errors["base"] = "no_response"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                _LOGGER.debug("Rotel answered: %s", info)
                self._data = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_NAME: user_input[CONF_NAME],
                }
                return await self.async_step_sources()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which inputs are used."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_SOURCES]:
                errors[CONF_SOURCES] = "no_sources"
            else:
                self._sources = _parse_sources(user_input)
                self._max_volume = int(user_input[CONF_MAX_VOLUME])
                self._poll = int(user_input[CONF_POLL_INTERVAL])
                self._auto_off = int(user_input[CONF_AUTO_OFF])
                return await self.async_step_names()
        return self.async_show_form(
            step_id="sources",
            data_schema=_sources_schema(
                self._sources or list(SOURCES),
                self._max_volume,
                self._poll,
                self._auto_off,
            ),
            errors=errors,
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename selected inputs."""
        errors: dict[str, str] = {}
        opts: dict[str, Any] = {}
        if user_input is not None:
            opts, errors = _names_options(self._sources, user_input)
            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_NAME],
                    data=self._data,
                    options={
                        CONF_SOURCES: self._sources,
                        **opts,
                        CONF_MAX_VOLUME: self._max_volume,
                        CONF_POLL_INTERVAL: self._poll,
                        CONF_AUTO_OFF: self._auto_off,
                    },
                )
        return self.async_show_form(
            step_id="names",
            data_schema=_names_schema(self._sources, opts),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host / port without losing the input configuration."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            try:
                await async_test_connection(host, port)
            except (OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except NoResponseError:
                errors["base"] = "no_response"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                # The entry unique_id (and therefore every entity's unique_id
                # and entity_id) is kept, so automations keep working.
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
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RotelOptionsFlow:
        """Return the options flow."""
        return RotelOptionsFlow()


class RotelOptionsFlow(OptionsFlow):
    """Change inputs / names / max volume."""

    def __init__(self) -> None:
        self._sources: list[str] = []
        self._max_volume: int = DEFAULT_MAX_VOLUME
        self._poll: int = DEFAULT_POLL_INTERVAL
        self._auto_off: int = DEFAULT_AUTO_OFF

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick inputs."""
        errors: dict[str, str] = {}
        options = self.config_entry.options
        if user_input is not None:
            if not user_input[CONF_SOURCES]:
                errors[CONF_SOURCES] = "no_sources"
            else:
                self._sources = _parse_sources(user_input)
                self._max_volume = int(user_input[CONF_MAX_VOLUME])
                self._poll = int(user_input[CONF_POLL_INTERVAL])
                self._auto_off = int(user_input[CONF_AUTO_OFF])
                return await self.async_step_names()
        return self.async_show_form(
            step_id="init",
            data_schema=_sources_schema(
                options.get(CONF_SOURCES, list(SOURCES)),
                int(options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)),
                int(options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
                int(options.get(CONF_AUTO_OFF, DEFAULT_AUTO_OFF)),
            ),
            errors=errors,
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename inputs."""
        errors: dict[str, str] = {}
        opts: dict[str, Any] = dict(self.config_entry.options)
        if user_input is not None:
            opts, errors = _names_options(self._sources, user_input)
            players = opts[CONF_SOURCE_PLAYERS]
            own = {
                e.entity_id
                for e in er.async_entries_for_config_entry(
                    er.async_get(self.hass), self.config_entry.entry_id
                )
            }
            for key, player in players.items():
                if player in own:
                    errors[f"{SOURCE_PLAYER_PREFIX}{key}"] = "self_player"
            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_SOURCES: self._sources,
                        **opts,
                        CONF_MAX_VOLUME: self._max_volume,
                        CONF_POLL_INTERVAL: self._poll,
                        CONF_AUTO_OFF: self._auto_off,
                    }
                )
        return self.async_show_form(
            step_id="names",
            data_schema=_names_schema(self._sources, opts),
            errors=errors,
        )

