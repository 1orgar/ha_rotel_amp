"""Auto power off with unreliable linked players.

Timer 1.2 s (auto_off=0.02 min), grace for an unavailable player 0.6 s.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest

from .helpers import ENTITY, wait_for
from .test_follow_autooff import ALICE, FEATS, _setup

AUTO_OFF = 0.02  # minutes = 1.2 s
GRACE = 0.6


@pytest.fixture(autouse=True)
def short_grace():
    with patch(
        "custom_components.rotel_amp.media_player.PLAYER_UNAVAILABLE_GRACE", GRACE
    ):
        yield


def set_alice(hass: HomeAssistant, state: str) -> None:
    hass.states.async_set(ALICE, state, {"supported_features": FEATS})


def turned_off(amp) -> bool:
    return "power_off!" in amp.received


async def test_paused_unavailable_flapping_does_not_restart(
    hass: HomeAssistant, fake_rotel
) -> None:
    """paused <-> unavailable every 0.15 s: still turns off ~1.2 s after start."""
    fake_rotel.state.update(power="on", source="coax1", freq="48000")
    set_alice(hass, "paused")
    entry = await _setup(hass, fake_rotel, source_follow=[], auto_off=AUTO_OFF)
    loop = asyncio.get_running_loop()
    start = loop.time()
    while not turned_off(fake_rotel) and loop.time() - start < 4:
        set_alice(hass, "unavailable")
        await asyncio.sleep(0.15)
        set_alice(hass, "paused")
        await asyncio.sleep(0.15)
    assert turned_off(fake_rotel)
    assert loop.time() - start < 2.0
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unavailable_player_with_signal_is_not_playing(
    hass: HomeAssistant, fake_rotel
) -> None:
    """Streamer keeps the S/PDIF clock while paused: the signal must not count."""
    fake_rotel.state.update(power="on", source="coax1", freq="48000")
    set_alice(hass, "unavailable")
    entry = await _setup(hass, fake_rotel, source_follow=[], auto_off=AUTO_OFF)
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("signal") is True)
    await wait_for(lambda: turned_off(fake_rotel), timeout=4)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_short_unavailable_while_playing_is_ignored(
    hass: HomeAssistant, fake_rotel
) -> None:
    """playing -> unavailable (< grace) -> playing: no power off, no re-follow."""
    fake_rotel.state.update(power="on", source="coax1")
    set_alice(hass, "playing")
    entry = await _setup(hass, fake_rotel, source_follow=["coax1"], auto_off=AUTO_OFF)
    await wait_for(lambda: hass.states.get(ENTITY).state == "playing")
    for _ in range(5):
        set_alice(hass, "unavailable")
        await asyncio.sleep(0.3)
        set_alice(hass, "playing")
        await asyncio.sleep(0.3)
    assert not turned_off(fake_rotel)
    assert hass.states.get(ENTITY).attributes["auto_off_at"] is None
    # coming back from unavailable is not a new start of playback
    assert fake_rotel.received.count("coax1!") == 0
    await hass.config_entries.async_unload(entry.entry_id)


async def test_player_gone_while_playing_turns_off_after_grace(
    hass: HomeAssistant, fake_rotel
) -> None:
    """playing -> unavailable for good: grace period, then the countdown."""
    fake_rotel.state.update(power="on", source="coax1")
    set_alice(hass, "playing")
    entry = await _setup(hass, fake_rotel, source_follow=[], auto_off=AUTO_OFF)
    await wait_for(lambda: hass.states.get(ENTITY).state == "playing")
    loop = asyncio.get_running_loop()
    start = loop.time()
    set_alice(hass, "unavailable")
    await asyncio.sleep(GRACE - 0.2)
    assert hass.states.get(ENTITY).attributes["auto_off_at"] is None  # in grace
    await wait_for(lambda: turned_off(fake_rotel), timeout=5)
    assert GRACE + 1.0 < loop.time() - start < GRACE + 2.5
    await hass.config_entries.async_unload(entry.entry_id)


async def test_real_playback_resets_countdown(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="on", source="coax1")
    set_alice(hass, "paused")
    entry = await _setup(hass, fake_rotel, source_follow=[], auto_off=AUTO_OFF)
    await wait_for(lambda: hass.states.get(ENTITY).attributes["auto_off_at"] is not None)
    await asyncio.sleep(0.8)
    set_alice(hass, "playing")
    await wait_for(lambda: hass.states.get(ENTITY).attributes["auto_off_at"] is None)
    set_alice(hass, "paused")
    await asyncio.sleep(0.8)  # 1.6 s since setup, only 0.8 s since the pause
    assert not turned_off(fake_rotel)
    await wait_for(lambda: turned_off(fake_rotel), timeout=3)
    await hass.config_entries.async_unload(entry.entry_id)
