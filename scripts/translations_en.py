"""English texts (source of strings.json)."""

ADDRESS = {
    "data": {"host": "Host", "port": "Port", "name": "Name"},
    "data_description": {
        "host": "IP address or host name of the amplifier. Give it a fixed "
        "address (DHCP reservation) in your router.",
        "port": "TCP control port. Rotel uses 9590; change only if you know why.",
        "name": "Device name in Home Assistant, e.g. Living room amplifier.",
    },
}

GENERAL_DATA = {"sources": "Inputs in use"}
GENERAL_DESC = {
    "sources": "Only these inputs appear in the source list. Unused inputs are "
    "hidden; if one is selected on the front panel it is shown with its "
    "default name.",
}
GENERAL_SECTIONS = {
    "volume": {
        "name": "Volume",
        "data": {"max_volume": "Maximum volume"},
        "data_description": {
            "max_volume": "Amplifier level (1–96) that equals 100 % in Home "
            "Assistant. The slider covers 0…this value, and anything set above "
            "it on the remote or front panel is pulled back to it.",
        },
    },
    "power_volume": {
        "name": "Auto power off",
        "data": {"auto_off": "Auto power off after, min"},
        "data_description": {
            "auto_off": "Turn the amplifier off after it has been on with nothing "
            "playing for this many minutes. 0 = never. Playing means: the linked "
            "player of the current input is playing, or a digital input carries "
            "a signal. Analog inputs without a player never count as playing, so "
            "mark them \"Never auto power off\".",
        },
    },
    "advanced": {
        "name": "Advanced",
        "data": {"poll_interval": "Status poll interval, s"},
        "data_description": {
            "poll_interval": "The amplifier reports changes by itself; polling "
            "only catches missed updates and the signal on digital inputs. "
            "Default 30 s. 0 = off.",
        },
    },
}

INPUT = {
    "title": "Input {label}",
    "description": "Settings of the **{input}** input. Pick a linked media player "
    "and press Submit to see its options.",
    "data": {"name": "Name", "player": "Linked media player"},
    "data_description": {
        "name": "Shown in the source list instead of \"{input}\", e.g. Streamer, TV.",
        "player": "The media player connected to this input (streamer, smart "
        "speaker, Chromecast…). While this input is selected the amplifier "
        "entity shows its track, artwork and state, and play / pause / next / "
        "seek / browse go to it. Power, volume and input stay on the amplifier. "
        "Leave empty if nothing controllable is connected.",
    },
    "sections": {
        "player_options": {
            "name": "Linked player",
            "data": {
                "follow": "Switch to this input when the player starts playing",
                "fixed_volume": "Keep the player volume at 100 %",
            },
            "data_description": {
                "follow": "When the player starts playing, the amplifier turns "
                "on if needed, selects this input and pauses the other linked "
                "players. With this option on any input, only the current "
                "input's player may play. A second player starting within 5 s "
                "of an automatic switch is paused instead (no ping-pong).",
                "fixed_volume": "Volume is controlled on the amplifier, so the "
                "player should always output full level. Its volume is set to "
                "100 % and unmuted at start-up and whenever someone changes it.",
            },
        },
        "power_volume": {
            "name": "Volume matching and power",
            "data": {
                "ref_volume": "Relative volume",
                "keep_on": "Never auto power off on this input",
            },
            "data_description": {
                "ref_volume": "Amplifier level at which this input sounds as loud "
                "as your other inputs, e.g. Streamer 40, Yandex station 20. When "
                "switching between two inputs that both have a value, the volume "
                "is scaled by their ratio (Streamer at 30 → station at 15). "
                "0 = don't adjust.",
                "keep_on": "Auto power off never triggers while this input is "
                "selected. Use it for turntables, CD players and other analog "
                "sources the integration cannot see playing.",
            },
        },
    },
}

