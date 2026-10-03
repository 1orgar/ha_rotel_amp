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
CONF_MAX_VOLUME: Final = "max_volume"
CONF_POLL_INTERVAL: Final = "poll_interval"

DEFAULT_POLL_INTERVAL: Final = 30  # seconds, 0 = disabled
FULL_REFRESH_EVERY: Final = 10  # every Nth poll re-queries everything

# Prefix of dynamic per-source name fields in the flows ("name_coax2" ...)
SOURCE_NAME_PREFIX: Final = "name_"
# Prefix of dynamic per-source linked media player fields ("player_coax2" ...)
SOURCE_PLAYER_PREFIX: Final = "player_"

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
POLL_QUERIES: Final = ("power?", "volume?", "mute?", "source?")

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
