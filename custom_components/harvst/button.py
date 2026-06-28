"""Button platform: trigger watering for a zone."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HarvstConnectionError
from .const import DEFAULT_WATER_SECONDS, DOMAIN, ZONES
from .coordinator import HarvstCoordinator
from .entity import HarvstEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Harvst water-now buttons."""
    coordinator: HarvstCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(HarvstWaterZoneButton(coordinator, zone) for zone in ZONES)


class HarvstWaterZoneButton(HarvstEntity, ButtonEntity):
    """Water a zone for the duration configured by its number entity."""

    def __init__(self, coordinator: HarvstCoordinator, zone: int) -> None:
        """Initialise the button for ``zone``."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_name = f"Water zone {zone}"
        self._attr_unique_id = f"{self._identifier}_water_zone_{zone}"

    async def async_press(self) -> None:
        """Trigger watering on this zone."""
        seconds = self.coordinator.zone_durations.get(self._zone, DEFAULT_WATER_SECONDS)
        try:
            await self.coordinator.async_water_zone(self._zone, seconds)
        except HarvstConnectionError as err:
            raise HomeAssistantError(str(err)) from err