ANNOUNCE = {
    "title": "Announcements (TTS)",
    "description": "Text-to-speech and Assist can speak through the amplifier. "
    "It switches to the chosen input, the linked player speaks, then the "
    "previous input, volume and power state are restored.",
    "data": {
        "announce_source": "Input for announcements",
        "announce_volume": "Announcement volume",
    },
    "data_description": {
        "announce_source": "Only inputs with a linked player can be chosen. "
        "— = announcements are not supported.",
        "announce_volume": "In % of the volume scale (100 % = maximum volume). "
        "0 = keep the current volume.",
    },
}

ERRORS = {
    "cannot_connect": "Failed to connect to the amplifier. Check the address and "
    "that POWER OPTION is set to Quick.",
    "no_response": "The device is reachable but does not answer Rotel commands.",
    "unknown": "Unexpected error",
    "no_sources": "Select at least one input",
    "duplicate_name": "Another input already has this name",
    "self_player": "Cannot link the amplifier to itself",
}

MENU = {
    "title": "Rotel settings",
    "description": "{summary}{unsaved}Choose what to change, then **Save**.",
    "menu_options": {
        "general": "Inputs, volume and auto power off",
        "inputs": "Configure an input",
        "announce": "Announcements (TTS)",
        "save": "Save",
    },
    "menu_option_descriptions": {
        "general": "Which inputs are used, maximum volume, auto power off, polling",
        "inputs": "Name, linked player, auto switching, fixed and relative volume",
        "announce": "Input and volume for text-to-speech",
        "save": "Apply the changes (the integration reloads)",
    },
}

OVERVIEW = {
    "title": "Check and finish",
    "description": "{summary}\n\nEverything can also be changed later via "
    "**Configure**.",
    "menu_options": {
        "finish": "Finish setup",
        "edit_input": "Change an input",
        "announce": "Announcements (TTS)",
        "sources": "Back to inputs and general settings",
    },
    "menu_option_descriptions": {
        "finish": "Create the integration with these settings",
        "edit_input": "Name, linked player, auto switching, fixed and relative "
        "volume",
        "announce": "Input and volume for text-to-speech",
        "sources": "Add or remove inputs, maximum volume, auto power off",
    },
}

TEXT = {
    "user_title": "Rotel amplifier",
    "user_desc": "Set **POWER OPTION = Quick** on the amplifier so it stays "
    "reachable over the network in standby.",
    "sources_title": "Inputs and general settings",
    "sources_desc": "Next you will set up each selected input, then see an "
    "overview where you can go back to any step.",
    "reconfigure_title": "Change amplifier address",
    "reconfigure_desc": "New IP address or port. Inputs, links and entity IDs "
    "are kept.",
    "already_configured": "This amplifier is already configured",
    "reconfigure_successful": "Address updated",
    "inputs_title": "Configure an input",
    "inputs_desc": "auto = switch on playback · 100 % = fixed player volume · "
    "≈N = relative volume · ⏻ = never auto power off",
    "inputs_field": "Input",
    "issue_title": "Linked media player not found",
    "issue_desc": "{title}: these linked media players no longer exist: "
    "{players}. Open the integration → Configure → Configure an input and pick "
    "another player or clear the field.",
}

ENTITIES = {
    "sensor": {
        "model": "Model",
        "firmware": "Firmware",
        "pc_usb_firmware": "PC-USB firmware",
        "ip_address": "IP address",
        "mac_address": "MAC address",
        "latency": "Response time",
        "connection": "Connection",
        "connected_since": "Connected since",
        "last_message": "Last message",
        "reconnects": "Reconnects",
        "last_error": "Last connection error",
    },
    "button": {"test_connection": "Test connection"},
    "number": {"bass": "Bass", "treble": "Treble", "balance": "Balance"},
    "switch": {
        "speaker_a": "Speakers A",
        "speaker_b": "Speakers B",
        "bypass": "Tone bypass",
    },
    "select": {"dimmer": "Display dimmer", "pcusb_class": "PC-USB audio class"},
}
CONNECTION_STATES = {"connected": "Connected", "disconnected": "Disconnected"}

from translations_common import build  # noqa: E402

STRINGS = build(globals())
