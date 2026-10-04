"""Test helpers."""
from __future__ import annotations

import asyncio

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rotel_amp.const import DOMAIN

ENTITY = "media_player.rotel"


async def wait_for(cond, timeout: float = 10.0) -> None:
    """Poll until cond() is true."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if cond():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met")


def general(sources: list[str], max_volume: int = 60, auto_off: int = 0,
            poll_interval: int = 0) -> dict:
    """User input of the 'sources' / 'general' step (with sections)."""
    return {
        "sources": sources,
        "volume": {"max_volume": max_volume},
        "power_volume": {"auto_off": auto_off},
        "advanced": {"poll_interval": poll_interval},
    }


def one_input(name: str, player: str | None = None, *, follow: bool = False,
              fixed_volume: bool = False, ref_volume: int = 0,
              keep_on: bool = False, with_player_section: bool = True) -> dict:
    """User input of the per-input step."""
    data: dict = {
        "name": name,
        "power_volume": {"ref_volume": ref_volume, "keep_on": keep_on},
    }
    if player:
        data["player"] = player
        if with_player_section:
            data["player_options"] = {"follow": follow, "fixed_volume": fixed_volume}
    return data


def make_entry(port: int, poll_interval: int = 0) -> MockConfigEntry:
    """Config entry pointing at the fake amp."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"127.0.0.1:{port}",
        title="Rotel",
        data={"host": "127.0.0.1", "port": port, "name": "Rotel"},
        options={
            "sources": ["coax2", "opt1"],
            "source_names": {"coax2": "Стример", "opt1": "ТВ"},
            "max_volume": 50,
            "poll_interval": poll_interval,
        },
    )
