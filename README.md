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
- **Volume scale up to your limit:** 100 % in Home Assistant = the configured maximum volume on the amplifier.
- **Volume matching between inputs:** quiet and loud sources sound equally loud after a switch.
- **Automatic reconnect:** after the amplifier reboots or loses power, the integration reconnects by itself, so you don't need to restart Home Assistant.
- **Always up-to-date state:**
  - full state is requested on every connect/reconnect;
  - power, volume, mute and input are polled every N seconds (default 30); every 10th poll requests the full state;
  - full state is re-requested when the amplifier wakes from standby.
- **Linked media player per input** (replaces a `universal` media player setup, see below).
- **Follow playback:** when a linked player starts playing, the amplifier turns on, switches to its input and pauses the other players.
- **Auto power off** after N minutes without playback; digital inputs count as playing while they carry a signal.
- **Fixed 100 % volume** on linked players (volume is controlled on the amplifier).
- **Announcements (TTS)** through a chosen input, with the previous input, volume and power state restored afterwards.
- **Tone, balance, speakers A/B, tone bypass and dimmer** as entities on the device page.
- **Device info sensors** (model, firmware, IP, MAC, connection state) and a **Test connection** button.
- **Change the IP address** without re-adding the integration; renamed linked players are picked up automatically, removed ones raise a repair issue.
- Changes made on the front panel or remote arrive instantly (push).

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
2. Inputs you use, maximum volume, poll interval (`0` disables polling), auto power off (`0` disables it).
3. For each input:
   - name;
   - optional linked media player, with the "switch to this input" and "keep volume at 100 %" options;
   - relative volume and "never auto power off".

   Plus the input and volume used for announcements.

You can change all of this later with **Configure**. To change the IP address or port, use **⋮ → Reconfigure**. Inputs, links and entity IDs are kept.

## Volume
The Home Assistant volume slider covers **0…maximum volume** of the amplifier. With a maximum of 60, 100 % in HA is 60 on the amplifier display, 50 % is 30, and one volume step is one amplifier step. If the volume is raised above the limit on the front panel or remote, it is pulled back to the limit. The `amp_volume` attribute shows the raw amplifier value.

> Upgrading from 3.x: there the scale was fixed at 0…100, so automations that set `volume_level` now give a louder result whenever the maximum is below 100.

### Volume matching between inputs
Sources have different output levels. For example, the streamer at 40 sounds as loud as the Yandex station at 20. Set this **relative volume** for each input (`0` = not used). When you switch between two inputs that both have a value, the volume is scaled by their ratio:

| Relative volume | Before the switch | After the switch |
|---|---|---|
| Player 40, Alice 20 | Player at 30 | Alice at 15 |
| | Alice at 15 | Player at 30 |

When the new input is quieter, the volume is lowered before switching, so nothing gets loud for a moment. When it is louder, the volume is raised after switching. The result never exceeds the maximum volume. The volume is not touched when the amplifier is muted, or when one of the two inputs has no relative volume. This works for switches from Home Assistant and for automatic "switch to this input". It does not apply to switches from the remote or front panel.

## Linked media players
Each input can be linked to another `media_player` entity, such as a streamer, a smart speaker or a Chromecast connected to that input. While that input is selected and the amplifier is on, the Rotel entity acts as a single combined player:

| | comes from |
|---|---|
| power, volume, mute, input list / selection | **amplifier** |
| state (`playing` / `paused` / `idle`), title, artist, album, artwork, position, app | **linked player** |
| play / pause / stop / next / previous / seek / shuffle / repeat / play media / browse media | sent to the **linked player** |

The available controls follow what the linked player supports. If the current input has no linked player, or that player is unavailable, the entity is a plain amplifier: its state is `on`, and transport commands go to the amplifier itself (USB/Bluetooth playback). The `linked_player` attribute shows which player is active.

This replaces a manual `universal` media player setup like:

```yaml
media_player:
  - platform: universal
    children: [media_player.gostinaia, media_player.yandex_station_xxx]
    active_child_template: >-
      {% if is_state_attr('media_player.rotel_amplifier', 'source', 'Alice') %} ...
    commands: { select_source: ..., turn_on: ..., turn_off: ... }
    attributes: { volume_level: media_player.rotel_amplifier|volume_level, ... }
```

With this integration you only link *Alice → media_player.yandex_station_xxx* and *Player → media_player.gostinaia* in **Configure**.

