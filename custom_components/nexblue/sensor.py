"""Read-only NexBlue charger sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator

DIAGNOSTIC_METRICS = {
    "is_lock",
    "cable_lock_mode",
    "is_disable",
    "access_level",
    "phase_charging",
    "cable_current_limit",
    "circuit_fuse",
    "network_status",
    "brightness",
    "protocol_version",
}


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Create one consistent read-only entity set per charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for serial_number in coordinator.data
        for entity in (
            NexBlueStatusSensor(coordinator, serial_number, "charging_state"),
            NexBlueStatusSensor(coordinator, serial_number, "is_lock"),
            NexBlueStatusSensor(coordinator, serial_number, "cable_lock_mode"),
            NexBlueStatusSensor(coordinator, serial_number, "is_disable"),
            NexBlueStatusSensor(coordinator, serial_number, "access_level"),
            NexBlueStatusSensor(coordinator, serial_number, "phase_charging"),
            NexBlueStatusSensor(coordinator, serial_number, "power"),
            NexBlueStatusSensor(coordinator, serial_number, "energy"),
            NexBlueStatusSensor(coordinator, serial_number, "lifetime_energy"),
            NexBlueStatusSensor(coordinator, serial_number, "current_limit"),
            NexBlueStatusSensor(coordinator, serial_number, "cable_current_limit"),
            NexBlueStatusSensor(coordinator, serial_number, "circuit_fuse"),
            *(NexBlueStatusSensor(coordinator, serial_number, "current", phase) for phase in range(3)),
            *(NexBlueStatusSensor(coordinator, serial_number, "voltage", phase) for phase in range(3)),
            NexBlueStatusSensor(coordinator, serial_number, "network_status"),
            # Keep uk_reg parsed in the API model, but do not expose it to users yet.
            # NexBlueStatusSensor(coordinator, serial_number, "uk_reg"),
            NexBlueStatusSensor(coordinator, serial_number, "brightness"),
            NexBlueStatusSensor(coordinator, serial_number, "protocol_version"),
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
        if metric in DIAGNOSTIC_METRICS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if metric == "power":
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric in {"energy", "lifetime_energy"}:
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif metric in {"current", "current_limit", "cable_current_limit", "circuit_fuse"}:
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "voltage":
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "brightness":
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Return false when this charger is listed but currently unreachable."""
        return self.coordinator.data.get(self._serial_number) is not None

    @property
    def native_value(self):
        status = self.coordinator.data.get(self._serial_number)
        if status is None:
            return None
        if self._metric == "charging_state":
            return CHARGING_STATE_MAP.get(status.charging_state, f"Unknown ({status.charging_state})")
        if self._metric == "network_status":
            return NETWORK_STATUS_MAP.get(status.network_status, f"Unknown ({status.network_status})")
        if self._metric == "is_disable":
            return _bool_text(status.is_disable, true_text="Disabled", false_text="Enabled")
        if self._metric == "is_lock":
            return _bool_text(status.is_lock, true_text="Locked", false_text="Unlocked")
        if self._metric == "power":
            return status.power_kw
        if self._metric == "energy":
            return status.energy_kwh
        if self._metric == "lifetime_energy":
            return status.lifetime_energy_kwh
        if self._metric == "current_limit":
            return status.current_limit_a
        if self._metric == "cable_current_limit":
            return status.cable_current_limit_a
        if self._metric == "circuit_fuse":
            return status.circuit_fuse_a
        if self._metric == "cable_lock_mode":
            return CABLE_LOCK_MODE_MAP.get(status.cable_lock_mode, f"Unknown ({status.cable_lock_mode})")
        if self._metric == "access_level":
            return ACCESS_LEVEL_MAP.get(status.access_level, f"Unknown ({status.access_level})")
        if self._metric == "phase_charging":
            return PHASE_CHARGING_MAP.get(status.phase_charging, f"Unknown ({status.phase_charging})")
        if self._metric == "brightness":
            return status.brightness_percent
        if self._metric == "uk_reg":
            return _bool_text(status.uk_reg, true_text="Enabled", false_text="Disabled")
        if self._metric == "protocol_version":
            return status.protocol_version
        values = status.current_a if self._metric == "current" else status.voltage_v
        return values[self._phase] if self._phase is not None and len(values) > self._phase else None


CHARGING_STATE_MAP = {
    0: "Free",
    1: "Car connected",
    2: "Charging",
    3: "Finishing",
    4: "Error",
    5: "Load balancing waiting",
    6: "Delayed waiting",
    7: "Car response waiting",
}

NETWORK_STATUS_MAP = {
    0: "None",
    1: "Wi-Fi",
    2: "Modem",
    3: "Ethernet",
}

CABLE_LOCK_MODE_MAP = {
    0: "Lock while charging",
    1: "Always locked",
}

ACCESS_LEVEL_MAP = {
    0: "Authorized users only",
    1: "No restrictions",
}

PHASE_CHARGING_MAP = {
    0: "Three-phase",
    1: "Single-phase",
}


def _bool_text(value: bool | None, *, true_text: str, false_text: str) -> str | None:
    """Return a friendly text value for an optional boolean."""
    if value is None:
        return None
    return true_text if value else false_text


def _sensor_name(metric: str, phase: int | None) -> str:
    """Return stable names that do not depend on frontend translation cache."""
    if metric == "charging_state":
        return "Charging state"
    if metric == "network_status":
        return "Network status"
    if metric == "is_disable":
        return "Availability"
    if metric == "is_lock":
        return "Cable lock state"
    if metric == "power":
        return "Charging power"
    if metric == "energy":
        return "Session energy"
    if metric == "lifetime_energy":
        return "Lifetime energy"
    if metric == "current_limit":
        return "Current limit"
    if metric == "cable_current_limit":
        return "Cable current limit"
    if metric == "circuit_fuse":
        return "Circuit fuse"
    if metric == "cable_lock_mode":
        return "Cable lock mode"
    if metric == "access_level":
        return "Access level"
    if metric == "phase_charging":
        return "Phase charging"
    if metric == "brightness":
        return "LED brightness"
    if metric == "uk_reg":
        return "UK regulation mode"
    if metric == "protocol_version":
        return "Protocol version"
    if metric == "current" and phase is not None:
        return f"Current L{phase + 1}"
    if metric == "voltage" and phase is not None:
        return f"Voltage L{phase + 1}"
    return metric
