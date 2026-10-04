"""Announcements (TTS) through the announce input."""
from __future__ import annotations

import asyncio

from homeassistant.components.media_player import (
    DATA_COMPONENT,
    MediaPlayerEntityFeature as F,
)
from homeassistant.core import HomeAssistant, ServiceCall

from .helpers import ENTITY, wait_for
from .test_reconfigure_repairs import ALICE, FEATS, linked_entry


def _speaking_player(hass: HomeAssistant, seconds: float):
    """Stand-in play_media: the player 'speaks' for a while, then goes idle."""

    async def _play(call: ServiceCall) -> None:
        hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
        await asyncio.sleep(seconds)
        hass.states.async_set(ALICE, "idle", {"supported_features": FEATS})

    hass.services.async_register("media_player", "play_media", _play)


async def _announce(hass: HomeAssistant) -> None:
    # media_player.play_media is replaced by the stand-in above, so call the
    # Rotel entity directly (the way the media_player service would).
    entity = hass.data[DATA_COMPONENT].get_entity(ENTITY)
    await entity.async_play_media("music", "tts://hello", announce=True)


async def test_announce_switches_and_restores(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="on", source="opt1", volume="30")
    hass.states.async_set(ALICE, "idle", {"supported_features": FEATS})
    entry = linked_entry(
        fake_rotel.port, source_follow=[], announce_source="coax1", announce_volume=50
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    feats = F(hass.states.get(ENTITY).attributes["supported_features"])
    assert F.MEDIA_ANNOUNCE in feats

    _speaking_player(hass, 0.3)
    task = hass.async_create_task(_announce(hass))
    await wait_for(lambda: "coax1!" in fake_rotel.received)
    await wait_for(lambda: "vol_40!" in fake_rotel.received)  # 50 % of max 80
    await task
    await wait_for(lambda: hass.states.get(ENTITY).attributes["source"] == "ТВ")
    assert hass.states.get(ENTITY).attributes["amp_volume"] == 30
    await hass.config_entries.async_unload(entry.entry_id)


async def test_announce_when_amp_off_turns_it_back_off(
    hass: HomeAssistant, fake_rotel
) -> None:
    fake_rotel.state.update(power="standby", source="opt1")
    hass.states.async_set(ALICE, "idle", {"supported_features": FEATS})
    entry = linked_entry(fake_rotel.port, source_follow=[], announce_source="coax1")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "off")

    _speaking_player(hass, 0.2)
    await _announce(hass)
    assert "power_on!" in fake_rotel.received
    await wait_for(lambda: hass.states.get(ENTITY).state == "off")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_announce_does_not_trigger_follow(hass: HomeAssistant, fake_rotel) -> None:
    """Alice has follow enabled, but a TTS must not leave the amp on her input."""
    fake_rotel.state.update(power="on", source="opt1")
    hass.states.async_set(ALICE, "idle", {"supported_features": FEATS})
    hass.states.async_set("media_player.player", "idle", {"supported_features": FEATS})
    entry = linked_entry(fake_rotel.port, announce_source="coax1")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    _speaking_player(hass, 0.2)
    await _announce(hass)
    await wait_for(lambda: hass.states.get(ENTITY).attributes["source"] == "ТВ")
    await asyncio.sleep(0.5)
    assert hass.states.get(ENTITY).attributes["source"] == "ТВ"
    await hass.config_entries.async_unload(entry.entry_id)
