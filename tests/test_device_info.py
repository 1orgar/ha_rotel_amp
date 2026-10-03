"""Device info sensors, connection test, fixed volume."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.media_player import MediaPlayerEntityFeature as F
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rotel_amp.const import DOMAIN

from .helpers import ENTITY, make_entry, wait_for


async def test_device_sensors(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get("sensor.rotel_model") is not None
                   and hass.states.get("sensor.rotel_model").state == "RA-1572")
    assert hass.states.get("sensor.rotel_firmware").state == "V1.4.3"
    assert hass.states.get("sensor.rotel_mac_address").state == "00:11:22:33:44:55"
    assert hass.states.get("sensor.rotel_ip_address").state == "127.0.0.1"
    assert hass.states.get("sensor.rotel_connection").state == "connected"
    assert hass.states.get("sensor.rotel_reconnects").state == "0"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.unique_id)})
    assert device.model == "RA-1572"
    assert device.sw_version == "V1.4.3"

    await fake_rotel.stop()
    await wait_for(lambda: hass.states.get("sensor.rotel_connection").state == "disconnected")
    assert hass.states.get("sensor.rotel_model").state == "unavailable"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_test_connection_button(hass: HomeAssistant, fake_rotel) -> None:
    entry = make_entry(fake_rotel.port)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state == "on")
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.rotel_test_connection"}, blocking=True
    )
    await wait_for(lambda: hass.states.get("sensor.rotel_response_time").state
                   not in ("unknown", "unavailable"))
    assert float(hass.states.get("sensor.rotel_response_time").state) >= 0
    await hass.config_entries.async_unload(entry.entry_id)


async def test_config_flow_no_rotel_answer(hass: HomeAssistant, fake_rotel) -> None:
    fake_rotel.mute_replies = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1", "port": fake_rotel.port, "name": "Rotel"},
    )
    assert result["errors"] == {"base": "no_response"}


async def test_fixed_volume(hass: HomeAssistant, fake_rotel) -> None:
    child = "media_player.streamer"
    feats = int(F.VOLUME_SET | F.VOLUME_MUTE | F.PLAY)
    hass.states.async_set(child, "idle", {"supported_features": feats,
                                          "volume_level": 0.4})
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"127.0.0.1:{fake_rotel.port}",
        title="Rotel",
        data={"host": "127.0.0.1", "port": fake_rotel.port, "name": "Rotel"},
        options={
            "sources": ["coax2"],
            "source_names": {"coax2": "Стример"},
            "source_players": {"coax2": child},
            "source_fixed_volume": ["coax2"],
            "max_volume": 50,
            "poll_interval": 0,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await wait_for(lambda: hass.states.get(ENTITY).state not in ("unavailable",))

    calls: list[tuple[str, dict]] = []

    async def _rec(call: ServiceCall) -> None:
        calls.append((call.service, dict(call.data)))
        attrs = dict(hass.states.get(child).attributes)
        if call.service == "volume_set":
            attrs["volume_level"] = call.data["volume_level"]
        if call.service == "volume_mute":
            attrs["is_volume_muted"] = call.data["is_volume_muted"]
        hass.states.async_set(child, hass.states.get(child).state, attrs)

    for svc in ("volume_set", "volume_mute"):
        hass.services.async_register("media_player", svc, _rec)

    # someone lowers the child volume and mutes it -> restored to 100 %, unmuted
    hass.states.async_set(child, "playing", {"supported_features": feats,
                                             "volume_level": 0.2,
                                             "is_volume_muted": True})
    await wait_for(lambda: ("volume_set", {"volume_level": 1.0, "entity_id": child})
                   in calls)
    await wait_for(lambda: ("volume_mute", {"is_volume_muted": False,
                                            "entity_id": child}) in calls)
    await wait_for(lambda: hass.states.get(child).attributes["volume_level"] == 1.0)
    n = len(calls)
    hass.states.async_set(child, "paused", dict(hass.states.get(child).attributes))
    await hass.async_block_till_done()
    assert len(calls) == n  # already at 100 % -> nothing to do
    await hass.config_entries.async_unload(entry.entry_id)
