"""The Rotel Amplifier integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .client import RotelClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.BUTTON]

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
    return True


async def _async_update_listener(hass: HomeAssistant, entry: RotelConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RotelConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.stop()
    return unload_ok
