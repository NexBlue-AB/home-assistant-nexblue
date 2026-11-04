"""NexBlue charger current limit control."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from nexblue_api import NexBlueError

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator

# Documented range for the cloud set_current_limit command.
MIN_CURRENT_LIMIT_A = 6
MAX_CURRENT_LIMIT_A = 32


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Add one current limit control per charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(NexBlueCurrentLimitNumber(coordinator, serial_number) for serial_number in coordinator.data)


class NexBlueCurrentLimitNumber(CoordinatorEntity[NexBlueDataUpdateCoordinator], NumberEntity):
    """Set the charger current limit through the documented cloud command.

    Only owner and installer accounts may change it. The charger still applies the
    lowest of this value, the circuit fuse, the cable rating and load balancing.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "current_limit"
    _attr_name = "Current limit"
    _attr_icon = "mdi:current-ac"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = MIN_CURRENT_LIMIT_A
    _attr_native_step = 1

    def __init__(self, coordinator: NexBlueDataUpdateCoordinator, serial_number: str) -> None:
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_current_limit"
        self._attr_device_info = DeviceInfo(identifiers={("nexblue", serial_number)}, name=f"NexBlue {serial_number}", manufacturer="NexBlue")

    @property
    def available(self) -> bool:
        """Return false when this charger is listed but currently unreachable."""
        return self.coordinator.data.get(self._serial_number) is not None

    @property
    def native_max_value(self) -> float:
        """The API rejects limits above the circuit fuse, so cap the slider there."""
        status = self.coordinator.data.get(self._serial_number)
        if status is not None and status.circuit_fuse_a:
            return max(MIN_CURRENT_LIMIT_A, min(MAX_CURRENT_LIMIT_A, status.circuit_fuse_a))
        return MAX_CURRENT_LIMIT_A

    @property
    def native_value(self) -> float | None:
        status = self.coordinator.data.get(self._serial_number)
        return None if status is None else status.current_limit_a

    async def async_set_native_value(self, value: float) -> None:
        """Send the new limit, then refresh so the value reflects the charger."""
        try:
            await self.coordinator.client.async_set_current_limit(self._serial_number, int(value))
        except (NexBlueError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
