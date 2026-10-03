"""Shared entity helpers."""
from __future__ import annotations

from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import Entity

from . import RotelConfigEntry
from .client import RotelClient
from .const import DOMAIN


class RotelControlEntity(Entity):
    """Base for amp settings exposed as entities (tone, speakers, dimmer)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    # amp keys that update this entity
    _keys: tuple[str, ...] = ()

    def __init__(self, entry: RotelConfigEntry, client: RotelClient, key: str) -> None:
        self._client = client
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry, client)

    async def async_added_to_hass(self) -> None:
        """Subscribe to client updates."""
        self.async_on_remove(self._client.add_update_callback(self._on_message))
        self.async_on_remove(
            self._client.add_connection_callback(lambda _c: self.async_write_ha_state())
        )

    @callback
    def _on_message(self, key: str, _value: str) -> None:
        if key in self._keys or key == "power":
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Settings can only be changed while the amp is connected and on."""
        return self._client.connected and self._client.values.get("power") == "on"

    def _value(self) -> str | None:
        for key in self._keys:
            if (value := self._client.values.get(key)) is not None:
                return value
        return None

    async def _send(self, command: str) -> None:
        try:
            await self._client.send(command)
        except ConnectionError as err:
            raise HomeAssistantError(str(err)) from err


def device_info(entry: RotelConfigEntry, client: RotelClient) -> DeviceInfo:
    """Device info shared by all platforms (model/firmware/MAC if known)."""
    info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        manufacturer="Rotel",
        name=entry.data[CONF_NAME],
    )
    if model := client.device_info.get("model"):
        info["model"] = model
    if version := client.device_info.get("version"):
        info["sw_version"] = version
    if mac := client.device_info.get("mac"):
        info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac))}
    return info
