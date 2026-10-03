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
