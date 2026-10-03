"""The Rotel Amplifier integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .client import RotelClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

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
