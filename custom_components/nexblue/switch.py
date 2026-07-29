"""NexBlue charger start/stop control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from nexblue_api import NexBlueCommandError, NexBlueConnectionError, NexBlueRateLimitError

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Add one charging control per reachable charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(NexBlueChargingSwitch(coordinator, serial_number) for serial_number in coordinator.data)


class NexBlueChargingSwitch(CoordinatorEntity[NexBlueDataUpdateCoordinator], SwitchEntity):
    """Expose only the documented cloud start/stop APIs as a Home Assistant switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "charging"

    def __init__(self, coordinator: NexBlueDataUpdateCoordinator, serial_number: str) -> None:
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_charging"
        self._attr_device_info = DeviceInfo(
            identifiers={("nexblue", serial_number)}, name=f"NexBlue {serial_number}", manufacturer="NexBlue"
        )

    @property
    def is_on(self) -> bool:
        """NexBlue status enum 2 means charging."""
        return str(self.coordinator.data[self._serial_number].charging_state).lower() in {"2", "charging"}

    async def async_turn_on(self, **kwargs) -> None:
        """Start a session, then request one coordinated status refresh."""
        await self._async_set_charging(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop a session, then request one coordinated status refresh."""
        await self._async_set_charging(False)

    async def _async_set_charging(self, should_charge: bool) -> None:
        try:
            if should_charge:
                await self.coordinator.client.async_start_charging(self._serial_number)
            else:
                await self.coordinator.client.async_stop_charging(self._serial_number)
        except (NexBlueCommandError, NexBlueConnectionError, NexBlueRateLimitError) as err:
            raise HomeAssistantError("NexBlue charger command failed") from err
        await self.coordinator.async_request_refresh()
