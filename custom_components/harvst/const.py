"""Constants for the Harvst greenhouse integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "harvst"

# Config / options keys
CONF_HOST: Final = "host"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
DEFAULT_WATER_SECONDS: Final = 30
MIN_WATER_SECONDS: Final = 1
MAX_WATER_SECONDS: Final = 3600

# Zones we support (the aux outputs x1/x2/x3 are intentionally ignored).
ZONES: Final = (1, 2)

# Sentinel value the control panel reports when a sensor is not present.
SENSOR_ABSENT: Final = -13

# Service
SERVICE_WATER_ZONE: Final = "water_zone"
ATTR_ZONE: Final = "zone"
ATTR_SECONDS: Final = "seconds"

# Reading dictionary keys (as emitted by the panel's /events SSE stream).
KEY_TEMPERATURE: Final = "te"
KEY_TEMPERATURE_AVG: Final = "teAve"
KEY_CURRENT: Final = "cc"
KEY_PUMP_STATE: Final = "pump_state"

# Keys for diagnostic values scraped from the /settings page.
KEY_PUMP_BACK_PRESSURE: Final = "pump_back_pressure"
KEY_PUMP_DETECTION: Final = "pump_detection"
