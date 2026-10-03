"""Media player for Rotel amplifiers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import voluptuous as vol

from . import RotelConfigEntry
from .client import RotelClient
from .const import (
    CONF_MAX_VOLUME,
    CONF_SOURCE_NAMES,
    CONF_SOURCES,
    DEFAULT_MAX_VOLUME,
    DOMAIN,
    REPORTED_TO_SOURCE,
    SOURCES,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)


def _parse_signed(value: str) -> int:
    """Parse '+05' / '-05' / '000' / 'L05' / 'R05'."""
    value = value.strip()
    if value[:1] in ("L", "l", "-"):
        return -int(value[1:])
    if value[:1] in ("R", "r", "+"):
        return int(value[1:])
    return int(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RotelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Rotel media player."""
    async_add_entities([RotelMediaPlayer(entry, entry.runtime_data)])

    platform = entity_platform.async_get_current_platform()
    level = lambda lo, hi: {  # noqa: E731
        vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(min=lo, max=hi))
    }
    platform.async_register_entity_service("set_bass", level(-10, 10), "set_bass")
    platform.async_register_entity_service("set_treble", level(-10, 10), "set_treble")
    platform.async_register_entity_service("set_balance", level(-15, 15), "set_balance")
    platform.async_register_entity_service("set_dimmer", level(0, 6), "set_dimmer")
    platform.async_register_entity_service(
        "set_bypass", {vol.Required("bypass"): cv.boolean}, "set_bypass"
    )
    platform.async_register_entity_service(
        "set_speaker_a", {vol.Required("enabled"): cv.boolean}, "set_speaker_a"
    )
    platform.async_register_entity_service(
        "set_speaker_b", {vol.Required("enabled"): cv.boolean}, "set_speaker_b"
    )
    platform.async_register_entity_service(
        "set_pcusb_class",
        {vol.Required("usb_class"): vol.In(["1", "2"])},
        "set_pcusb_class",
    )
    simple = {
        "toggle_speaker_a": "speaker_a!",
        "toggle_speaker_b": "speaker_b!",
        "toggle_dimmer": "dimmer!",
        "bass_up": "bass_up!",
        "bass_down": "bass_down!",
        "treble_up": "treble_up!",
        "treble_down": "treble_down!",
        "balance_left": "balance_l!",
        "balance_right": "balance_r!",
    }
    for service, command in simple.items():
        platform.async_register_entity_service(
            service, {}, lambda ent, call, cmd=command: ent.async_send(cmd)
        )
    platform.async_register_entity_service(
        "get_current_status", {}, "async_refresh_state"
    )


