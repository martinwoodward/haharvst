"""Number platform: per-zone watering duration used by the buttons."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DEFAULT_WATER_SECONDS,
    DOMAIN,
    MAX_WATER_SECONDS,
    MIN_WATER_SECONDS,
    ZONES,
)
from .coordinator import HarvstCoordinator
from .entity import HarvstEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Harvst duration numbers."""
    coordinator: HarvstCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(HarvstZoneDurationNumber(coordinator, zone) for zone in ZONES)


class HarvstZoneDurationNumber(HarvstEntity, RestoreEntity, NumberEntity):
    """Stores the watering duration (seconds) for a zone's 'water now' button."""

    _attr_native_min_value = MIN_WATER_SECONDS
    _attr_native_max_value = MAX_WATER_SECONDS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_entity_category = None

    def __init__(self, coordinator: HarvstCoordinator, zone: int) -> None:
        """Initialise the number for ``zone``."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_name = f"Zone {zone} watering duration"
        self._attr_unique_id = f"{self._identifier}_zone_{zone}_duration"
        self._value: float = DEFAULT_WATER_SECONDS

    async def async_added_to_hass(self) -> None:
        """Restore the last set duration."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            try:
                self._value = float(last.state)
            except (TypeError, ValueError):
                self._value = DEFAULT_WATER_SECONDS
        self.coordinator.zone_durations[self._zone] = int(self._value)

    @property
    def native_value(self) -> float:
        """Return the configured duration."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Update the configured duration."""
        self._value = value
        self.coordinator.zone_durations[self._zone] = int(value)
        self.async_write_ha_state()
