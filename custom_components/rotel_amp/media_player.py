"""Media player for Rotel amplifiers."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.media_player import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DATA_COMPONENT as MP_DATA_COMPONENT,
    DOMAIN as MP_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    SERVICE_SHUFFLE_SET,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_PORT,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
import voluptuous as vol

from . import RotelConfigEntry
from .client import RotelClient
from .const import (
    CONF_AUTO_OFF,
    CONF_MAX_VOLUME,
    CONF_SOURCE_FIXED_VOLUME,
    CONF_SOURCE_FOLLOW,
    CONF_SOURCE_NAMES,
    CONF_SOURCE_PLAYERS,
    CONF_SOURCES,
    DEFAULT_AUTO_OFF,
    DEFAULT_MAX_VOLUME,
    POWER_ON_SETTLE,
    POWER_ON_TIMEOUT,
    REPORTED_TO_SOURCE,
    SOURCE_ATTEMPTS,
    SOURCE_CONFIRM_TIMEOUT,
    SOURCES,
)
from .entity import device_info

_LOGGER = logging.getLogger(__name__)

# Always handled by the amplifier itself (power, volume, input).
OWN_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

# Without a linked player the amp's own transport commands are used.
SUPPORTED_FEATURES = (
    OWN_FEATURES
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)

# Features taken from the linked player of the current input.
PROXY_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.MEDIA_ENQUEUE
    | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
)

# Linked player states shown instead of plain "on".
PROXY_STATES = {
    MediaPlayerState.PLAYING,
    MediaPlayerState.PAUSED,
    MediaPlayerState.IDLE,
    MediaPlayerState.BUFFERING,
}

# property name -> linked player attribute
PROXY_ATTRS = {
    "media_content_id": ATTR_MEDIA_CONTENT_ID,
    "media_content_type": ATTR_MEDIA_CONTENT_TYPE,
    "media_duration": ATTR_MEDIA_DURATION,
    "media_position": ATTR_MEDIA_POSITION,
    "media_position_updated_at": ATTR_MEDIA_POSITION_UPDATED_AT,
    "media_title": ATTR_MEDIA_TITLE,
    "media_artist": ATTR_MEDIA_ARTIST,
    "media_album_name": ATTR_MEDIA_ALBUM_NAME,
    "media_album_artist": ATTR_MEDIA_ALBUM_ARTIST,
    "media_track": ATTR_MEDIA_TRACK,
    "media_series_title": ATTR_MEDIA_SERIES_TITLE,
    "media_season": ATTR_MEDIA_SEASON,
    "media_episode": ATTR_MEDIA_EPISODE,
    "media_channel": ATTR_MEDIA_CHANNEL,
    "media_playlist": ATTR_MEDIA_PLAYLIST,
    "app_id": ATTR_APP_ID,
    "app_name": ATTR_APP_NAME,
    "shuffle": ATTR_MEDIA_SHUFFLE,
    "repeat": ATTR_MEDIA_REPEAT,
}


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
        players: dict[str, str] = options.get(CONF_SOURCE_PLAYERS, {})
        self._players = {k: v for k, v in players.items() if k in self._sources and v}
        self._follow = {
            k for k in options.get(CONF_SOURCE_FOLLOW, []) if k in self._players
        }
        self._auto_off = float(options.get(CONF_AUTO_OFF, DEFAULT_AUTO_OFF)) * 60
        self._auto_off_unsub: CALLBACK_TYPE | None = None
        self._power_on_event = asyncio.Event()
        self._source_event = asyncio.Event()
        self._follow_task: asyncio.Task | None = None
        self._fixvol = {
            k
            for k in options.get(CONF_SOURCE_FIXED_VOLUME, [])
            if k in self._players
        }
        self._fixvol_players = {self._players[k] for k in self._fixvol}
        self._exclusive_task: asyncio.Task | None = None

        self._attr_unique_id = entry.unique_id or entry.entry_id
        self._attr_device_info = device_info(entry, client)
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
        if self._players:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, sorted(set(self._players.values())), self._handle_linked
                )
            )

        self.async_on_remove(self._cancel_auto_off)
        self.async_on_remove(self._cancel_follow)
        if self._fixvol_players:
            self._enforce_all_fixed_volume()

    @callback
    def _handle_linked(self, event: Event[EventStateChangedData]) -> None:
        """React to linked player changes."""
        entity_id = event.data["entity_id"]
        new, old = event.data["new_state"], event.data["old_state"]
        if entity_id in self._fixvol_players:
            self._enforce_fixed_volume(new)
        if (
            new is not None
            and new.state == MediaPlayerState.PLAYING
            and (old is None or old.state != MediaPlayerState.PLAYING)
        ):
            key = next(
                (k for k in self._follow if self._players[k] == entity_id), None
            )
            if key is not None:
                self._start_follow(key)
            elif self._follow and self._attr_state == MediaPlayerState.ON:
                # a non-follow player started while another input is active
                self._schedule_exclusive()
        if entity_id == self._linked_entity_id:
            self._write_state()

    # ---- fixed 100 % volume on linked players -----------------------------
    @callback
    def _enforce_fixed_volume(self, state: State | None) -> None:
        """Keep the linked player at 100 % (volume is controlled on the amp)."""
        if state is None or state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            MediaPlayerState.OFF,
        ):
            return
        features = int(state.attributes.get(ATTR_SUPPORTED_FEATURES, 0))
        level = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
        muted = state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
        calls: list[tuple[str, dict[str, Any]]] = []
        if (
            features & MediaPlayerEntityFeature.VOLUME_SET
            and level is not None
            and float(level) < 0.999
        ):
            calls.append((SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 1.0}))
        if features & MediaPlayerEntityFeature.VOLUME_MUTE and muted:
            calls.append((SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}))
        for service, data in calls:
            _LOGGER.debug("Restoring %s on %s", data, state.entity_id)
            self.hass.async_create_task(
                self._async_call_quiet(state.entity_id, service, data)
            )

    async def _async_call_quiet(
        self, entity_id: str, service: str, data: dict[str, Any] | None = None
    ) -> None:
        try:
            await self.hass.services.async_call(
                MP_DOMAIN, service, {**(data or {}), ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("%s on %s failed: %s", service, entity_id, err)

    @callback
    def _enforce_all_fixed_volume(self) -> None:
        for entity_id in self._fixvol_players:
            self._enforce_fixed_volume(self.hass.states.get(entity_id))

    @callback
    def _handle_connection(self, connected: bool) -> None:
        self._attr_available = connected
        self._write_state()

    @callback
    def _handle_update(self, key: str, value: str) -> None:
        try:
            self._apply(key, value)
        except (ValueError, IndexError):
            _LOGGER.debug("Cannot parse %s=%s", key, value)
            return
        self._write_state()

    @callback
    def _write_state(self) -> None:
        self.async_write_ha_state()
        self._update_auto_off()
        self._check_exclusive()

    @callback
    def _check_exclusive(self) -> None:
        """With follow enabled, only the current input's player may play.

        Runs whenever the amp state changes (input switched by hand or by the
        remote, amp turned on): if several linked players are playing, all
        but the one of the current input are paused.
        """
        if not self._follow or self._attr_state != MediaPlayerState.ON:
            return
        current = self._linked_entity_id
        if current is None:
            return
        for other in set(self._players.values()) - {current}:
            state = self.hass.states.get(other)
            if state is not None and state.state == MediaPlayerState.PLAYING:
                self._schedule_exclusive()
                return

    # ---- follow playback -------------------------------------------------
    @callback
    def _start_follow(self, key: str) -> None:
        """A follow-enabled player started playing: switch the amp to it."""
        self._cancel_follow()
        self._follow_task = self.hass.async_create_background_task(
            self._async_follow(key), f"rotel_amp_follow_{key}"
        )

    @callback
    def _cancel_follow(self) -> None:
        if self._follow_task and not self._follow_task.done():
            self._follow_task.cancel()
        self._follow_task = None

    @property
    def _current_key(self) -> str | None:
        return REPORTED_TO_SOURCE.get(self._raw_source or "")

    async def _async_follow(self, key: str) -> None:
        player = self._players[key]
        _LOGGER.debug("%s started playing, switching to input %s", player, key)
        # Stop the others right away: the amp switch must not delay this.
        stop_task = self.hass.async_create_task(self._async_stop_others(player))
        try:
            if self._attr_state != MediaPlayerState.ON:
                self._power_on_event.clear()
                await self._client.send("power_on!")
                async with asyncio.timeout(POWER_ON_TIMEOUT):
                    await self._power_on_event.wait()
                await asyncio.sleep(POWER_ON_SETTLE)
            await self._async_switch_source(key)
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.warning("Cannot switch Rotel to %s: %s", self._names[key], err)
        await stop_task

    async def _async_switch_source(self, key: str) -> None:
        """Send the input command until the amp confirms it (fast retries).

        Right after power on the amp may silently ignore the command, so
        instead of a long fixed delay the command is repeated.
        """
        for _ in range(SOURCE_ATTEMPTS):
            if self._current_key == key:
                return
            self._source_event.clear()
            await self._client.send(SOURCES[key][0])
            try:
                async with asyncio.timeout(SOURCE_CONFIRM_TIMEOUT):
                    while self._current_key != key:
                        await self._source_event.wait()
                        self._source_event.clear()
            except TimeoutError:
                continue
            return
        raise TimeoutError(f"input {key} not confirmed")

    async def _async_stop_others(self, keep: str | None) -> None:
        """Pause (or stop) every linked player except `keep` that is playing."""
        others = [
            other
            for other in sorted(set(self._players.values()) - {keep})
            if (state := self.hass.states.get(other)) is not None
            and state.state in (MediaPlayerState.PLAYING, MediaPlayerState.BUFFERING)
        ]
        tasks = []
        for other in others:
            state = self.hass.states.get(other)
            features = int(state.attributes.get(ATTR_SUPPORTED_FEATURES, 0))
            service = (
                SERVICE_MEDIA_PAUSE
                if features & MediaPlayerEntityFeature.PAUSE
                else SERVICE_MEDIA_STOP
            )
            _LOGGER.debug("Stopping %s (%s)", other, service)
            tasks.append(self._async_call_quiet(other, service))
        if tasks:
            await asyncio.gather(*tasks)

    @callback
    def _schedule_exclusive(self) -> None:
        """Only the player of the current input may play; stop the rest."""
        if self._exclusive_task and not self._exclusive_task.done():
            return
        if self._follow_task and not self._follow_task.done():
            return  # follow will stop the others itself
        self._exclusive_task = self.hass.async_create_task(
            self._async_stop_others(self._linked_entity_id)
        )

    # ---- auto power off --------------------------------------------------
    @callback
    def _update_auto_off(self) -> None:
        """Run the idle timer while the amp is on and nothing is playing."""
        if not self._auto_off:
            return
        idle = (
            self.available
            and self._attr_state == MediaPlayerState.ON
            and self.state != MediaPlayerState.PLAYING
        )
        if not idle:
            self._cancel_auto_off()
        elif self._auto_off_unsub is None:
            self._auto_off_unsub = async_call_later(
                self.hass, self._auto_off, self._async_auto_off
            )

    @callback
    def _cancel_auto_off(self) -> None:
        if self._auto_off_unsub is not None:
            self._auto_off_unsub()
            self._auto_off_unsub = None

    async def _async_auto_off(self, _now: datetime) -> None:
        self._auto_off_unsub = None
        if (
            self._attr_state == MediaPlayerState.ON
            and self.state != MediaPlayerState.PLAYING
        ):
            _LOGGER.info(
                "Nothing played for %s min, turning Rotel off", self._auto_off / 60
            )
            try:
                await self._client.send("power_off!")
            except ConnectionError as err:
                _LOGGER.warning("Auto power off failed: %s", err)

    def _apply(self, key: str, value: str) -> None:
        if key == "power":
            self._attr_state = (
                MediaPlayerState.ON if value == "on" else MediaPlayerState.OFF
            )
            if value == "on":
                self._power_on_event.set()
        elif key == "source":
            self._raw_source = value
            self._source_event.set()
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
        return {
            **self._extra,
            "address": self._host_info,
            "linked_player": self._linked_entity_id,
        }

    # ---- linked (proxied) media player ------------------------------------
    @property
    def _linked_entity_id(self) -> str | None:
        """Linked media_player of the currently selected input."""
        if self._raw_source is None:
            return None
        key = REPORTED_TO_SOURCE.get(self._raw_source)
        return self._players.get(key) if key else None

    @property
    def _linked(self) -> State | None:
        """State of the linked player if it is usable."""
        if self._attr_state != MediaPlayerState.ON:
            return None
        entity_id = self._linked_entity_id
        if entity_id is None or self.hass is None:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state

    def _linked_attr(self, name: str) -> Any:
        state = self._linked
        return state.attributes.get(name) if state else None

    @property
    def state(self) -> MediaPlayerState | None:
        """Amp power; while on, playback state of the linked player."""
        if self._attr_state != MediaPlayerState.ON:
            return self._attr_state
        linked = self._linked
        if linked is not None and linked.state in PROXY_STATES:
            return MediaPlayerState(linked.state)
        return MediaPlayerState.ON

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Own features + playback features of the linked player."""
        linked = self._linked
        if linked is None:
            return SUPPORTED_FEATURES
        child = MediaPlayerEntityFeature(
            int(linked.attributes.get(ATTR_SUPPORTED_FEATURES, 0))
        )
        return OWN_FEATURES | (child & PROXY_FEATURES)

    @property
    def entity_picture(self) -> str | None:
        """Artwork of the linked player (already proxied by HA)."""
        return self._linked_attr(ATTR_ENTITY_PICTURE)

    @property
    def media_image_url(self) -> str | None:
        """Artwork of the linked player."""
        return self._linked_attr(ATTR_ENTITY_PICTURE)

    async def _async_call_linked(
        self, service: str, data: dict[str, Any] | None = None
    ) -> bool:
        """Call a media_player service on the linked player. False if none."""
        linked = self._linked
        if linked is None:
            return False
        await self.hass.services.async_call(
            MP_DOMAIN,
            service,
            {**(data or {}), ATTR_ENTITY_ID: linked.entity_id},
            blocking=True,
            context=self._context,
        )
        return True

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media on the linked player."""
        data: dict[str, Any] = {
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
        }
        for key in (ATTR_MEDIA_ENQUEUE, ATTR_MEDIA_ANNOUNCE, ATTR_MEDIA_EXTRA):
            if (value := kwargs.get(key)) is not None:
                data[key] = value.value if hasattr(value, "value") else value
        if not await self._async_call_linked(SERVICE_PLAY_MEDIA, data):
            raise ServiceValidationError("No linked media player for current input")

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse media of the linked player."""
        linked = self._linked
        if linked is not None and (
            entity := self.hass.data[MP_DATA_COMPONENT].get_entity(linked.entity_id)
        ):
            return await entity.async_browse_media(media_content_type, media_content_id)
        raise HomeAssistantError("No linked media player for current input")

    async def async_media_seek(self, position: float) -> None:
        """Seek on the linked player."""
        await self._async_call_linked(
            SERVICE_MEDIA_SEEK, {ATTR_MEDIA_SEEK_POSITION: position}
        )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Shuffle on the linked player."""
        await self._async_call_linked(SERVICE_SHUFFLE_SET, {ATTR_MEDIA_SHUFFLE: shuffle})

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Repeat on the linked player."""
        await self._async_call_linked(SERVICE_REPEAT_SET, {ATTR_MEDIA_REPEAT: repeat})

    async def async_clear_playlist(self) -> None:
        """Clear playlist on the linked player."""
        await self._async_call_linked(SERVICE_CLEAR_PLAYLIST)


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

    # Transport: linked player of the current input if any, else the amp
    # itself (controls USB/Bluetooth/PC-USB playback).
    async def async_media_play(self) -> None:
        """Play."""
        if not await self._async_call_linked(SERVICE_MEDIA_PLAY):
            await self.async_send("play!")

    async def async_media_pause(self) -> None:
        """Pause."""
        if not await self._async_call_linked(SERVICE_MEDIA_PAUSE):
            await self.async_send("pause!")

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause."""
        if not await self._async_call_linked(SERVICE_MEDIA_PLAY_PAUSE):
            await super().async_media_play_pause()

    async def async_media_stop(self) -> None:
        """Stop."""
        if not await self._async_call_linked(SERVICE_MEDIA_STOP):
            await self.async_send("stop!")

    async def async_media_next_track(self) -> None:
        """Next track."""
        if not await self._async_call_linked(SERVICE_MEDIA_NEXT_TRACK):
            await self.async_send("trkf!")

    async def async_media_previous_track(self) -> None:
        """Previous track."""
        if not await self._async_call_linked(SERVICE_MEDIA_PREVIOUS_TRACK):
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



def _proxy_property(attr: str) -> property:
    """Property that returns an attribute of the linked player."""
    return property(lambda self: self._linked_attr(attr))


# media metadata (title, artist, position, ...) comes from the linked player
for _name, _attr in PROXY_ATTRS.items():
    setattr(RotelMediaPlayer, _name, _proxy_property(_attr))
