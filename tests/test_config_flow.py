"""Config / options flow tests."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, make_entry, wait_for


async def test_config_flow(hass: HomeAssistant, fake_rotel) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1", "port": fake_rotel.port, "name": "Rotel"},
    )
    assert result["step_id"] == "sources"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sources": [], "max_volume": 60, "poll_interval": 20, "auto_off": 0},
    )
    assert result["errors"] == {"sources": "no_sources"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "sources": ["opt1", "coax2"],
            "max_volume": 60,
            "poll_interval": 20,
            "auto_off": 15,
        },
    )
    assert result["step_id"] == "names"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name_coax2": "Стример", "name_opt1": "Стример"}
    )
    assert result["errors"] == {"name_opt1": "duplicate_name"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name_coax2": "Стример", "name_opt1": "ТВ"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "sources": ["coax2", "opt1"],
        "source_names": {"coax2": "Стример", "opt1": "ТВ"},
        "source_players": {},
        "source_follow": [],
        "source_fixed_volume": [],
        "max_volume": 60,
        "poll_interval": 20,
        "auto_off": 15,
    }
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("source") == "Стример")
    assert hass.states.get(ENTITY).attributes["source_list"] == ["Стример", "ТВ"]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "127.0.0.1", "port": 1, "name": "Rotel"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"sources": ["coax2", "cd"], "max_volume": 70, "poll_interval": 0, "auto_off": 0}
    )
    assert result["step_id"] == "names"
    # linking the integration's own entity is rejected
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name_cd": "Проигрыватель", "name_coax2": "Streamer", "player_cd": ENTITY},
    )
    assert result["errors"] == {"player_cd": "self_player"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name_cd": "Проигрыватель",
            "name_coax2": "Streamer",
            "player_coax2": "media_player.streamer",
            "follow_coax2": True,
            "follow_cd": True,  # ignored: no player linked
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["source_players"] == {"coax2": "media_player.streamer"}
    assert entry.options["source_follow"] == ["coax2"]
    await wait_for(
        lambda: (s := hass.states.get(ENTITY)) is not None
        and s.attributes.get("source_list") == ["Проигрыватель", "Streamer"]
    )
    await hass.config_entries.async_unload(entry.entry_id)
