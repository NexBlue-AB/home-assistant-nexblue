"""Stable data models independent of Home Assistant."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenBundle:
    """Tokens returned by NexBlue; callers must persist only the refresh token."""

    access_token: str
    refresh_token: str | None
    expires_in: int

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "TokenBundle":
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=payload.get("refresh_token"),
            expires_in=int(payload.get("expires_in", 0)),
        )


@dataclass(frozen=True, slots=True)
class Charger:
    """A charger visible to the authenticated end user."""

    serial_number: str
    role: str | int | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Charger":
        return cls(serial_number=str(payload["serial_number"]), role=payload.get("role"))


@dataclass(frozen=True, slots=True)
class ChargerStatus:
    """Read-only charger telemetry normalized to API units (kW, kWh, A, V)."""

    serial_number: str
    protocol_version: str | None
    charging_state: str | int
    power_kw: float
    energy_kwh: float
    lifetime_energy_kwh: float
    is_lock: bool | None
    network_status: int | None
    is_disable: bool | None
    cable_current_limit_a: int | None
    circuit_fuse_a: int | None
    current_limit_a: int | None
    cable_lock_mode: int | None
    access_level: int | None
    phase_charging: int | None
    brightness_percent: int | None
    uk_reg: bool | None
    current_a: tuple[float, ...]
    voltage_v: tuple[int, ...]

    @classmethod
    def from_api(cls, serial_number: str, payload: dict[str, Any]) -> "ChargerStatus":
        return cls(
            serial_number=serial_number,
            protocol_version=_optional_str(payload.get("protocol_version")),
            charging_state=payload.get("charging_state"),
            power_kw=float(payload.get("power", 0)),
            energy_kwh=float(payload.get("energy", 0)),
            lifetime_energy_kwh=float(payload.get("lifetime_energy", 0)),
            is_lock=_optional_bool(payload.get("is_lock")),
            network_status=_optional_int(payload.get("network_status")),
            is_disable=_optional_bool(payload.get("is_disable")),
            cable_current_limit_a=_optional_int(payload.get("cable_current_limit")),
            circuit_fuse_a=_optional_int(payload.get("circuit_fuse")),
            current_limit_a=_optional_int(payload.get("current_limit")),
            cable_lock_mode=_optional_int(payload.get("cable_lock_mode")),
            access_level=_optional_int(payload.get("access_level")),
            phase_charging=_optional_int(payload.get("phase_charging")),
            brightness_percent=_optional_int(payload.get("brightness")),
            uk_reg=_optional_bool(payload.get("uk_reg")),
            current_a=tuple(float(value) for value in payload.get("current_list", [])),
            voltage_v=tuple(int(value) for value in payload.get("voltage_list", [])),
        )


def _optional_bool(value: Any) -> bool | None:
    """Return a bool when the API included one."""
    return value if isinstance(value, bool) else None


def _optional_int(value: Any) -> int | None:
    """Return an int when the API included an integer-like value."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    """Return a string when the API included a value."""
    return None if value is None else str(value)
