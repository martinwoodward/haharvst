"""Data update coordinator for the Harvst integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
import re
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HarvstClient, HarvstConnectionError
from .const import (
    DOMAIN,
    KEY_CURRENT,
    KEY_PUMP_STATE,
    KEY_TEMPERATURE,
    KEY_TEMPERATURE_AVG,
    SENSOR_ABSENT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class HarvstData:
    """Parsed state of the control panel."""

    temperature: float | None = None
    temperature_average: float | None = None
    current: int | None = None
    pump_running: bool = False
    pump_back_pressure: str | None = None
    pump_back_pressure_value: int | None = None
    pump_back_pressure_reference: int | None = None
    pump_detection: str | None = None
    low_water: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _is_low_water(pump_detection: str | None) -> bool | None:
    """Derive a low-water flag from the panel's pump detection status.

    Low water is detected by the pump via back pressure (current drain): when
    the pump starts pushing air the panel reports a non-OK status. The exact
    wording isn't documented, so any status that doesn't read as "OK" is treated
    as a low-water alert. ``None`` (status unknown) yields ``None``.
    """
    if pump_detection is None:
        return None
    return "ok" not in pump_detection.casefold()


def _parse_back_pressure(value: str | None) -> tuple[int | None, int | None]:
    """Split a "56 / 4712" back-pressure string into (reading, reference)."""
    if not value:
        return None, None
    numbers = [int(n) for n in re.findall(r"-?\d+", value)]
    reading = numbers[0] if len(numbers) >= 1 else None
    reference = numbers[1] if len(numbers) >= 2 else None
    return reading, reference


def _clean_temperature(value: Any) -> float | None:
    """Return a temperature, treating the panel's -13 sentinel as absent."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number == SENSOR_ABSENT:
        return None
    return number


def parse_reading(reading: dict[str, Any]) -> HarvstData:
    """Convert a raw panel reading into a :class:`HarvstData`."""
    current = reading.get(KEY_CURRENT)
    try:
        current_val = int(current) if current is not None else None
    except (TypeError, ValueError):
        current_val = None

    pump_state = reading.get(KEY_PUMP_STATE)
    # The pump_state field is only present on transition readings. During
    # steady-state pumping the current (cc) stays strongly negative, while it
    # is ~100 when idle, so a negative current is a reliable "watering" signal.
    if pump_state is not None:
        pump_running = bool(int(pump_state))
    elif current_val is not None:
        pump_running = current_val < 0
    else:
        pump_running = False

    return HarvstData(
        temperature=_clean_temperature(reading.get(KEY_TEMPERATURE)),
        temperature_average=_clean_temperature(reading.get(KEY_TEMPERATURE_AVG)),
        current=current_val,
        pump_running=pump_running,
        raw=reading,
    )


class HarvstCoordinator(DataUpdateCoordinator[HarvstData]):
    """Poll one reading from the panel's event stream on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: HarvstClient,
        scan_interval: int,
        device_id: str | None,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry = entry
        self.device_id = device_id
        # Per-zone "water now" durations (seconds), shared between the number
        # entities (which set them) and the button entities (which use them).
        self.zone_durations: dict[int, int] = {}
        # Tracks the most recent zone we commanded and when that run ends, so
        # per-zone watering sensors can attribute active pumping to a zone.
        self._active_zone: int | None = None
        self._active_until: float = 0.0

    @property
    def host(self) -> str:
        """Return the panel host."""
        return self.client.host

    async def _async_update_data(self) -> HarvstData:
        try:
            reading = await self.client.async_get_reading()
        except HarvstConnectionError as err:
            raise UpdateFailed(str(err)) from err
        data = parse_reading(reading)
        await self._apply_settings_info(data)
        return data

    async def _apply_settings_info(self, data: HarvstData) -> None:
        """Populate diagnostic fields scraped from /settings (best effort).

        A failure to read /settings must not fail the whole update (the SSE
        reading is the primary data), so we log and fall back to the previously
        known values instead.
        """
        try:
            info = await self.client.async_get_settings_info()
        except HarvstConnectionError as err:
            _LOGGER.debug("Could not read pump diagnostics from /settings: %s", err)
            if self.data is not None:
                data.pump_back_pressure = self.data.pump_back_pressure
                data.pump_back_pressure_value = self.data.pump_back_pressure_value
                data.pump_back_pressure_reference = (
                    self.data.pump_back_pressure_reference
                )
                data.pump_detection = self.data.pump_detection
                data.low_water = self.data.low_water
            return

        data.pump_back_pressure = info.get("pump_back_pressure")
        data.pump_detection = info.get("pump_detection")
        data.low_water = _is_low_water(data.pump_detection)
        reading, reference = _parse_back_pressure(data.pump_back_pressure)
        data.pump_back_pressure_value = reading
        data.pump_back_pressure_reference = reference

    async def async_water_zone(self, zone: int, seconds: int) -> None:
        """Trigger watering and remember which zone is now active."""
        await self.client.async_water_zone(zone, seconds)
        self._active_zone = zone
        self._active_until = time.monotonic() + seconds
        await self.async_request_refresh()

    def zone_is_watering(self, zone: int) -> bool:
        """Return True if ``zone`` is currently being watered by us."""
        data = self.data
        if data is None or not data.pump_running:
            return False
        if self._active_zone != zone:
            return False
        return time.monotonic() < self._active_until
