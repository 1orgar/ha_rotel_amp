"""Diagnostic sensors with Rotel device / connection information."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RotelConfigEntry
from .client import RotelClient
from .entity import device_info


@dataclass(frozen=True, kw_only=True)
class RotelSensorDescription(SensorEntityDescription):
    """Sensor reading a value from the client."""

    value_fn: Callable[[RotelClient], Any]
    keys: tuple[str, ...] = ()  # amp messages that refresh the sensor
    available_when_disconnected: bool = False


def _info(key: str, **kwargs: Any) -> RotelSensorDescription:
    return RotelSensorDescription(
        key=key, translation_key=key, keys=(kwargs.pop("msg", key),), **kwargs
    )


SENSORS: tuple[RotelSensorDescription, ...] = (
    _info("model", msg="model", icon="mdi:amplifier",
          value_fn=lambda c: c.device_info.get("model")),
    _info("firmware", msg="version", icon="mdi:chip",
          value_fn=lambda c: c.device_info.get("version")),
    _info("pc_usb_firmware", msg="pc_version", icon="mdi:usb",
          value_fn=lambda c: c.device_info.get("pc_version"),
          entity_registry_enabled_default=False),
    _info("ip_address", msg="ip", icon="mdi:ip-network",
          value_fn=lambda c: c.device_info.get("ip") or c.host,
          available_when_disconnected=True),
    _info("mac_address", msg="mac", icon="mdi:network",
          value_fn=lambda c: c.device_info.get("mac")),
    _info("latency", msg="ping", icon="mdi:timer-outline",
          device_class=SensorDeviceClass.DURATION,
          native_unit_of_measurement=UnitOfTime.MILLISECONDS,
          value_fn=lambda c: c.last_ping_ms),
    RotelSensorDescription(
        key="connection",
        translation_key="connection",
        icon="mdi:lan-connect",
        device_class=SensorDeviceClass.ENUM,
        options=["connected", "disconnected"],
        value_fn=lambda c: "connected" if c.connected else "disconnected",
        available_when_disconnected=True,
    ),
    RotelSensorDescription(
        key="connected_since",
        translation_key="connected_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.connected_since if c.connected else None,
    ),
    RotelSensorDescription(
        key="last_message",
        translation_key="last_message",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.last_message,
        entity_registry_enabled_default=False,
        available_when_disconnected=True,
    ),
    RotelSensorDescription(
        key="reconnects",
        translation_key="reconnects",
        icon="mdi:connection",
        value_fn=lambda c: c.reconnects,
        available_when_disconnected=True,
    ),
    RotelSensorDescription(
        key="last_error",
        translation_key="last_error",
        icon="mdi:alert-circle-outline",
        value_fn=lambda c: c.last_error,
        available_when_disconnected=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RotelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up diagnostic sensors."""
    client = entry.runtime_data
    async_add_entities(RotelSensor(entry, client, d) for d in SENSORS)


class RotelSensor(SensorEntity):
    """Diagnostic sensor."""

    entity_description: RotelSensorDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        entry: RotelConfigEntry,
        client: RotelClient,
        description: RotelSensorDescription,
    ) -> None:
        self.entity_description = description
        self._client = client
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry, client)

    async def async_added_to_hass(self) -> None:
        """Subscribe to client updates."""
        self.async_on_remove(self._client.add_update_callback(self._on_message))
        self.async_on_remove(self._client.add_connection_callback(self._on_connection))

    @callback
    def _on_message(self, key: str, _value: str) -> None:
        if key in self.entity_description.keys or (
            key == "ipaddress" and "ip" in self.entity_description.keys
        ):
            self.async_write_ha_state()

    @callback
    def _on_connection(self, _connected: bool) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Device info sensors are unavailable while disconnected."""
        return (
            self.entity_description.available_when_disconnected
            or self._client.connected
        )

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Current value."""
        return self.entity_description.value_fn(self._client)
