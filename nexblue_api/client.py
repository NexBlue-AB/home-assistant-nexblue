"""Async NexBlue OpenAPI client."""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import TYPE_CHECKING, Any

try:
    from aiohttp import ClientError
except ModuleNotFoundError:  # pragma: no cover - supports static checks without optional runtime deps
    ClientError = OSError

if TYPE_CHECKING:
    from aiohttp import ClientSession

from .exceptions import (
    NexBlueAuthError,
    NexBlueCommandError,
    NexBlueConnectionError,
    NexBlueDeviceOfflineError,
    NexBlueError,
    NexBlueRateLimitError,
)
from .models import Charger, ChargerStatus
from .models import TokenBundle

CHARGING_CONTROL_RESULT_MESSAGES = {
    1: "The charger is not in a state that allows this command",
    2: "You do not have permission to control this charger",
    3: "The charger RCD check failed",
    4: "The charger is disabled",
    5: "The charger is currently occupied by another user",
}


class NexBlueClient:
    """Use one API session for a Home Assistant config entry."""

    def __init__(self, session: "ClientSession", base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_token_expires_at = 0.0

    @property
    def refresh_token(self) -> str | None:
        """Return the persisted credential; callers must never log it."""
        return self._refresh_token

    def set_access_token(self, access_token: str) -> None:
        """Set an access token managed by an external OAuth session."""
        self._access_token = access_token
        self._access_token_expires_at = 0.0

    async def async_login(self, username: str, password: str) -> TokenBundle:
        """Login with end-user credentials and keep only returned tokens."""
        payload = await self._async_request(
            "POST",
            "/openapi/account/login",
            json={"username": username, "password": password, "account_type": 0},
            authenticated=False,
        )
        token = TokenBundle.from_api(payload)
        self._store_token(token, fallback_refresh_token=None)
        return token

    async def async_refresh_access_token(self, refresh_token: str | None = None) -> TokenBundle:
        """Refresh the short-lived access token using a persisted refresh token."""
        token_value = refresh_token or self._refresh_token
        if not token_value:
            raise NexBlueAuthError("Refresh token is not available")
        payload = await self._async_request(
            "POST",
            "/openapi/account/refresh_token",
            json={"refresh_token": token_value, "account_type": 0},
            authenticated=False,
        )
        token = TokenBundle.from_api(payload)
        self._store_token(token, fallback_refresh_token=token_value)
        return token

    async def async_ensure_access_token(self, refresh_token: str) -> TokenBundle | None:
        """Refresh only when the current access token is missing or near expiry."""
        if self._access_token and time.monotonic() < self._access_token_expires_at:
            return None
        return await self.async_refresh_access_token(refresh_token)

    async def async_list_chargers(self) -> list[Charger]:
        """Return all chargers accessible to the end user."""
        payload = await self._async_authenticated_request("GET", "/openapi/chargers")
        return [Charger.from_api(item) for item in payload.get("data", [])]

    async def async_get_charger_status(self, serial_number: str) -> ChargerStatus:
        """Return current read-only telemetry for one charger."""
        payload = await self._async_authenticated_request(
            "GET", f"/openapi/chargers/{serial_number}/cmd/status"
        )
        return ChargerStatus.from_api(serial_number, payload)

    async def async_start_charging(self, serial_number: str) -> None:
        """Request charging start; command availability is enforced by the API/device."""
        await self._async_command(serial_number, "start_charging")

    async def async_stop_charging(self, serial_number: str) -> None:
        """Request charging stop; command availability is enforced by the API/device."""
        await self._async_command(serial_number, "stop_charging")

    async def _async_command(self, serial_number: str, command: str) -> None:
        payload = await self._async_request(
            "POST",
            f"/openapi/chargers/{serial_number}/cmd/{command}",
            json={},
            authenticated=True,
            command=True,
        )
        result = payload.get("result")
        if result not in (0, "success"):
            message = CHARGING_CONTROL_RESULT_MESSAGES.get(
                result, f"The charger rejected the command with result {result}"
            )
            raise NexBlueCommandError(message)

    async def _async_authenticated_request(self, method: str, path: str) -> dict[str, Any]:
        if not self._access_token:
            raise NexBlueAuthError("Access token is not available")
        return await self._async_request(method, path, authenticated=True)

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        authenticated: bool,
        command: bool = False,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token}"} if authenticated else None
        try:
            async with self._session.request(
                method, f"{self._base_url}{path}", json=json, headers=headers
            ) as response:
                if response.status in (401, 403):
                    raise NexBlueAuthError("Authentication failed")
                if response.status == 429:
                    raise NexBlueRateLimitError("NexBlue API rate limit reached")
                if response.status == 415:
                    raise NexBlueCommandError("The NexBlue API rejected the command format")
                if response.status >= 400:
                    error_payload = await _async_safe_json(response)
                    if error_payload.get("code") == 2105:
                        raise NexBlueDeviceOfflineError("NexBlue charger is offline")
                    if command:
                        raise NexBlueCommandError(
                            _command_http_error_message(response.status, error_payload)
                        )
                    raise NexBlueError(f"NexBlue API returned HTTP {response.status}")
                data = await response.json()
        except ClientError as err:
            raise NexBlueConnectionError("Cannot connect to NexBlue API") from err
        if not isinstance(data, dict):
            raise NexBlueError("NexBlue API returned an invalid response")
        return data

    def _store_token(self, token: TokenBundle, fallback_refresh_token: str | None) -> None:
        self._access_token = token.access_token
        self._refresh_token = token.refresh_token or fallback_refresh_token
        expires_in = max(token.expires_in - 60, 0)
        self._access_token_expires_at = time.monotonic() + expires_in


async def _async_safe_json(response: Any) -> dict[str, Any]:
    """Return an error response body when it is JSON, without exposing it."""
    try:
        data = await response.json()
    except (ClientError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _command_http_error_message(status: int, payload: Mapping[str, Any]) -> str:
    """Return a safe user-facing HTTP command error without exposing raw responses."""
    code = payload.get("code")
    if code is not None:
        return f"The NexBlue API rejected the command with code {code}"

    return f"The NexBlue API rejected the command with HTTP {status}"
