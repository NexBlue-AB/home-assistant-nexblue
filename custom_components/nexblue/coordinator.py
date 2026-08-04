"""One bounded poll per integration update interval."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from nexblue_api import (
    NexBlueAuthError,
    NexBlueClient,
    NexBlueConnectionError,
    NexBlueDeviceOfflineError,
    NexBlueError,
    NexBlueRateLimitError,
)
from nexblue_api.models import ChargerStatus

from .const import CONF_REFRESH_TOKEN, CONF_USERNAME, DOMAIN, UPDATE_INTERVAL

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
