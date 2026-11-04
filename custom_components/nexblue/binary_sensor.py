"""Read-only NexBlue charger binary sensors derived from the charging state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator

# Charging state 2 means the charger is delivering energy.
CHARGING_STATES = {2}
# Every state except 0 (connect cable to charge) and 4 (charging unavailable) has a car plugged in.
VEHICLE_CONNECTED_STATES = {1, 2, 3, 5, 6, 7}


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Add charging and vehicle connected sensors per charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for serial_number in coordinator.data
        for entity in (
            NexBlueStateBinarySensor(coordinator, serial_number, "charging"),
            NexBlueStateBinarySensor(coordinator, serial_number, "vehicle_connected"),
        )
    )


class NexBlueStateBinarySensor(CoordinatorEntity[NexBlueDataUpdateCoordinator], BinarySensorEntity):
    """Expose charging state groups as on/off entities for automations."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NexBlueDataUpdateCoordinator, serial_number: str, metric: str) -> None:
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._metric = metric
        self._attr_unique_id = f"{serial_number}_{metric}"
        self._attr_translation_key = metric
        self._attr_device_info = DeviceInfo(identifiers={("nexblue", serial_number)}, name=f"NexBlue {serial_number}", manufacturer="NexBlue")
        if metric == "charging":
            self._attr_name = "Charging"
            self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
            self._states = CHARGING_STATES
        else:
            self._attr_name = "Vehicle connected"
            self._attr_device_class = BinarySensorDeviceClass.PLUG
            self._states = VEHICLE_CONNECTED_STATES

    @property
    def available(self) -> bool:
        """Return false when this charger is listed but currently unreachable."""
        return self.coordinator.data.get(self._serial_number) is not None

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get(self._serial_number)
        if status is None:
            return None
        return status.charging_state in self._states
