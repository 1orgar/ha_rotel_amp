"""Display dimmer and PC-USB class selects."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RotelConfigEntry
from .client import RotelClient
from .entity import RotelControlEntity

DIMMER_OPTIONS = [str(i) for i in range(7)]  # 0 = brightest
PCUSB_OPTIONS = ["1", "2"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RotelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    client = entry.runtime_data
    async_add_entities([RotelDimmerSelect(entry, client), RotelPcUsbSelect(entry, client)])


class RotelDimmerSelect(RotelControlEntity, SelectEntity):
    """Front panel brightness."""

    _attr_icon = "mdi:brightness-6"
    _attr_options = DIMMER_OPTIONS
    _keys = ("dimmer",)

    def __init__(self, entry: RotelConfigEntry, client: RotelClient) -> None:
        super().__init__(entry, client, "dimmer")

    @property
    def current_option(self) -> str | None:
        """Current dimmer level."""
        value = self._value()
        if value is None:
            return None
        value = value.lstrip("0") or "0"
        return value if value in DIMMER_OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        """Set dimmer level."""
        await self._send(f"dimmer_{option}!")


class RotelPcUsbSelect(RotelControlEntity, SelectEntity):
    """PC-USB audio class."""

    _attr_icon = "mdi:usb"
    _attr_options = PCUSB_OPTIONS
    _attr_entity_registry_enabled_default = False
    _keys = ("pcusb_class", "pcusb")

    def __init__(self, entry: RotelConfigEntry, client: RotelClient) -> None:
        super().__init__(entry, client, "pcusb_class")

    @property
    def current_option(self) -> str | None:
        """Current USB audio class."""
        value = self._value()
        if value is None:
            return None
        digits = "".join(ch for ch in value if ch.isdigit())
        return digits if digits in PCUSB_OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        """Set USB audio class."""
        await self._send(f"pcusb_class_{option}!")
