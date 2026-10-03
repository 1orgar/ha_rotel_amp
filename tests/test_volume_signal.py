"""Signal detection on digital inputs and volume matching between inputs."""
from __future__ import annotations

import asyncio

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, wait_for


def _entry(port: int, **options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"127.0.0.1:{port}",
        title="Rotel",
        data={"host": "127.0.0.1", "port": port, "name": "Rotel"},
        options={
            "sources": ["coax1", "coax2", "opt1", "cd"],
            "source_names": {"coax1": "Алиса", "coax2": "Плеер", "opt1": "ТВ",
                             "cd": "CD"},
            "source_players": {},
            "max_volume": 80,
            "poll_interval": 0,
            "auto_off": 0,
            **options,
        },
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")


async def _select(hass: HomeAssistant, source: str) -> None:
    await hass.services.async_call(
        "media_player", "select_source", {"entity_id": ENTITY, "source": source},
        blocking=True,
    )


def _amp(hass: HomeAssistant) -> int | None:
    return hass.states.get(ENTITY).attributes.get("amp_volume")


async def test_auto_off_respects_digital_signal(hass: HomeAssistant, fake_rotel) -> None:
    """TV on optical: no linked player, but signal present -> stay on."""
    fake_rotel.state.update(source="opt1", freq="48000")
    await _setup(hass, _entry(fake_rotel.port, auto_off=0.01))  # 0.6 s
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("signal") is True)
    await asyncio.sleep(1.2)
    assert "power_off!" not in fake_rotel.received

    # TV turned off: signal gone -> auto off
    fake_rotel.state["freq"] = "off"
    await fake_rotel.push("freq=off$")
    await wait_for(lambda: "power_off!" in fake_rotel.received, timeout=5)


async def test_keep_on_input(hass: HomeAssistant, fake_rotel) -> None:
    """Analog input marked "never auto off": timer never runs there."""
    fake_rotel.state.update(source="cd")
    await _setup(hass, _entry(fake_rotel.port, auto_off=0.01, source_keep_on=["cd"]))
    await asyncio.sleep(1.2)
    assert "power_off!" not in fake_rotel.received


async def test_signal_checked_after_input_change(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(source="cd")
    fake_rotel.signals["opt1"] = "44100"
    await _setup(hass, _entry(fake_rotel.port))
    fake_rotel.received.clear()
    await _select(hass, "ТВ")
    await wait_for(lambda: "freq?" in fake_rotel.received, timeout=4)
    await wait_for(lambda: hass.states.get(ENTITY).attributes.get("signal") is True)


async def test_volume_matching(hass: HomeAssistant, fake_rotel) -> None:
    """Player 40 sounds like Alice 20: Player at 30 -> Alice at 15 and back."""
    fake_rotel.state.update(source="coax2", volume="30")
    await _setup(hass, _entry(fake_rotel.port,
                              source_ref_volume={"coax2": 40, "coax1": 20}))

    await _select(hass, "Алиса")
    await wait_for(lambda: _amp(hass) == 15)
    # quieter target: volume is lowered BEFORE the input switch
    assert fake_rotel.received.index("vol_15!") < fake_rotel.received.index("coax1!")

    await _select(hass, "Плеер")
    await wait_for(lambda: _amp(hass) == 30)
    # louder target: input first, then volume
    assert fake_rotel.received.index("coax2!") < fake_rotel.received.index("vol_30!")

    # input without a reference -> volume untouched
    await _select(hass, "ТВ")
    await wait_for(lambda: hass.states.get(ENTITY).attributes["source"] == "ТВ")
    assert _amp(hass) == 30


async def test_volume_matching_capped_by_max(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.state.update(source="coax1", volume="50")
    await _setup(hass, _entry(fake_rotel.port, max_volume=60,
                              source_ref_volume={"coax2": 40, "coax1": 20}))
    await _select(hass, "Плеер")
    await wait_for(lambda: _amp(hass) == 60)
