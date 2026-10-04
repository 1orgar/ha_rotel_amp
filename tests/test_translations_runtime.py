"""Translations as served to the frontend (backend translation cache)."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation
from homeassistant.setup import async_setup_component

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, make_entry, wait_for


async def _check(hass: HomeAssistant) -> None:
    for lang in ("ru", "en"):
        for cat in ("config", "options"):
            strings = await translation.async_get_translations(
                hass, lang, cat, [DOMAIN]
            )
            base = f"component.{DOMAIN}.{cat}.step.input"
            assert f"{base}.title" in strings, (lang, cat)
            assert f"{base}.data_description.player" in strings, (lang, cat)


async def test_config_translations_before_setup(hass: HomeAssistant) -> None:
    """Adding the first amp: integration not loaded yet."""
    assert await async_setup_component(hass, "homeassistant", {})
    await _check(hass)


async def test_config_translations_with_loaded_entry(
    hass: HomeAssistant, fake_rotel
) -> None:
    """Adding a second amp while one is already loaded."""
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    await _check(hass)
    await hass.config_entries.async_unload(entry.entry_id)
