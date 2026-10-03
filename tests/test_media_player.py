"""Media player + reconnect tests."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.rotel_amp.client import parse_messages

from .helpers import ENTITY, make_entry, wait_for

FAST = (
    patch("custom_components.rotel_amp.client.RECONNECT_MIN_DELAY", 0.1),
    patch("custom_components.rotel_amp.client.RECONNECT_MAX_DELAY", 0.2),
)


def test_parse_messages() -> None:
    msgs, rest = parse_messages("power=on$volume=30$sou")
    assert msgs == [("power", "on"), ("volume", "30")]
    assert rest == "sou"


async def test_select_source_and_volume_limit(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    assert hass.states.get(ENTITY).attributes["source"] == "Стример"

    await hass.services.async_call(
        "media_player", "select_source",
        {"entity_id": ENTITY, "source": "ТВ"}, blocking=True,
    )
    await wait_for(lambda: "opt1!" in fake_rotel.received)
    await wait_for(lambda: hass.states.get(ENTITY).attributes["source"] == "ТВ")

    await hass.config_entries.async_unload(entry.entry_id)


def _amp(hass: HomeAssistant) -> int | None:
    return hass.states.get(ENTITY).attributes.get("amp_volume")


async def test_volume_scale_maps_to_max_volume(hass: HomeAssistant, fake_rotel) -> None:
    """HA 0..100 % = amp 0..max_volume (50 in the test entry)."""
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: _amp(hass) == 30)
    assert hass.states.get(ENTITY).attributes["volume_level"] == 0.6  # 30 / 50

    for level, expected in ((1.0, 50), (0.5, 25), (0.0, 0), (0.33, 16)):
        await hass.services.async_call(
            "media_player", "volume_set",
            {"entity_id": ENTITY, "volume_level": level}, blocking=True,
        )
        await wait_for(lambda e=expected: _amp(hass) == e)

    # set above the limit on the front panel -> pulled back to max_volume
    await fake_rotel.push("volume=70$")
    await wait_for(lambda: "vol_50!" in fake_rotel.received[-3:])
    assert hass.states.get(ENTITY).attributes["volume_level"] == 1.0
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reconnect_after_amp_reboot(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    with FAST[0], FAST[1]:
        await hass.config_entries.async_setup(entry.entry_id)
        await wait_for(lambda: hass.states.get(ENTITY).state == "on")

        fake_rotel.state["volume"] = "42"
        await fake_rotel.reboot()
        await wait_for(
            lambda: hass.states.get(ENTITY).state == "on" and _amp(hass) == 42
        )
        await hass.services.async_call(
            "media_player", "volume_set",
            {"entity_id": ENTITY, "volume_level": 0.2}, blocking=True,
        )
        await wait_for(lambda: _amp(hass) == 10)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_silent_amp_detected_as_dead(hass: HomeAssistant, fake_rotel) -> None:
    """Amp stops answering without closing TCP (power cut) -> reconnect."""
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    with FAST[0], FAST[1], patch(
        "custom_components.rotel_amp.client.HEARTBEAT_INTERVAL", 0.2
    ), patch("custom_components.rotel_amp.client.STALE_TIMEOUT", 0.5):
        await hass.config_entries.async_setup(entry.entry_id)
        await wait_for(lambda: hass.states.get(ENTITY).state == "on")
        fake_rotel.mute_replies = True
        await wait_for(lambda: hass.states.get(ENTITY).state == "unavailable")
        fake_rotel.mute_replies = False
        await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_periodic_poll_picks_up_missed_change(
    hass: HomeAssistant, fake_rotel
) -> None:
    """Volume changed on the amp without a push is picked up by polling."""
    entry = make_entry(fake_rotel.port, poll_interval=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: _amp(hass) == 30)
    fake_rotel.state["volume"] = "37"  # silent change, no push
    await wait_for(lambda: _amp(hass) == 37)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_full_refresh_on_wake_from_standby(
    hass: HomeAssistant, fake_rotel
) -> None:
    """power off -> on push triggers a full state re-query."""
    fake_rotel.state["power"] = "standby"
    entry = make_entry(fake_rotel.port, poll_interval=0)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "off")
    fake_rotel.state.update(power="on", volume="44")
    await fake_rotel.push("power=on$")
    await wait_for(
        lambda: hass.states.get(ENTITY).state == "on" and _amp(hass) == 44
    )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_while_amp_offline(hass: HomeAssistant, fake_rotel) -> None:
    await fake_rotel.stop()
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    with FAST[0], FAST[1]:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await wait_for(lambda: hass.states.get(ENTITY) is not None)
        assert hass.states.get(ENTITY).state == "unavailable"
        await fake_rotel.start()
        await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    await hass.config_entries.async_unload(entry.entry_id)
