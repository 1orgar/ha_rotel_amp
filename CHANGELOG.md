# Changelog

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
