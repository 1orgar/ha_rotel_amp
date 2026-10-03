"""Constants for the Rotel Amplifier integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "rotel_amp"

DEFAULT_NAME: Final = "Rotel Amplifier"
DEFAULT_PORT: Final = 9590
DEFAULT_MAX_VOLUME: Final = 96

CONF_SOURCES: Final = "sources"
CONF_SOURCE_NAMES: Final = "source_names"
CONF_SOURCE_PLAYERS: Final = "source_players"
CONF_SOURCE_FOLLOW: Final = "source_follow"  # inputs whose player triggers auto-switch
CONF_AUTO_OFF: Final = "auto_off"  # minutes, 0 = disabled

DEFAULT_AUTO_OFF: Final = 0
CONF_MAX_VOLUME: Final = "max_volume"
CONF_POLL_INTERVAL: Final = "poll_interval"

DEFAULT_POLL_INTERVAL: Final = 30  # seconds, 0 = disabled
FULL_REFRESH_EVERY: Final = 10  # every Nth poll re-queries everything

# Prefix of dynamic per-source name fields in the flows ("name_coax2" ...)
SOURCE_NAME_PREFIX: Final = "name_"
# Prefix of dynamic per-source linked media player fields ("player_coax2" ...)
SOURCE_PLAYER_PREFIX: Final = "player_"
# Prefix of per-source "follow playback" switches ("follow_coax2" ...)
SOURCE_FOLLOW_PREFIX: Final = "follow_"

# Prefix of per-source "keep linked player at 100 % volume" switches
SOURCE_FIXVOL_PREFIX: Final = "fixvol_"
CONF_SOURCE_FIXED_VOLUME: Final = "source_fixed_volume"

# Per-input "relative volume" for automatic volume matching on input change
SOURCE_REFVOL_PREFIX: Final = "refvol_"
CONF_SOURCE_REF_VOLUME: Final = "source_ref_volume"
# Per-input "never auto power off on this input"
SOURCE_KEEPON_PREFIX: Final = "keepon_"
CONF_SOURCE_KEEP_ON: Final = "source_keep_on"

# Announcements (TTS) sent to the amplifier entity
CONF_ANNOUNCE_SOURCE: Final = "announce_source"
CONF_ANNOUNCE_VOLUME: Final = "announce_volume"  # % of the volume scale, 0 = keep
ANNOUNCE_START_TIMEOUT: Final = 10.0  # wait for the player to start speaking
ANNOUNCE_MAX_DURATION: Final = 120.0
ANNOUNCE_RESTORE_DELAY: Final = 0.5

# Inputs where the amp reports the sample rate of an incoming signal (freq?)
DIGITAL_SOURCES: Final = frozenset(
    {"coax1", "coax2", "opt1", "opt2", "usb", "bluetooth", "pc_usb"}
)
NO_SIGNAL_VALUES: Final = frozenset({"", "off", "0", "none", "no_signal", "---"})

# Ignore follow triggers this soon after the previous automatic switch
FOLLOW_COOLDOWN: Final = 5.0
EVENT_SOURCE_SWITCHED: Final = "rotel_amp_source_switched"

# Follow playback timings
POWER_ON_TIMEOUT: Final = 8.0  # max wait for "power=on" after power_on!
POWER_ON_SETTLE: Final = 0.3  # amp may ignore the input command right after boot
SOURCE_CONFIRM_TIMEOUT: Final = 1.0  # wait for "source=..." before retrying
SOURCE_ATTEMPTS: Final = 4

PING_TIMEOUT: Final = 3.0

# Connection tuning
CONNECT_TIMEOUT: Final = 5.0
WRITE_TIMEOUT: Final = 3.0
HEARTBEAT_INTERVAL: Final = 15.0  # send power? if nothing was received for this long
STALE_TIMEOUT: Final = 40.0  # no data at all for this long -> reconnect
RECONNECT_MIN_DELAY: Final = 2.0
RECONNECT_MAX_DELAY: Final = 30.0

# source key -> (command sent to amp, values reported by amp, default name)
SOURCES: Final[dict[str, tuple[str, tuple[str, ...], str]]] = {
    "cd": ("cd!", ("cd", "analog_cd"), "CD"),
    "coax1": ("coax1!", ("coax1",), "Coax 1"),
    "coax2": ("coax2!", ("coax2",), "Coax 2"),
    "opt1": ("opt1!", ("opt1",), "Optical 1"),
    "opt2": ("opt2!", ("opt2",), "Optical 2"),
    "aux": ("aux!", ("aux",), "Aux"),
    "tuner": ("tuner!", ("tuner",), "Tuner"),
    "phono": ("phono!", ("phono",), "Phono"),
    "usb": ("usb!", ("usb",), "USB"),
    "bluetooth": ("bluetooth!", ("bluetooth",), "Bluetooth"),
    "bal_xlr": ("bal_xlr!", ("bal_xlr",), "XLR"),
    "pc_usb": ("pcusb!", ("pc_usb", "pcusb"), "PC USB"),
}

# reported value -> source key
REPORTED_TO_SOURCE: Final[dict[str, str]] = {
    reported: key for key, (_, values, _) in SOURCES.items() for reported in values
}

# queried on every poll
POLL_QUERIES: Final = ("power?", "volume?", "mute?", "source?", "freq?")
# re-check the incoming signal this long after an input change
SIGNAL_CHECK_DELAY: Final = 1.5

# device information, queried once per connection
DEVICE_QUERIES: Final = ("model?", "version?", "pc_version?", "ip?", "mac?")
# reply keys that are device information
DEVICE_INFO_KEYS: Final = ("model", "version", "pc_version", "ipaddress", "ip", "mac")

STATE_QUERIES: Final = (
    "power?",
    "source?",
    "volume?",
    "mute?",
    "bypass?",
    "bass?",
    "treble?",
    "balance?",
    "speaker?",
    "dimmer?",
    "pcusb?",
    "freq?",
)