### Switch to the input when its player starts playing
Each linked player has a **"switch to this input when the player starts playing"** option. When that player starts playing (its state changes to `playing`):

1. Every other linked player that is currently playing is paused right away (or stopped if it can't pause).
2. If the amplifier is off, it is turned on. The input is switched as soon as the amplifier reports `power=on`, with a short 0.3 s settle and no fixed delay.
3. The amplifier switches to this player's input. If the amplifier ignores the command (this can happen right after boot), it is resent every second, up to 4 times. If the amplifier is already on, the switch is immediate.

For example, you start music on the Yandex station: the amplifier wakes up and switches to *Alice*. Later you start a stream on the other player: the amplifier switches to *Player* and the station is paused.

**No ping-pong.** If another player with this option starts within 5 s after an automatic switch, the amplifier stays on the first one and the newcomer is paused. Every automatic switch is written to the **logbook** and fires a `rotel_amp_source_switched` event (`source`, `previous_source`, `reason`) that you can use in automations.

**Only one player at a time.** When at least one input has this option enabled, only the linked player of the current input is allowed to play. If several linked players are playing, the others are paused. This is checked whenever the input changes (including from the remote or front panel), when the amplifier turns on, and when a player without the option starts playing.

### Fixed 100 % volume
Each linked player also has a **"keep the player volume at 100 %"** option. Volume is controlled on the amplifier, so the player should always output full level. When enabled, the integration sets the player to 100 % and unmutes it. This happens at startup and every time the player's state changes, so if someone lowers the volume on the player itself, it is restored immediately. Players that are off or unavailable are left alone.

### Announcements (TTS)
Choose an **input for announcements**, for example the Yandex station, and optionally an **announcement volume** in % of the scale (`0` = don't change). When Home Assistant sends an announcement to the Rotel entity (`media_player.play_media` with `announce: true`, which is what TTS and Assist use):

1. The amplifier is turned on if needed and switched to the announcement input, and the announcement volume is set.
2. The announcement is played on the linked player of that input.
3. When the player finishes (or after 2 minutes at most), the previous input and volume are restored. If the amplifier was off, it is turned off again.

While an announcement is playing, "switch to this input", "only one player" and auto power off are paused.

### Renamed or removed players
If you rename a linked player's entity ID, the link is updated automatically. If a linked player is deleted, **Settings → Repairs** shows a warning listing the missing players. It disappears once you pick other players in **Configure**.

## Amplifier settings
On the device page, under *Configuration*:

| Entity | |
|---|---|
| Bass, Treble | −10…+10 |
| Balance | −15 (left)…+15 (right) |
| Speakers A, Speakers B | switches |
| Tone bypass | switch |
| Display dimmer | 0 (brightest)…6 |
| PC-USB audio class | 1 / 2 (disabled by default) |

They are unavailable while the amplifier is off. The `rotel_amp.*` actions below still work.

## Device information and connection test
The device gets diagnostic entities:

| Entity | |
|---|---|
| Model, Firmware, PC-USB firmware (disabled by default), IP address, MAC address | read from the amplifier on every connect; model/firmware/MAC also appear on the device page |
| Connection | `connected` / `disconnected` |
| Connected since, Reconnects, Last connection error, Last message (disabled by default) | connection diagnostics |
| Response time | latency of the last connection test, ms |
| **Test connection** button | sends `power?` and measures the reply time; an error is shown if the amplifier doesn't answer |

When you add the integration, the config flow also checks that the device actually answers Rotel commands, not just that the port is open.

## Auto power off
**Auto power off, min** (`0` disables it) turns the amplifier off after it has been on with nothing playing for the given time. The timer restarts every time playback stops, and is cancelled as soon as something plays or the amplifier is turned off.

What counts as "playing":

| Current input | Playing when |
|---|---|
| Has a linked player | the player is `playing` |
| Digital input (Coax, Optical, USB, Bluetooth, PC-USB) without a linked player | the amplifier reports a sample rate (a signal is present), e.g. the TV is on |
| Analog input (CD, Aux, Tuner, Phono, XLR) without a linked player | never, so enable **"never auto power off on this input"** for it |

The signal is queried 1.5 s after every input change and on every poll. The `signal` and `frequency` attributes show the current value.

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

Tone, balance and other values are also available as attributes of the media player.

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
