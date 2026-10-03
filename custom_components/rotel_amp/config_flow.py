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

from .client import async_test_connection
from .const import (
    CONF_AUTO_OFF,
    CONF_MAX_VOLUME,
    CONF_POLL_INTERVAL,
    CONF_SOURCE_FOLLOW,
    CONF_SOURCE_NAMES,
    CONF_SOURCE_PLAYERS,
    CONF_SOURCES,
    DEFAULT_AUTO_OFF,
    DEFAULT_MAX_VOLUME,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
    SOURCE_FOLLOW_PREFIX,
    SOURCE_NAME_PREFIX,
    SOURCE_PLAYER_PREFIX,
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


def _names_schema(
    sources: list[str],
    names: dict[str, str],
    players: dict[str, str],
    follow: list[str],
) -> vol.Schema:
    """Per input: name, optional linked media player, follow-playback switch."""
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
    return vol.Schema(fields)


def _follow_from_input(
    players: dict[str, str], user_input: dict[str, Any]
) -> list[str]:
    """Inputs with follow-playback enabled (only those that have a player)."""
    return [k for k in players if user_input.get(f"{SOURCE_FOLLOW_PREFIX}{k}")]


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
            try:
                await async_test_connection(host, port)
            except (OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
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
        names: dict[str, str] = {}
        players: dict[str, str] = {}
        follow: list[str] = []
        if user_input is not None:
            names = _names_from_input(self._sources, user_input)
            players = _players_from_input(self._sources, user_input)
            follow = _follow_from_input(players, user_input)
            errors = _validate_names(names)
            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_NAME],
                    data=self._data,
                    options={
                        CONF_SOURCES: self._sources,
                        CONF_SOURCE_NAMES: names,
                        CONF_SOURCE_PLAYERS: players,
                        CONF_SOURCE_FOLLOW: follow,
                        CONF_MAX_VOLUME: self._max_volume,
                        CONF_POLL_INTERVAL: self._poll,
                        CONF_AUTO_OFF: self._auto_off,
                    },
                )
        return self.async_show_form(
            step_id="names",
            data_schema=_names_schema(self._sources, names, players, follow),
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
        names = dict(self.config_entry.options.get(CONF_SOURCE_NAMES, {}))
        players = dict(self.config_entry.options.get(CONF_SOURCE_PLAYERS, {}))
        follow = list(self.config_entry.options.get(CONF_SOURCE_FOLLOW, []))
        if user_input is not None:
            names = _names_from_input(self._sources, user_input)
            players = _players_from_input(self._sources, user_input)
            follow = _follow_from_input(players, user_input)
            errors = _validate_names(names)
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
                        CONF_SOURCE_NAMES: names,
                        CONF_SOURCE_PLAYERS: players,
                        CONF_SOURCE_FOLLOW: follow,
                        CONF_MAX_VOLUME: self._max_volume,
                        CONF_POLL_INTERVAL: self._poll,
                        CONF_AUTO_OFF: self._auto_off,
                    }
                )
        return self.async_show_form(
            step_id="names",
            data_schema=_names_schema(self._sources, names, players, follow),
            errors=errors,
        )

