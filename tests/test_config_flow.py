"""Config flow tests."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, general, one_input, wait_for

STREAMER = "media_player.streamer"


def field_names(result) -> list[str]:
    return [str(k) for k in result["data_schema"].schema]


async def _start(hass: HomeAssistant, port: int):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "127.0.0.1", "port": port, "name": "Rotel"}
    )


async def test_config_flow(hass: HomeAssistant, fake_rotel) -> None:
    result = await _start(hass, fake_rotel.port)
    assert result["step_id"] == "sources"
    assert field_names(result) == ["sources", "volume", "power_volume", "advanced"]
    flow = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow, general([]))
    assert result["errors"] == {"sources": "no_sources"}

    result = await hass.config_entries.flow.async_configure(
        flow, general(["opt1", "coax2"], max_volume=60, auto_off=15, poll_interval=20)
    )
    # inputs are configured one by one, in canonical order
    assert result["step_id"] == "input"
    assert result["description_placeholders"]["input"] == "Coax 2"
    # no player yet -> no player options
    assert field_names(result) == ["name", "player", "power_volume"]

    # picking a player shows the same input again, now with its options
    result = await hass.config_entries.flow.async_configure(
        flow, one_input("Стример", STREAMER, with_player_section=False)
    )
    assert result["description_placeholders"]["input"] == "Coax 2"
    assert field_names(result) == ["name", "player", "player_options", "power_volume"]
    result = await hass.config_entries.flow.async_configure(
        flow,
        one_input("Стример", STREAMER, follow=True, fixed_volume=True, ref_volume=40),
    )
    assert result["description_placeholders"]["input"] == "Optical 1"

    result = await hass.config_entries.flow.async_configure(flow, one_input("Стример"))
    assert result["errors"] == {"name": "duplicate_name"}
    result = await hass.config_entries.flow.async_configure(
        flow, one_input("ТВ", keep_on=True)
    )
    # all inputs done -> overview with navigation ("back")
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "overview"
    assert result["menu_options"] == ["finish", "edit_input", "announce", "sources"]
    assert "Стример (Coax 2)" in result["description_placeholders"]["summary"]

    # go back to an input and change it
    result = await hass.config_entries.flow.async_configure(
        flow, {"next_step_id": "edit_input"}
    )
    result = await hass.config_entries.flow.async_configure(flow, {"sources": "opt1"})
    assert result["step_id"] == "input"
    assert result["description_placeholders"]["input"] == "Optical 1"
    result = await hass.config_entries.flow.async_configure(
        flow, one_input("ТВ", keep_on=True)
    )
    assert result["step_id"] == "overview"

    # back to general settings: already configured inputs are not asked again
    result = await hass.config_entries.flow.async_configure(
        flow, {"next_step_id": "sources"}
    )
    assert result["step_id"] == "sources"
    result = await hass.config_entries.flow.async_configure(
        flow, general(["opt1", "coax2"], max_volume=60, auto_off=15, poll_interval=20)
    )
    assert result["step_id"] == "overview"

    result = await hass.config_entries.flow.async_configure(
        flow, {"next_step_id": "announce"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow, {"announce_source": "coax2", "announce_volume": 30}
    )
    assert result["step_id"] == "overview"
    result = await hass.config_entries.flow.async_configure(
        flow, {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "sources": ["coax2", "opt1"],
        "source_names": {"coax2": "Стример", "opt1": "ТВ"},
        "source_players": {"coax2": STREAMER},
        "source_follow": ["coax2"],
        "source_fixed_volume": ["coax2"],
        "source_ref_volume": {"coax2": 40},
        "source_keep_on": ["opt1"],
        "announce_source": "coax2",
        "announce_volume": 30,
        "max_volume": 60,
        "poll_interval": 20,
        "auto_off": 15,
    }
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("source") == "Стример")
    assert hass.states.get(ENTITY).attributes["source_list"] == ["Стример", "ТВ"]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_config_flow_without_players_skips_announce(
    hass: HomeAssistant, fake_rotel
) -> None:
    result = await _start(hass, fake_rotel.port)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], general(["cd"])
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], one_input("")  # empty name -> default name
    )
    assert result["menu_options"] == ["finish", "edit_input", "sources"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["source_names"] == {"cd": "CD"}
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await _start(hass, 1)
    assert result["errors"] == {"base": "cannot_connect"}
