"""Read-only NexBlue charger sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Create one consistent read-only entity set per charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for serial_number in coordinator.data
        for entity in (
            NexBlueStatusSensor(coordinator, serial_number, "charging_state"),
            NexBlueStatusSensor(coordinator, serial_number, "power"),
            NexBlueStatusSensor(coordinator, serial_number, "lifetime_energy"),
            *(NexBlueStatusSensor(coordinator, serial_number, "current", phase) for phase in range(3)),
            *(NexBlueStatusSensor(coordinator, serial_number, "voltage", phase) for phase in range(3)),
        )
    )


class NexBlueStatusSensor(CoordinatorEntity[NexBlueDataUpdateCoordinator], SensorEntity):
    """Expose normalized charger telemetry without control capability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NexBlueDataUpdateCoordinator, serial_number: str, metric: str, phase: int | None = None) -> None:
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._metric = metric
        self._phase = phase
        suffix = f"_{phase + 1}" if phase is not None else ""
        self._attr_unique_id = f"{serial_number}_{metric}{suffix}"
        self._attr_translation_key = f"{metric}{suffix}"
        self._attr_name = _sensor_name(metric, phase)
        self._attr_device_info = DeviceInfo(identifiers={("nexblue", serial_number)}, name=f"NexBlue {serial_number}", manufacturer="NexBlue")
        if metric == "power":
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "lifetime_energy":
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif metric == "current":
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "voltage":
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        status = self.coordinator.data[self._serial_number]
        if self._metric == "charging_state":
            return str(status.charging_state)
        if self._metric == "power":
            return status.power_kw
        if self._metric == "lifetime_energy":
            return status.lifetime_energy_kwh
        values = status.current_a if self._metric == "current" else status.voltage_v
        return values[self._phase] if self._phase is not None and len(values) > self._phase else None


def _sensor_name(metric: str, phase: int | None) -> str:
    """Return stable names that do not depend on frontend translation cache."""
    if metric == "charging_state":
        return "Charging state"
    if metric == "power":
        return "Charging power"
    if metric == "lifetime_energy":
        return "Lifetime energy"
    if metric == "current" and phase is not None:
        return f"Current phase {phase + 1}"
    if metric == "voltage" and phase is not None:
        return f"Voltage phase {phase + 1}"
    return metric
