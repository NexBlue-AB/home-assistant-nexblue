"""NexBlue Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from nexblue_api import NexBlueClient

from .const import CONF_API_BASE_URL, DEFAULT_API_URL, PLATFORMS
from .coordinator import NexBlueDataUpdateCoordinator, NexBlueLastSessionCoordinator


NexBlueConfigEntry = ConfigEntry["NexBlueRuntimeData"]


@dataclass(slots=True)
class NexBlueRuntimeData:
    """Runtime-only state; access tokens never enter config entry storage."""

    client: NexBlueClient
    coordinator: NexBlueDataUpdateCoordinator
    session_coordinator: NexBlueLastSessionCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry) -> bool:
    """Set up NexBlue from an existing config entry."""
    client = NexBlueClient(
        async_get_clientsession(hass),
        entry.data.get(CONF_API_BASE_URL, DEFAULT_API_URL),
    )
    coordinator = NexBlueDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    session_coordinator = NexBlueLastSessionCoordinator(hass, entry, client, coordinator)
    # Session history is optional; do not block setup if it is unavailable.
    await session_coordinator.async_refresh()
    entry.runtime_data = NexBlueRuntimeData(
        client=client, coordinator=coordinator, session_coordinator=session_coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NexBlueConfigEntry) -> bool:
    """Unload all NexBlue entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
