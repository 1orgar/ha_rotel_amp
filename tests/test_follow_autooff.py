"""Follow-playback and auto power off."""
from __future__ import annotations

import asyncio

from homeassistant.components.media_player import MediaPlayerEntityFeature as F
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, wait_for

ALICE = "media_player.alice"
PLAYER = "media_player.player"
FEATS = int(F.PLAY | F.PAUSE | F.STOP)


def _entry(port: int, **options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"127.0.0.1:{port}",
        title="Rotel",
        data={"host": "127.0.0.1", "port": port, "name": "Rotel"},
        options={
            "sources": ["coax1", "coax2", "opt1"],
            "source_names": {"coax1": "Алиса", "coax2": "Плеер", "opt1": "ТВ"},
            "source_players": {"coax1": ALICE, "coax2": PLAYER},
            "source_follow": ["coax1", "coax2"],
            "max_volume": 50,
            "poll_interval": 0,
            "auto_off": 0,
            **options,
        },
    )


async def _setup(hass: HomeAssistant, amp, **options):
    entry = _entry(amp.port, **options)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state not in ("unavailable", "unknown"))
    return entry


def _record_services(hass: HomeAssistant) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    async def _rec(call: ServiceCall) -> None:
        calls.append((call.service, call.data["entity_id"]))
        hass.states.async_set(call.data["entity_id"], "paused", {"supported_features": FEATS})

    for svc in ("media_pause", "media_stop"):
        hass.services.async_register("media_player", svc, _rec)
    return calls


async def test_player_start_turns_amp_on_and_selects_input(
    hass: HomeAssistant, fake_rotel
) -> None:
    fake_rotel.state.update(power="standby", source="opt1")
    hass.states.async_set(ALICE, "idle", {"supported_features": FEATS})
    entry = await _setup(hass, fake_rotel)
    assert hass.states.get(ENTITY).state == "off"

    hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
    await wait_for(lambda: "power_on!" in fake_rotel.received)
    await fake_rotel.push("power=on$")
    fake_rotel.state["power"] = "on"
    await wait_for(lambda: "coax1!" in fake_rotel.received)
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("source") == "Алиса")
    assert hass.states.get(ENTITY).state == "playing"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_second_player_takes_over(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="on", source="coax1")
    hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
    hass.states.async_set(PLAYER, "idle", {"supported_features": FEATS})
    entry = await _setup(hass, fake_rotel)
    calls = _record_services(hass)
    await wait_for(lambda: hass.states.get(ENTITY).state == "playing")

    hass.states.async_set(PLAYER, "playing", {"supported_features": FEATS})
    await wait_for(lambda: "coax2!" in fake_rotel.received)
    await wait_for(lambda: calls == [("media_pause", ALICE)])
    assert "power_on!" not in fake_rotel.received
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("source") == "Плеер")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_no_follow_option_does_nothing(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="standby")
    hass.states.async_set(ALICE, "idle", {})
    entry = await _setup(hass, fake_rotel, source_follow=[])
    hass.states.async_set(ALICE, "playing", {})
    await hass.async_block_till_done()
    await wait_for(lambda: hass.states.get(ENTITY).state == "off")
    assert "power_on!" not in fake_rotel.received
    await hass.config_entries.async_unload(entry.entry_id)


async def test_auto_off_when_idle(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="on", source="coax1")
    hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
    entry = await _setup(hass, fake_rotel, auto_off=0.01)  # 0.6 s
    await wait_for(lambda: hass.states.get(ENTITY).state == "playing")
    # playing -> timer must not fire
    await asyncio.sleep(1.0)
    assert "power_off!" not in fake_rotel.received

    # player paused -> amp idle -> auto off after the delay
    hass.states.async_set(ALICE, "paused", {"supported_features": FEATS})
    await wait_for(lambda: "power_off!" in fake_rotel.received, timeout=5)

    # playback resumes before the timer -> no power off
    fake_rotel.received.clear()
    hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
    await asyncio.sleep(1.0)
    assert "power_off!" not in fake_rotel.received
    await hass.config_entries.async_unload(entry.entry_id)


async def test_auto_off_cancelled_by_playback(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="on", source="coax1")
    hass.states.async_set(ALICE, "paused", {"supported_features": FEATS})
    entry = await _setup(hass, fake_rotel, auto_off=0.02)  # 1.2 s
    await wait_for(lambda: hass.states.get(ENTITY).state == "paused")
    await asyncio.sleep(0.5)
    hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
    await asyncio.sleep(1.0)
    assert "power_off!" not in fake_rotel.received
    await hass.config_entries.async_unload(entry.entry_id)
