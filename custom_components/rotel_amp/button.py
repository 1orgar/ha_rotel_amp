"""Connection test button."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RotelConfigEntry
from .client import RotelClient
from .entity import device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RotelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    async_add_entities([RotelTestConnectionButton(entry, entry.runtime_data)])


class RotelTestConnectionButton(ButtonEntity):
    """Ping the amplifier; result goes to the latency sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "test_connection"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-check"

    def __init__(self, entry: RotelConfigEntry, client: RotelClient) -> None:
        self._client = client
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_test_connection"
        self._attr_device_info = device_info(entry, client)

    async def async_press(self) -> None:
        """Run the connection test."""
        try:
            latency = await self._client.async_ping()
        except ConnectionError as err:
            raise HomeAssistantError(f"Rotel is not connected: {err}") from err
        except TimeoutError as err:
            raise HomeAssistantError("Rotel did not answer in time") from err
        _LOGGER.info("Rotel answered in %s ms", latency)
