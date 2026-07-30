"""NexBlue charger start/stop control."""

from __future__ import annotations

import time

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from nexblue_api import (
    NexBlueCommandError,
    NexBlueConnectionError,
    NexBlueDeviceOfflineError,
    NexBlueRateLimitError,
)

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator

ASSUMED_STATE_SECONDS = 15
COMMAND_REFRESH_DELAYS = (1, 3, 8, 15)


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
        self._assumed_is_on: bool | None = None
        self._assumed_state_expires_at = 0.0
        self._attr_unique_id = f"{serial_number}_charging"
        self._attr_device_info = DeviceInfo(
            identifiers={("nexblue", serial_number)}, name=f"{serial_number}", manufacturer="NexBlue"
        )

    @property
    def available(self) -> bool:
        """Return false when this charger is listed but currently unreachable."""
        return self.coordinator.data.get(self._serial_number) is not None

    @property
    def is_on(self) -> bool:
        """NexBlue status enum 2 means charging."""
        if self._assumed_is_on is not None:
            if time.monotonic() < self._assumed_state_expires_at:
                return self._assumed_is_on
            self._assumed_is_on = None

        status = self.coordinator.data.get(self._serial_number)
        return status is not None and str(status.charging_state).lower() in {
            "2",
            "3",
            "5",
            "7",
        }

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
        except (
            NexBlueCommandError,
            NexBlueConnectionError,
            NexBlueDeviceOfflineError,
            NexBlueRateLimitError,
        ) as err:
            raise HomeAssistantError(str(err)) from err

        self._assumed_is_on = should_charge
        self._assumed_state_expires_at = time.monotonic() + ASSUMED_STATE_SECONDS
        self.async_write_ha_state()
        self._schedule_command_refreshes()
        await self.coordinator.async_request_refresh()

    def _schedule_command_refreshes(self) -> None:
        """Refresh shortly after a command while the cloud/device state catches up."""
        @callback
        def _request_refresh(_now) -> None:
            """Request a coordinator refresh from the event loop."""
            self.hass.async_create_task(self.coordinator.async_request_refresh())

        for delay in COMMAND_REFRESH_DELAYS:
            cancel = async_call_later(
                self.hass,
                delay,
                _request_refresh,
            )
            self.async_on_remove(cancel)
