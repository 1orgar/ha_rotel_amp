"""Options flow: menu, per-input editing, player options visibility."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .helpers import ENTITY, general, make_entry, one_input, wait_for
from .test_config_flow import STREAMER, field_names


async def _open(hass: HomeAssistant, port: int):
    entry = make_entry(port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    return entry, result


async def _menu(hass: HomeAssistant, flow_id: str, option: str):
    return await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": option}
    )


async def test_options_menu_and_general(hass: HomeAssistant, fake_rotel) -> None:
    entry, result = await _open(hass, fake_rotel.port)
    flow = result["flow_id"]
    # no linked players -> no announce item
    assert result["menu_options"] == ["general", "inputs", "save"]
    assert "Стример (Coax 2)" in result["description_placeholders"]["summary"]

    result = await _menu(hass, flow, "general")
    assert result["step_id"] == "general"
    result = await hass.config_entries.options.async_configure(
        flow, general(["coax2", "cd"], max_volume=70)
    )
    assert result["type"] is FlowResultType.MENU
    assert result["description_placeholders"]["unsaved"]
    result = await _menu(hass, flow, "save")
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["sources"] == ["cd", "coax2"]  # canonical order
    assert entry.options["max_volume"] == 70
    # deselected input forgets its name
    assert entry.options["source_names"] == {"coax2": "Стример"}
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_edit_input(hass: HomeAssistant, fake_rotel) -> None:
    entry, result = await _open(hass, fake_rotel.port)
    flow = result["flow_id"]
    result = await _menu(hass, flow, "inputs")
    assert result["step_id"] == "inputs"
    result = await hass.config_entries.options.async_configure(flow, {"sources": "coax2"})
    assert result["step_id"] == "input"
    assert field_names(result) == ["name", "player", "power_volume"]

    # own entity is rejected
    result = await hass.config_entries.options.async_configure(
        flow, one_input("Стример", ENTITY, with_player_section=False)
    )
    assert "player_options" in field_names(result)  # shown for the chosen player
    result = await hass.config_entries.options.async_configure(
        flow, one_input("Стример", ENTITY)
    )
    assert result["errors"] == {"player": "self_player"}

    result = await hass.config_entries.options.async_configure(
        flow, one_input("Стример", STREAMER, with_player_section=False)
    )
    assert field_names(result) == ["name", "player", "player_options", "power_volume"]
    result = await hass.config_entries.options.async_configure(
        flow, one_input("Стример", STREAMER, follow=True)
    )
    assert result["type"] is FlowResultType.MENU
    assert "announce" in result["menu_options"]  # a player now exists

    # clearing the player removes its flags; the form then hides them again
    result = await _menu(hass, flow, "inputs")
    result = await hass.config_entries.options.async_configure(flow, {"sources": "coax2"})
    assert "player_options" in field_names(result)
    result = await hass.config_entries.options.async_configure(flow, one_input("Стример"))
    assert result["type"] is FlowResultType.MENU
    result = await _menu(hass, flow, "save")
    await hass.async_block_till_done()
    assert entry.options["source_players"] == {}
    assert entry.options["source_follow"] == []
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_announce(hass: HomeAssistant, fake_rotel) -> None:
    entry, result = await _open(hass, fake_rotel.port)
    flow = result["flow_id"]
    result = await _menu(hass, flow, "inputs")
    result = await hass.config_entries.options.async_configure(flow, {"sources": "coax2"})
    result = await hass.config_entries.options.async_configure(
        flow, one_input("Стример", STREAMER, with_player_section=False)
    )
    result = await hass.config_entries.options.async_configure(
        flow, one_input("Стример", STREAMER)
    )
    result = await _menu(hass, flow, "announce")
    assert result["step_id"] == "announce"
    result = await hass.config_entries.options.async_configure(
        flow, {"announce_source": "coax2", "announce_volume": 25}
    )
    result = await _menu(hass, flow, "save")
    await hass.async_block_till_done()
    assert entry.options["announce_source"] == "coax2"
    assert entry.options["announce_volume"] == 25
    await hass.config_entries.async_unload(entry.entry_id)
