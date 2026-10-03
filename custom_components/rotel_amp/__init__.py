"""The Rotel Amplifier integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .client import RotelClient
from .const import (
    CONF_POLL_INTERVAL,
    CONF_SOURCE_NAMES,
    CONF_SOURCE_PLAYERS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]

type RotelConfigEntry = ConfigEntry[RotelClient]


async def async_setup_entry(hass: HomeAssistant, entry: RotelConfigEntry) -> bool:
    """Set up Rotel from a config entry."""
    client = RotelClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        float(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
    )
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The client reconnects by itself, so the entry is set up even when the
    # amplifier is currently unreachable; the entity is just unavailable.
    client.start(
        lambda coro: entry.async_create_background_task(
            hass, coro, f"rotel_amp_{entry.entry_id}"
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _update_device(key: str, value: str) -> None:
        """Model/firmware/MAC arrive after connecting: update the device."""
        if key not in ("model", "version", "mac"):
            return
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)}
        )
        if device is None:
            return
        changes: dict = {}
        if key == "model" and device.model != value:
            changes["model"] = value
        elif key == "version" and device.sw_version != value:
            changes["sw_version"] = value
        elif key == "mac":
            conn = (dr.CONNECTION_NETWORK_MAC, dr.format_mac(value))
            if conn not in device.connections:
                changes["merge_connections"] = {conn}
        if changes:
            device_registry.async_update_device(device.id, **changes)

    entry.async_on_unload(client.add_update_callback(_update_device))
    _async_setup_player_tracking(hass, entry)
    return True


def _linked_players(entry: RotelConfigEntry) -> dict[str, str]:
    return dict(entry.options.get(CONF_SOURCE_PLAYERS, {}))


@callback
def _async_check_missing_players(hass: HomeAssistant, entry: RotelConfigEntry) -> None:
    """Raise / clear a repair issue for linked players that don't exist."""
    registry = er.async_get(hass)
    names = entry.options.get(CONF_SOURCE_NAMES, {})
    missing = [
        (key, entity_id)
        for key, entity_id in _linked_players(entry).items()
        if registry.async_get(entity_id) is None and hass.states.get(entity_id) is None
    ]
    issue_id = f"missing_player_{entry.entry_id}"
    if missing:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_player",
            translation_placeholders={
                "title": entry.title,
                "players": ", ".join(
                    f"{names.get(key, key)} → {entity_id}" for key, entity_id in missing
                ),
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


@callback
def _async_setup_player_tracking(hass: HomeAssistant, entry: RotelConfigEntry) -> None:
    """Follow renames of linked players and warn when they disappear."""

    @callback
    def _registry_updated(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        data = event.data
        players = _linked_players(entry)
        if data["action"] == "update" and "old_entity_id" in data:
            old, new = data["old_entity_id"], data["entity_id"]
            if old in players.values():
                _LOGGER.info("Linked player renamed %s -> %s", old, new)
                updated = {k: (new if v == old else v) for k, v in players.items()}
                hass.config_entries.async_update_entry(
                    entry, options={**entry.options, CONF_SOURCE_PLAYERS: updated}
                )
                return  # options update reloads the entry
        if data["action"] in ("remove", "create") and (
            data["entity_id"] in players.values()
        ):
            _async_check_missing_players(hass, entry)

    entry.async_on_unload(
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _registry_updated)
    )

    # check once HA has finished starting (other integrations add their players)
    if hass.state is CoreState.running:
        _async_check_missing_players(hass, entry)
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                lambda _e: _async_check_missing_players(hass, entry),
            )
        )


async def _async_update_listener(hass: HomeAssistant, entry: RotelConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RotelConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.stop()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: RotelConfigEntry) -> None:
    """Clean up the repair issue when the entry is deleted."""
    ir.async_delete_issue(hass, DOMAIN, f"missing_player_{entry.entry_id}")
