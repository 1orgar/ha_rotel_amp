"""Reconfigure flow, repair issues, rename tracking, follow cooldown."""
from __future__ import annotations

import asyncio

from homeassistant.components.media_player import MediaPlayerEntityFeature as F
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rotel_amp.const import DOMAIN

from .conftest import FakeRotel
from .helpers import ENTITY, make_entry, wait_for

ALICE = "media_player.alice"
PLAYER = "media_player.player"
FEATS = int(F.PLAY | F.PAUSE | F.PLAY_MEDIA)


def linked_entry(port: int, **options) -> MockConfigEntry:
    """Entry with two linked players (Alice on coax1, Player on coax2)."""
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
            "max_volume": 80,
            "poll_interval": 0,
            **options,
        },
    )


async def test_reconfigure_changes_address(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")

    new_amp = FakeRotel()
    await new_amp.start()
    try:
        result = await entry.start_reconfigure_flow(hass)
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "127.0.0.1", "port": 1}
        )
        assert result["errors"] == {"base": "cannot_connect"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "127.0.0.1", "port": new_amp.port}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data["port"] == new_amp.port
        assert entry.options["source_names"] == {"coax2": "Стример", "opt1": "ТВ"}
        await wait_for(lambda: "power?" in new_amp.received)
        # same entity_id as before: automations keep working
        await wait_for(lambda: hass.states.get(ENTITY).state == "on")
        assert hass.states.get("media_player.rotel_2") is None

        # adding a new entry for the moved address is rejected
        from homeassistant import config_entries

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "127.0.0.1", "port": new_amp.port, "name": "Dup"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await new_amp.stop()


async def test_repair_issue_for_missing_player(hass: HomeAssistant, fake_rotel) -> None:
    hass.states.async_set(ALICE, "idle", {})  # PLAYER does not exist
    entry = linked_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    issue_id = f"missing_player_{entry.entry_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert PLAYER in issue.translation_placeholders["players"]

    # fixing the options removes the issue
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "source_players": {"coax1": ALICE}}
    )
    await hass.async_block_till_done()
    await wait_for(lambda: ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_linked_player_rename_is_followed(hass: HomeAssistant, fake_rotel) -> None:
    registry = er.async_get(hass)
    reg = registry.async_get_or_create(
        "media_player", "test", "alice", suggested_object_id="alice"
    )
    assert reg.entity_id == ALICE
    hass.states.async_set(PLAYER, "idle", {})
    entry = linked_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry.async_update_entity(ALICE, new_entity_id="media_player.yandex")
    await wait_for(
        lambda: entry.options["source_players"]["coax1"] == "media_player.yandex"
    )
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_follow_cooldown_prevents_ping_pong(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(power="on", source="opt1")
    hass.states.async_set(ALICE, "idle", {"supported_features": FEATS})
    hass.states.async_set(PLAYER, "idle", {"supported_features": FEATS})
    entry = linked_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")

    paused: list[str] = []

    async def _pause(call: ServiceCall) -> None:
        paused.append(call.data["entity_id"])
        hass.states.async_set(
            call.data["entity_id"], "paused", {"supported_features": FEATS}
        )

    hass.services.async_register("media_player", "media_pause", _pause)
    events = []
    hass.bus.async_listen("rotel_amp_source_switched", events.append)

    hass.states.async_set(ALICE, "playing", {"supported_features": FEATS})
    await wait_for(lambda: hass.states.get(ENTITY).attributes["source"] == "Алиса")
    # the other player starts right after -> the newcomer is paused instead
    await asyncio.sleep(0.2)
    hass.states.async_set(PLAYER, "playing", {"supported_features": FEATS})
    await wait_for(lambda: PLAYER in paused)
    await asyncio.sleep(0.5)
    assert "coax2!" not in fake_rotel.received
    assert hass.states.get(ENTITY).attributes["source"] == "Алиса"
    assert len(events) == 1
    assert events[0].data["source"] == "Алиса"
    assert events[0].data["previous_source"] == "ТВ"
    await hass.config_entries.async_unload(entry.entry_id)
