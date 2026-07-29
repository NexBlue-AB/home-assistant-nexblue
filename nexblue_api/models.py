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
    charging_state: str | int
    power_kw: float
    lifetime_energy_kwh: float
    current_a: tuple[float, ...]
    voltage_v: tuple[int, ...]

    @classmethod
    def from_api(cls, serial_number: str, payload: dict[str, Any]) -> "ChargerStatus":
        return cls(
            serial_number=serial_number,
            charging_state=payload["charging_state"],
            power_kw=float(payload["power"]),
            lifetime_energy_kwh=float(payload["lifetime_energy"]),
            current_a=tuple(float(value) for value in payload.get("current_list", [])),
            voltage_v=tuple(int(value) for value in payload.get("voltage_list", [])),
        )
