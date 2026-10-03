"""Tone and balance controls."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RotelConfigEntry
from .client import RotelClient
from .entity import RotelControlEntity


def parse_signed(value: str) -> int:
    """Parse '+05' / '-05' / '000' / 'L05' / 'R05'."""
    value = value.strip()
    if value[:1] in ("L", "l", "-"):
        return -int(value[1:])
    if value[:1] in ("R", "r", "+"):
        return int(value[1:])
    return int(value)


def tone_command(name: str, level: int) -> str:
    """bass_+05! / bass_-03! / bass_000!"""
    return f"{name}_{level:+03d}!" if level else f"{name}_000!"


def balance_command(level: int) -> str:
    """balance_r05! / balance_l03! / balance_000!"""
    if level == 0:
        return "balance_000!"
    return f"balance_{'r' if level > 0 else 'l'}{abs(level):02d}!"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RotelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tone controls."""
    client = entry.runtime_data
    async_add_entities(
        [
            RotelNumber(entry, client, "bass", -10, 10, "mdi:speaker"),
            RotelNumber(entry, client, "treble", -10, 10, "mdi:surround-sound"),
            RotelNumber(entry, client, "balance", -15, 15, "mdi:scale-balance"),
        ]
    )


class RotelNumber(RotelControlEntity, NumberEntity):
    """Bass / treble / balance slider."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(
        self,
        entry: RotelConfigEntry,
        client: RotelClient,
        key: str,
        lo: int,
        hi: int,
        icon: str,
    ) -> None:
        super().__init__(entry, client, key)
        self._name = key
        self._keys = (key,)
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        """Current level."""
        value = self._value()
        if value is None:
            return None
        try:
            return parse_signed(value)
        except (ValueError, IndexError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set level."""
        level = int(round(value))
        if self._name == "balance":
            await self._send(balance_command(level))
        else:
            await self._send(tone_command(self._name, level))
