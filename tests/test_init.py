"""Tests for setup, entities and the water_zone service."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.harvst.const import (
    ATTR_SECONDS,
    ATTR_ZONE,
    CONF_HOST,
    DOMAIN,
    SERVICE_WATER_ZONE,
)

from .conftest import SETTINGS_HTML, SSE_IDLE


@pytest.fixture
async def setup_integration(hass: HomeAssistant, aioclient_mock, host):
    """Set up the integration with a mocked panel and return the entry."""
    aioclient_mock.get(f"http://{host}/events", text=SSE_IDLE)
    aioclient_mock.get(f"http://{host}/settings", text=SETTINGS_HTML)
    aioclient_mock.get(f"http://{host}/control", status=302)

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: host}, unique_id="A84467B865E4"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_created(hass: HomeAssistant, setup_integration):
    """Core entities are created from a single idle reading."""
    temp = hass.states.get("sensor.harvst_greenhouse_temperature")
    assert temp is not None
    assert temp.state == "22.0"

    pump = hass.states.get("binary_sensor.harvst_greenhouse_pump_running")
    assert pump is not None
    assert pump.state == STATE_OFF

    assert hass.states.get("button.harvst_greenhouse_water_zone_1") is not None
    assert hass.states.get("button.harvst_greenhouse_water_zone_2") is not None
    assert (
        hass.states.get("number.harvst_greenhouse_zone_1_watering_duration") is not None
    )


async def test_pump_diagnostics_from_settings(hass: HomeAssistant, setup_integration):
    """Pump back pressure and detection sensors are scraped from /settings."""
    back_pressure = hass.states.get("sensor.harvst_greenhouse_pump_back_pressure")
    assert back_pressure is not None
    assert back_pressure.state == "56"
    assert back_pressure.attributes["raw"] == "56 / 4712"
    assert back_pressure.attributes["reference"] == 4712

    detection = hass.states.get("sensor.harvst_greenhouse_pump_detection")
    assert detection is not None
    assert detection.state == "Pump OK"

    low_water = hass.states.get("binary_sensor.harvst_greenhouse_low_water")
    assert low_water is not None
    assert low_water.state == STATE_OFF
    assert low_water.attributes["status"] == "Pump OK"


async def test_water_zone_service(
    hass: HomeAssistant, aioclient_mock, setup_integration
):
    """The water_zone service issues a control request to the panel."""
    before = aioclient_mock.call_count
    await hass.services.async_call(
        DOMAIN,
        SERVICE_WATER_ZONE,
        {ATTR_ZONE: 1, ATTR_SECONDS: 15},
        blocking=True,
    )
    await hass.async_block_till_done()

    control_calls = [c for c in aioclient_mock.mock_calls if "/control" in str(c[1])]
    assert control_calls
    last = control_calls[-1]
    assert last[1].query["zone"] == "1"
    assert last[1].query["time"] == "15"
    assert aioclient_mock.call_count > before


async def test_button_press_waters_zone(
    hass: HomeAssistant, aioclient_mock, setup_integration
):
    """Pressing a zone button waters that zone for its configured duration."""
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.harvst_greenhouse_zone_2_watering_duration",
            "value": 20,
        },
        blocking=True,
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.harvst_greenhouse_water_zone_2"},
        blocking=True,
    )
    await hass.async_block_till_done()

    control_calls = [c for c in aioclient_mock.mock_calls if "/control" in str(c[1])]
    assert control_calls
    last = control_calls[-1]
    assert last[1].query["zone"] == "2"
    assert last[1].query["time"] == "20"


async def test_zone_watering_sensor_tracks_command(
    hass: HomeAssistant, aioclient_mock, host, setup_integration
):
    """After commanding a zone while the pump runs, its sensor turns on."""
    # Re-mock /events to now report the pump running.
    from .conftest import PUMPING_READING

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"http://{host}/events",
        text=f"id: 9\nevent: new_readings\ndata: {PUMPING_READING}\n\n",
    )
    aioclient_mock.get(f"http://{host}/settings", text=SETTINGS_HTML)
    aioclient_mock.get(f"http://{host}/control", status=302)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WATER_ZONE,
        {ATTR_ZONE: 1, ATTR_SECONDS: 300},
        blocking=True,
    )
    await hass.async_block_till_done()

    zone1 = hass.states.get("binary_sensor.harvst_greenhouse_zone_1_watering")
    assert zone1.state == STATE_ON
    zone2 = hass.states.get("binary_sensor.harvst_greenhouse_zone_2_watering")
    assert zone2.state == STATE_OFF


async def test_unload_entry(hass: HomeAssistant, setup_integration):
    """Unloading removes the entry and its service."""
    entry = setup_integration
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, SERVICE_WATER_ZONE)
