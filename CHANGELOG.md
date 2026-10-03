# Changelog

## 4.0.0
**Breaking:** the volume scale changed. 0…100 % in Home Assistant now maps to 0…`max_volume` on the amplifier (it used to be 0…100). Automations that set `volume_level` give a louder result when the maximum is below 100. The raw amplifier value is in the new `amp_volume` attribute.

- Volume matching between inputs: a per-input relative volume; on a switch the volume is scaled by the ratio (lowered before the switch, raised after it, capped by the maximum).
- Signal detection on digital inputs (`freq?`): an input with signal counts as playing for auto power off. New per-input option "never auto power off on this input". New `signal` attribute.
- Volume set above the limit on the front panel or remote is pulled back to the limit.
- Tone, balance, speakers A/B, tone bypass, dimmer and PC-USB class as number / switch / select entities.
- Reconfigure flow: change host/port while keeping inputs, links and entity IDs.
- Announcements (TTS): an announcement input and volume; the previous input, volume and power state are restored afterwards.
- Follow playback cooldown (5 s) against ping-pong between players; logbook entries and a `rotel_amp_source_switched` event for automatic switches.
- Repair issue for linked players that no longer exist; renamed linked players are updated automatically.

## 3.4.0
- Per linked player "keep volume at 100 %": volume is restored and the player unmuted whenever it changes.
- Faster follow playback: input is switched as soon as the amp reports power on (0.3 s settle instead of 1 s + up to 20 s), unconfirmed input commands are retried every second; other players are paused immediately and in parallel.
- Only the current input's linked player may play: others are paused when the input changes, the amp turns on, or another player starts.
- Diagnostic sensors: model, firmware, PC-USB firmware, IP, MAC, connection, connected since, reconnects, last error, last message, response time. Model/firmware/MAC are added to the device.
- "Test connection" button; config flow checks that the device answers Rotel commands.

## 3.3.0
- Per linked player "switch to this input when the player starts playing": turns the amp on, selects the input and pauses the other playing linked players.
- Auto power off after N minutes on with nothing playing.

## 3.2.0
- Linked media player per input: while the input is selected, the amp entity shows the linked player's state, metadata and artwork and forwards transport, seek, play media and browse to it. Volume, power and input stay on the amp.
- Opaque brand images (readable on dark theme), new icon.

## 3.1.0
- Periodic status polling (power/volume/mute/source, full refresh every 10th poll), configurable interval.
- Full state refresh when the amp wakes from standby.
- Brand images, HACS/hassfest validation, automatic tag & release.

## 3.0.0
- Rewrite for modern Home Assistant: config flow + options flow, domain `rotel_amp`.
- Select used inputs and rename them.
- Single persistent connection with automatic reconnect, heartbeat and TCP keepalive.
- Entity becomes unavailable while disconnected; state is push-based.

## 2.0.0 and earlier
See [k4Mr3/Rotel-RA-1572](https://github.com/k4Mr3/Rotel-RA-1572).
