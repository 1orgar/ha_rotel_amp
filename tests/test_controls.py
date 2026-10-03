"""Tone / speaker / dimmer entities."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .helpers import ENTITY, make_entry, wait_for


async def _set(hass: HomeAssistant, domain: str, service: str, data: dict) -> None:
    await hass.services.async_call(domain, service, data, blocking=True)


def _st(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_tone_speaker_dimmer_entities(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    await wait_for(lambda: _st(hass, "number.rotel_bass") == "0")

    await _set(hass, "number", "set_value", {"entity_id": "number.rotel_bass", "value": 4})
    await wait_for(lambda: _st(hass, "number.rotel_bass") == "4")
    assert "bass_+04!" in fake_rotel.received

    await _set(hass, "number", "set_value",
               {"entity_id": "number.rotel_balance", "value": -3})
    await wait_for(lambda: _st(hass, "number.rotel_balance") == "-3")
    assert "balance_l03!" in fake_rotel.received

    assert _st(hass, "switch.rotel_speakers_a") == "on"
    assert _st(hass, "switch.rotel_speakers_b") == "off"
    await _set(hass, "switch", "turn_on", {"entity_id": "switch.rotel_speakers_b"})
    await wait_for(lambda: _st(hass, "switch.rotel_speakers_b") == "on")
    assert _st(hass, "switch.rotel_speakers_a") == "on"

    await _set(hass, "switch", "turn_on", {"entity_id": "switch.rotel_tone_bypass"})
    await wait_for(lambda: _st(hass, "switch.rotel_tone_bypass") == "on")

    await _set(hass, "select", "select_option",
               {"entity_id": "select.rotel_display_dimmer", "option": "3"})
    await wait_for(lambda: _st(hass, "select.rotel_display_dimmer") == "3")

    # amp off -> settings unavailable
    await fake_rotel.push("power=standby$")
    await wait_for(lambda: _st(hass, "number.rotel_bass") == "unavailable")
    await hass.config_entries.async_unload(entry.entry_id)
