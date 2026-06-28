"""Binary sensor platform for Harvst (watering state)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ZONES
from .coordinator import HarvstCoordinator
from .entity import HarvstEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Harvst binary sensors."""
    coordinator: HarvstCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [HarvstPumpRunningSensor(coordinator)]
    entities.extend(HarvstZoneWateringSensor(coordinator, zone) for zone in ZONES)
    async_add_entities(entities)


class HarvstPumpRunningSensor(HarvstEntity, BinarySensorEntity):
    """True whenever the pump is running (any zone)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "pump_running"

    def __init__(self, coordinator: HarvstCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._identifier}_pump_running"

    @property
    def is_on(self) -> bool:
        """Return True if the pump is running."""
        return self.coordinator.data.pump_running

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Expose the raw pump current for diagnostics."""
        return {"current_ma": self.coordinator.data.current}


class HarvstZoneWateringSensor(HarvstEntity, BinarySensorEntity):
    """True while a specific zone is being watered."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, coordinator: HarvstCoordinator, zone: int) -> None:
        """Initialise the sensor for ``zone``."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_translation_key = f"zone_{zone}_watering"
        self._attr_name = f"Zone {zone} watering"
        self._attr_unique_id = f"{self._identifier}_zone_{zone}_watering"

    @property
    def is_on(self) -> bool:
        """Return True if this zone is currently watering."""
        return self.coordinator.zone_is_watering(self._zone)
