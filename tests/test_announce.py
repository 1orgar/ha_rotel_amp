"""Announcements (TTS) through the announce input."""
from __future__ import annotations

import asyncio

from homeassistant import config_entries
from homeassistant.components.media_player import (
    DATA_COMPONENT,
    MediaPlayerEntityFeature as F,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rotel_amp.const import DOMAIN

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


async def test_config_flow_new_options(hass: HomeAssistant, fake_rotel) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "127.0.0.1", "port": fake_rotel.port, "name": "R"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sources": ["coax1"], "max_volume": 60, "poll_interval": 0, "auto_off": 0},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name_coax1": "Алиса", "announce_source": "coax1"}
    )
    assert result["errors"] == {"announce_source": "announce_needs_player"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name_coax1": "Алиса",
            "player_coax1": ALICE,
            "refvol_coax1": 20,
            "keepon_coax1": True,
            "announce_source": "coax1",
            "announce_volume": 40,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    opts = result["options"]
    assert opts["source_ref_volume"] == {"coax1": 20}
    assert opts["source_keep_on"] == ["coax1"]
    assert opts["announce_source"] == "coax1"
    assert opts["announce_volume"] == 40
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(entry.entry_id)
