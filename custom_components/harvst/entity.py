"""Base entity for the Harvst integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HarvstCoordinator


class HarvstEntity(CoordinatorEntity[HarvstCoordinator]):
    """Common base wiring the entity to the panel device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HarvstCoordinator) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        identifier = coordinator.device_id or coordinator.host
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="Harvst",
            name="Harvst Greenhouse",
            model="Control Panel",
            configuration_url=f"http://{coordinator.host}/",
        )

    @property
    def _identifier(self) -> str:
        """Return the stable identifier used to build unique ids."""
        return self.coordinator.device_id or self.coordinator.host
