<p align="center">
  <img src="https://raw.githubusercontent.com/1orgar/ha_rotel_amp/main/brand/logo@2x.png" alt="Rotel Amp" height="96">
</p>

# Rotel Amplifier (TCP) for Home Assistant

🇷🇺 [Русская версия](https://github.com/1orgar/ha_rotel_amp/blob/main/README-RU.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/1orgar/ha_rotel_amp/actions/workflows/validate.yml/badge.svg)](https://github.com/1orgar/ha_rotel_amp/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/1orgar/ha_rotel_amp)](https://github.com/1orgar/ha_rotel_amp/releases)
[![License](https://img.shields.io/github/license/1orgar/ha_rotel_amp)](https://github.com/1orgar/ha_rotel_amp/blob/main/LICENSE)

Local network control of Rotel amplifiers (RA-1572, RA-1572MKII and other models using the same TCP protocol) on port 9590.
Based on [k4Mr3/Rotel-RA-1572](https://github.com/k4Mr3/Rotel-RA-1572), rewritten for modern Home Assistant.

## Features
- **UI setup** (config flow), no YAML needed.
- **Only the inputs you use.** Select your inputs and only those appear in the source list.
- **Custom input names**, e.g. `Coax 2` → `Streamer`. Change them any time via **Configure**.
- **Maximum volume limit.**
- **Automatic reconnect:** after the amplifier reboots or loses power, the integration reconnects by itself, so you don't need to restart Home Assistant.
- **Always up-to-date state:**
  - full state is requested on every connect/reconnect;
  - power, volume, mute and input are polled every N seconds (default 30); every 10th poll requests the full state;
  - full state is re-requested when the amplifier wakes from standby.
- Changes made on the front panel or remote arrive instantly (push).
- Actions for tone, balance, speakers A/B, dimmer, tone bypass and PC-USB class.

## Installation

### HACS
1. HACS → ⋮ → *Custom repositories* → `https://github.com/1orgar/ha_rotel_amp`, type *Integration*.
2. Find **Rotel Amplifier (TCP)**, install it and restart Home Assistant.

### Manual
Copy `custom_components/rotel_amp` to `<config>/custom_components/` and restart Home Assistant.

## Configuration
Set **POWER OPTION = Quick** on the amplifier, otherwise it is not reachable over the network in standby.

*Settings → Devices & services → Add integration → Rotel Amplifier (TCP)*:

1. Host, port (default `9590`), name.
2. Inputs you use, maximum volume, poll interval (`0` disables polling).
3. Input names.

You can change inputs, names, the volume limit and the poll interval later with **Configure**.

## Actions
| Action | Parameters |
|---|---|
| `rotel_amp.set_bass` / `set_treble` | `level` −10…10 |
| `rotel_amp.set_balance` | `level` −15…15 (negative = left) |
| `rotel_amp.set_dimmer` | `level` 0…6 |
| `rotel_amp.set_bypass` | `bypass` |
| `rotel_amp.set_speaker_a` / `set_speaker_b` | `enabled` |
| `rotel_amp.set_pcusb_class` | `usb_class` `1` / `2` |
| `rotel_amp.toggle_speaker_a/b`, `toggle_dimmer`, `bass_up/down`, `treble_up/down`, `balance_left/right` | — |
| `rotel_amp.get_current_status` | — (force a full state refresh) |

Tone, balance and other values are available as entity attributes.

## Debugging
```yaml
logger:
  logs:
    custom_components.rotel_amp: debug
```

## Development
```bash
pip install -r requirements_test.txt
ruff check custom_components tests
pytest
```
The tests run against an amplifier emulator and cover reboot, a silent amplifier, startup while the amplifier is offline, and polling.

### Releases
The version comes from `custom_components/rotel_amp/manifest.json`. When a new version is pushed to `main`, the **Tag & release** workflow creates the tag `v<version>` and a GitHub Release with `rotel_amp.zip`.

## License
Apache-2.0. Rotel is a trademark of its owner. This project is not affiliated with Rotel; the icon is a generic volume knob.
