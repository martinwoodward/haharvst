"""Tests for the reading parser and coordinator helpers."""

from __future__ import annotations

import json

from custom_components.harvst.coordinator import (
    _is_low_water,
    _parse_back_pressure,
    parse_reading,
)

from .conftest import IDLE_READING, PUMPING_READING


def test_parse_idle_reading():
    """An idle reading has temperature and no pump running."""
    data = parse_reading(json.loads(IDLE_READING))
    assert data.temperature == 22.0
    assert data.temperature_average == 14.66667
    assert data.current == 100
    assert data.pump_running is False


def test_parse_pumping_reading():
    """A pumping reading reports the pump as running with negative current."""
    data = parse_reading(json.loads(PUMPING_READING))
    assert data.pump_running is True
    assert data.current == -4104


def test_pump_running_inferred_from_negative_current():
    """During steady pumping there is no pump_state, but cc stays negative."""
    data = parse_reading({"te": 21.5, "cc": -3984})
    assert data.pump_running is True


def test_absent_temperature_sentinel_is_none():
    """The -13 sentinel is treated as 'sensor absent'."""
    data = parse_reading({"te": -13, "cc": 100})
    assert data.temperature is None
    assert data.pump_running is False


def test_missing_fields_are_safe():
    """A reading without expected fields does not raise."""
    data = parse_reading({})
    assert data.temperature is None
    assert data.current is None
    assert data.pump_running is False


def test_parse_back_pressure_splits_two_numbers():
    """A "56 / 4712" string splits into reading and reference."""
    reading, reference = _parse_back_pressure("56 / 4712")
    assert reading == 56
    assert reference == 4712


def test_parse_back_pressure_handles_missing():
    """Empty or single-value back-pressure strings degrade gracefully."""
    assert _parse_back_pressure(None) == (None, None)
    assert _parse_back_pressure("") == (None, None)
    assert _parse_back_pressure("42") == (42, None)


def test_low_water_from_pump_detection():
    """Any non-OK pump detection status flags low water."""
    assert _is_low_water("Pump OK") is False
    assert _is_low_water("OK") is False
    assert _is_low_water("Low water") is True
    assert _is_low_water("No water detected") is True
    assert _is_low_water("Pump dry") is True
    # Unknown status (settings not yet read) stays unknown.
    assert _is_low_water(None) is None