class RotelMediaPlayer(MediaPlayerEntity):
    """Rotel amplifier entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_volume_step = 0.01

    def __init__(self, entry: RotelConfigEntry, client: RotelClient) -> None:
        self._client = client
        options = entry.options
        self._max_volume = int(options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME))
        self._sources: list[str] = [
            k for k in options.get(CONF_SOURCES, list(SOURCES)) if k in SOURCES
        ]
        names: dict[str, str] = options.get(CONF_SOURCE_NAMES, {})
        self._names = {k: names.get(k) or SOURCES[k][2] for k in self._sources}
        self._by_name = {v: k for k, v in self._names.items()}

        self._attr_unique_id = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Rotel",
            name=entry.data[CONF_NAME],
        )
        self._host_info = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        self._attr_available = False
        self._attr_state = None
        self._attr_source_list = [self._names[k] for k in self._sources]
        self._raw_source: str | None = None
        self._rotel_volume: int | None = None
        self._extra: dict[str, Any] = {
            "bass": None,
            "treble": None,
            "balance": None,
            "bypass": None,
            "speaker_a": None,
            "speaker_b": None,
            "dimmer": None,
            "pcusb_class": None,
            "frequency": None,
            "max_volume": self._max_volume,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to client callbacks."""
        self.async_on_remove(self._client.add_update_callback(self._handle_update))
        self.async_on_remove(
            self._client.add_connection_callback(self._handle_connection)
        )
        self._attr_available = self._client.connected

    @callback
    def _handle_connection(self, connected: bool) -> None:
        self._attr_available = connected
        self.async_write_ha_state()

    @callback
    def _handle_update(self, key: str, value: str) -> None:
        try:
            self._apply(key, value)
        except (ValueError, IndexError):
            _LOGGER.debug("Cannot parse %s=%s", key, value)
            return
        self.async_write_ha_state()

    def _apply(self, key: str, value: str) -> None:
        if key == "power":
            self._attr_state = (
                MediaPlayerState.ON if value == "on" else MediaPlayerState.OFF
            )
        elif key == "source":
            self._raw_source = value
        elif key == "volume":
            vol_int = int(value)
            if 0 <= vol_int <= 96:
                self._rotel_volume = vol_int
        elif key == "mute":
            self._attr_is_volume_muted = value == "on"
        elif key in ("bass", "treble", "balance"):
            self._extra[key] = _parse_signed(value)
        elif key == "bypass":
            self._extra["bypass"] = value == "on"
        elif key == "speaker":
            self._extra["speaker_a"] = "a" in value
            self._extra["speaker_b"] = "b" in value
        elif key == "dimmer":
            self._extra["dimmer"] = int(value) if value.isdigit() else 0
        elif key in ("pcusb_class", "pcusb"):
            self._extra["pcusb_class"] = value
        elif key == "freq":
            self._extra["frequency"] = value

    @property
    def volume_level(self) -> float | None:
        """Volume 0..1 (Rotel level mapped 1:1 like the original)."""
        return None if self._rotel_volume is None else self._rotel_volume / 100

    @property
    def source(self) -> str | None:
        """Current source with the user-defined name."""
        if self._raw_source is None:
            return None
        key = REPORTED_TO_SOURCE.get(self._raw_source)
        if key is None:
            return self._raw_source
        # a disabled input selected on the front panel shows its default name
        return self._names.get(key, SOURCES[key][2])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes."""
        return {**self._extra, "address": self._host_info}


    # ---- commands --------------------------------------------------------
    async def async_send(self, command: str) -> None:
        """Send command, converting errors for HA."""
        try:
            await self._client.send(command)
        except ConnectionError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_refresh_state(self) -> None:
        """Re-query all values."""
        try:
            await self._client.query_state()
        except ConnectionError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self) -> None:
        """Power on."""
        await self.async_send("power_on!")

    async def async_turn_off(self) -> None:
        """Power off."""
        await self.async_send("power_off!")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume, capped by max_volume."""
        level = round(volume * 100)
        if level > self._max_volume:
            raise ServiceValidationError(
                f"Volume {level} exceeds configured maximum {self._max_volume}"
            )
        await self.async_send(f"vol_{level:02d}!")

    async def async_volume_up(self) -> None:
        """Volume up (respects max_volume)."""
        if self._rotel_volume is not None and self._rotel_volume >= self._max_volume:
            return
        await self.async_send("vol_up!")

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self.async_send("vol_down!")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute."""
        await self.async_send("mute_on!" if mute else "mute_off!")

    async def async_select_source(self, source: str) -> None:
        """Select source by user-defined name."""
        key = self._by_name.get(source)
        if key is None:
            raise ServiceValidationError(f"Unknown source: {source}")
        await self.async_send(SOURCES[key][0])

    async def async_media_play(self) -> None:
        """Play."""
        await self.async_send("play!")

    async def async_media_pause(self) -> None:
        """Pause."""
        await self.async_send("pause!")

    async def async_media_stop(self) -> None:
        """Stop."""
        await self.async_send("stop!")

    async def async_media_next_track(self) -> None:
        """Next track."""
        await self.async_send("trkf!")

    async def async_media_previous_track(self) -> None:
        """Previous track."""
        await self.async_send("trkb!")

    # ---- custom services -------------------------------------------------
    async def set_bass(self, level: int) -> None:
        """Bass -10..10."""
        await self.async_send(f"bass_{level:+03d}!" if level else "bass_000!")

    async def set_treble(self, level: int) -> None:
        """Treble -10..10."""
        await self.async_send(f"treble_{level:+03d}!" if level else "treble_000!")

    async def set_balance(self, level: int) -> None:
        """Balance -15..15."""
        if level == 0:
            await self.async_send("balance_000!")
        else:
            side = "r" if level > 0 else "l"
            await self.async_send(f"balance_{side}{abs(level):02d}!")

    async def set_dimmer(self, level: int) -> None:
        """Dimmer 0..6."""
        await self.async_send(f"dimmer_{level}!")

    async def set_bypass(self, bypass: bool) -> None:
        """Tone bypass."""
        await self.async_send("bypass_on!" if bypass else "bypass_off!")

    async def set_speaker_a(self, enabled: bool) -> None:
        """Speaker A."""
        await self.async_send("speaker_a_on!" if enabled else "speaker_a_off!")

    async def set_speaker_b(self, enabled: bool) -> None:
        """Speaker B."""
        await self.async_send("speaker_b_on!" if enabled else "speaker_b_off!")

    async def set_pcusb_class(self, usb_class: str) -> None:
        """PC-USB audio class."""
        await self.async_send(f"pcusb_class_{usb_class}!")

