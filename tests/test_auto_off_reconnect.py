"""Auto power off countdown across amplifier connection drops."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest

from .helpers import wait_for
from .test_auto_off_flapping import AUTO_OFF, set_alice, turned_off
from .test_follow_autooff import _setup


@pytest.fixture(autouse=True)
def fast_reconnect():
    with patch(
        "custom_components.rotel_amp.client.RECONNECT_MIN_DELAY", 0.05
    ), patch("custom_components.rotel_amp.client.RECONNECT_MAX_DELAY", 0.1):
        yield


async def test_countdown_survives_amp_reconnect(hass: HomeAssistant, fake_rotel) -> None:
    """Connection drops mid-countdown: the countdown is not restarted."""
    fake_rotel.state.update(power="on", source="coax1")
    set_alice(hass, "paused")
    entry = await _setup(hass, fake_rotel, source_follow=[], auto_off=AUTO_OFF)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await asyncio.sleep(0.5)
    await fake_rotel.reboot(downtime=0.2)
    await wait_for(lambda: turned_off(fake_rotel), timeout=5)
    # ~1.2 s plus reconnect time, not 0.5 + reconnect + a fresh 1.2 s
    assert loop.time() - start < 2.2
    await hass.config_entries.async_unload(entry.entry_id)


async def test_due_while_disconnected_fires_after_reconnect(
    hass: HomeAssistant, fake_rotel
) -> None:
    fake_rotel.state.update(power="on", source="coax1")
    set_alice(hass, "paused")
    entry = await _setup(hass, fake_rotel, source_follow=[], auto_off=AUTO_OFF)
    await asyncio.sleep(0.2)
    await fake_rotel.reboot(downtime=1.6)  # the deadline passes while offline
    await wait_for(lambda: turned_off(fake_rotel), timeout=5)
    await hass.config_entries.async_unload(entry.entry_id)
