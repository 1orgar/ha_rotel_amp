"""Speaker A/B and tone bypass switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RotelConfigEntry
from .client import RotelClient
from .entity import RotelControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RotelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    client = entry.runtime_data
    async_add_entities(
        [
            RotelSpeakerSwitch(entry, client, "a"),
            RotelSpeakerSwitch(entry, client, "b"),
            RotelBypassSwitch(entry, client),
        ]
    )


class RotelSpeakerSwitch(RotelControlEntity, SwitchEntity):
    """Speaker output A or B."""

    _attr_icon = "mdi:speaker"
    _keys = ("speaker",)

    def __init__(self, entry: RotelConfigEntry, client: RotelClient, side: str) -> None:
        super().__init__(entry, client, f"speaker_{side}")
        self._side = side

    @property
    def is_on(self) -> bool | None:
        """Speaker enabled (amp reports a / b / a_b / off)."""
        value = self._value()
        if value is None:
            return None
        return self._side in value.replace("off", "")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable output."""
        await self._send(f"speaker_{self._side}_on!")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable output."""
        await self._send(f"speaker_{self._side}_off!")


class RotelBypassSwitch(RotelControlEntity, SwitchEntity):
    """Tone bypass."""

    _attr_icon = "mdi:tune-variant"
    _keys = ("bypass",)

    def __init__(self, entry: RotelConfigEntry, client: RotelClient) -> None:
        super().__init__(entry, client, "bypass")

    @property
    def is_on(self) -> bool | None:
        """Bypass on."""
        value = self._value()
        return None if value is None else value == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable bypass."""
        await self._send("bypass_on!")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable bypass."""
        await self._send("bypass_off!")
