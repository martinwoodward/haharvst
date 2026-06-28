"""The Harvst greenhouse integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .client import HarvstClient, HarvstConnectionError
from .const import (
    ATTR_SECONDS,
    ATTR_ZONE,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_WATER_SECONDS,
    MIN_WATER_SECONDS,
    SERVICE_WATER_ZONE,
    ZONES,
)
from .coordinator import HarvstCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
]

WATER_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): vol.All(vol.Coerce(int), vol.In(ZONES)),
        vol.Required(ATTR_SECONDS): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_WATER_SECONDS, max=MAX_WATER_SECONDS),
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Harvst from a config entry."""
    session = async_get_clientsession(hass)
    client = HarvstClient(entry.data[CONF_HOST], session)

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    try:
        device_id = await client.async_get_device_id()
    except HarvstConnectionError:
        device_id = None

    coordinator = HarvstCoordinator(
        hass, entry, client, scan_interval, device_id or entry.unique_id
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_WATER_ZONE)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_WATER_ZONE):
        return

    async def _handle_water_zone(call: ServiceCall) -> None:
        zone = call.data[ATTR_ZONE]
        seconds = call.data[ATTR_SECONDS]
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            raise HomeAssistantError("No Harvst control panel configured")
        try:
            for coordinator in coordinators:
                await coordinator.async_water_zone(zone, seconds)
        except HarvstConnectionError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_WATER_ZONE,
        _handle_water_zone,
        schema=WATER_ZONE_SCHEMA,
    )
