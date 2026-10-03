"""Shared entity helpers."""
from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from . import RotelConfigEntry
from .client import RotelClient
from .const import DOMAIN


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
