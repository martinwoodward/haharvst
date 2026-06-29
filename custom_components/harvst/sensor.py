"""Sensor platform for Harvst (temperature)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HarvstCoordinator
from .entity import HarvstEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Harvst sensors."""
    coordinator: HarvstCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HarvstTemperatureSensor(coordinator),
            HarvstAverageTemperatureSensor(coordinator),
            HarvstPumpBackPressureSensor(coordinator),
            HarvstPumpDetectionSensor(coordinator),
        ]
    )


class HarvstTemperatureSensor(HarvstEntity, SensorEntity):
    """The wired 'silver bullet' temperature probe."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "temperature"

    def __init__(self, coordinator: HarvstCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._identifier}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.temperature


class HarvstAverageTemperatureSensor(HarvstEntity, SensorEntity):
    """The rolling average temperature reported by the panel."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "temperature_average"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HarvstCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._identifier}_temperature_average"

    @property
    def native_value(self) -> float | None:
        """Return the average temperature."""
        value = self.coordinator.data.temperature_average
        return round(value, 1) if value is not None else None


class HarvstPumpBackPressureSensor(HarvstEntity, SensorEntity):
    """Pump back-pressure diagnostic reported on the /settings page.

    The panel reports this as two numbers (e.g. ``56 / 4712``); the current
    reading is exposed as the state, with both numbers available as attributes.
    """

    _attr_translation_key = "pump_back_pressure"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HarvstCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._identifier}_pump_back_pressure"

    @property
    def native_value(self) -> int | None:
        """Return the current back-pressure reading."""
        return self.coordinator.data.pump_back_pressure_value

    @property
    def extra_state_attributes(self) -> dict[str, int | str] | None:
        """Expose the raw string and the calibration reference value."""
        data = self.coordinator.data
        attrs: dict[str, int | str] = {}
        if data.pump_back_pressure is not None:
            attrs["raw"] = data.pump_back_pressure
        if data.pump_back_pressure_reference is not None:
            attrs["reference"] = data.pump_back_pressure_reference
        return attrs or None


class HarvstPumpDetectionSensor(HarvstEntity, SensorEntity):
    """Pump detection status reported on the /settings page (e.g. 'Pump OK')."""

    _attr_translation_key = "pump_detection"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HarvstCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._identifier}_pump_detection"

    @property
    def native_value(self) -> str | None:
        """Return the pump detection status string."""
        return self.coordinator.data.pump_detection
