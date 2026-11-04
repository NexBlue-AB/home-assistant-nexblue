"""One bounded poll per integration update interval."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from nexblue_api import (
    NexBlueAuthError,
    NexBlueClient,
    NexBlueConnectionError,
    NexBlueDeviceOfflineError,
    NexBlueError,
    NexBlueRateLimitError,
)
from nexblue_api.models import ChargerSession, ChargerStatus

from .const import (
    CONF_REFRESH_TOKEN,
    CONF_USERNAME,
    DOMAIN,
    SESSION_LOOKBACK,
    SESSION_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class NexBlueDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ChargerStatus | None]]):
    """Fetch all charger telemetry using a single coordinated update."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NexBlueClient,
    ) -> None:
        super().__init__(hass, logger=_LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.config_entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, ChargerStatus | None]:
        try:
            await self._async_ensure_authorized()
            chargers = await self.client.async_list_chargers()
            data: dict[str, ChargerStatus | None] = {}
            for charger in chargers:
                try:
                    data[charger.serial_number] = await self.client.async_get_charger_status(
                        charger.serial_number
                    )
                except (NexBlueAuthError, NexBlueConnectionError, NexBlueRateLimitError):
                    raise
                except NexBlueDeviceOfflineError:
                    data[charger.serial_number] = None
                except NexBlueError:
                    data[charger.serial_number] = None
        except NexBlueAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (NexBlueConnectionError, NexBlueRateLimitError, NexBlueError) as err:
            raise UpdateFailed("Unable to update NexBlue charger data") from err

        return data

    async def _async_ensure_authorized(self) -> None:
        """Refresh the access token, falling back to the stored password once."""
        try:
            token = await self.client.async_ensure_access_token(
                self.config_entry.data[CONF_REFRESH_TOKEN]
            )
        except NexBlueAuthError:
            password = self.config_entry.data.get(CONF_PASSWORD)
            if not password:
                raise
            token = await self.client.async_login(
                self.config_entry.data[CONF_USERNAME],
                password,
            )

        if token and token.refresh_token and token.refresh_token != self.config_entry.data[CONF_REFRESH_TOKEN]:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_REFRESH_TOKEN: token.refresh_token},
            )


class NexBlueLastSessionCoordinator(DataUpdateCoordinator[dict[str, ChargerSession | None]]):
    """Fetch the most recent completed session per charger on a slower interval.

    Relies on the telemetry coordinator for the charger list and token refresh.
    A charger whose history cannot be read reports no session rather than failing
    the whole update.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NexBlueClient,
        status_coordinator: NexBlueDataUpdateCoordinator,
    ) -> None:
        super().__init__(
            hass, logger=_LOGGER, name=f"{DOMAIN}_last_session", update_interval=SESSION_UPDATE_INTERVAL
        )
        self.config_entry = entry
        self.client = client
        self._status_coordinator = status_coordinator

    async def _async_update_data(self) -> dict[str, ChargerSession | None]:
        now = dt_util.utcnow()
        data: dict[str, ChargerSession | None] = {}
        for serial_number in self._status_coordinator.data or {}:
            try:
                sessions = await self.client.async_list_sessions(serial_number, now - SESSION_LOOKBACK, now)
            except (NexBlueConnectionError, NexBlueRateLimitError) as err:
                raise UpdateFailed("Unable to update NexBlue session history") from err
            except NexBlueError:
                data[serial_number] = None
                continue
            ended = [session for session in sessions if session.end_time is not None]
            data[serial_number] = max(ended, key=lambda session: session.end_time, default=None)
        return data
