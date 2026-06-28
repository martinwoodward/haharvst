"""Sensor platform for Harvst (temperature)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
