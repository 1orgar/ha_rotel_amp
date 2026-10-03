# Changelog

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
