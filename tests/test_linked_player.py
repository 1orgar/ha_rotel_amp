"""Linked (proxied) media player per input."""
from __future__ import annotations

from homeassistant.components.media_player import (
    DATA_COMPONENT,
    MediaPlayerEntityFeature as F,
)
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, wait_for

CHILD = "media_player.streamer"
CHILD_FEATURES = int(F.PLAY | F.PAUSE | F.NEXT_TRACK | F.SEEK | F.PLAY_MEDIA)


def _entry(port: int) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"127.0.0.1:{port}",
        title="Rotel",
        data={"host": "127.0.0.1", "port": port, "name": "Rotel"},
        options={
            "sources": ["coax2", "opt1"],
            "source_names": {"coax2": "Стример", "opt1": "ТВ"},
            "source_players": {"coax2": CHILD},
            "max_volume": 50,
            "poll_interval": 0,
        },
    )


async def _setup(hass: HomeAssistant, port: int):
    entry = _entry(port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "playing")
    return entry, hass.data[DATA_COMPONENT].get_entity(ENTITY)


async def test_state_and_metadata_from_linked_player(
    hass: HomeAssistant, fake_rotel
) -> None:
    hass.states.async_set(
        CHILD,
        "playing",
        {
            "supported_features": CHILD_FEATURES,
            "media_title": "Song",
            "media_artist": "Artist",
            "entity_picture": "/api/media_player_proxy/x",
        },
    )
    entry, _ = await _setup(hass, fake_rotel.port)

    st = hass.states.get(ENTITY)
    assert st.attributes["source"] == "Стример"
    assert st.attributes["media_title"] == "Song"
    assert st.attributes["media_artist"] == "Artist"
    assert st.attributes["entity_picture"] == "/api/media_player_proxy/x"
    assert st.attributes["amp_volume"] == 30  # volume always from the amp
    assert st.attributes["linked_player"] == CHILD
    feats = F(st.attributes["supported_features"])
    assert {F.SEEK, F.PLAY_MEDIA, F.SELECT_SOURCE, F.VOLUME_SET} <= set(feats)
    assert F.STOP not in feats  # the child does not support it

    hass.states.async_set(CHILD, "paused", {"supported_features": CHILD_FEATURES})
    await wait_for(lambda: hass.states.get(ENTITY).state == "paused")

    # child unavailable -> just "on" with the amp's own features
    hass.states.async_set(CHILD, "unavailable", {})
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_amp_off_hides_linked_player(hass: HomeAssistant, fake_rotel) -> None:
    hass.states.async_set(CHILD, "playing", {"media_title": "Song"})
    entry, _ = await _setup(hass, fake_rotel.port)
    await fake_rotel.push("power=standby$")
    await wait_for(lambda: hass.states.get(ENTITY).state == "off")
    assert "media_title" not in hass.states.get(ENTITY).attributes
    await hass.config_entries.async_unload(entry.entry_id)


async def test_transport_routing(hass: HomeAssistant, fake_rotel) -> None:
    calls: list[tuple[str, dict]] = []

    async def _record(call: ServiceCall) -> None:
        calls.append((call.service, dict(call.data)))

    hass.states.async_set(CHILD, "playing", {"supported_features": CHILD_FEATURES})
    entry, ent = await _setup(hass, fake_rotel.port)
    # stand-ins for the child integration's services (after media_player loaded)
    for svc in ("media_pause", "media_next_track", "media_seek", "play_media"):
        hass.services.async_register("media_player", svc, _record)

    await ent.async_media_pause()
    await ent.async_media_next_track()
    await ent.async_media_seek(42)
    await ent.async_play_media("music", "spotify:track:1")
    assert calls == [
        ("media_pause", {"entity_id": CHILD}),
        ("media_next_track", {"entity_id": CHILD}),
        ("media_seek", {"seek_position": 42, "entity_id": CHILD}),
        (
            "play_media",
            {
                "media_content_type": "music",
                "media_content_id": "spotify:track:1",
                "entity_id": CHILD,
            },
        ),
    ]
    assert not {"pause!", "trkf!"} & set(fake_rotel.received)

    # input without a linked player -> transport goes to the amp itself
    await ent.async_select_source("ТВ")
    await wait_for(lambda: hass.states.get(ENTITY).attributes["source"] == "ТВ")
    assert hass.states.get(ENTITY).state == "on"
    assert hass.states.get(ENTITY).attributes["linked_player"] is None
    await ent.async_media_pause()
    await wait_for(lambda: "pause!" in fake_rotel.received)
    await hass.config_entries.async_unload(entry.entry_id)
