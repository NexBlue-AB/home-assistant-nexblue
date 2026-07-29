"""One bounded poll per integration update interval."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from nexblue_api import NexBlueAuthError, NexBlueClient, NexBlueConnectionError, NexBlueRateLimitError
from nexblue_api.models import ChargerStatus

from .const import CONF_REFRESH_TOKEN, DOMAIN, UPDATE_INTERVAL


class NexBlueDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ChargerStatus]]):
    """Fetch all charger telemetry using a single coordinated update."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NexBlueClient,
    ) -> None:
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.config_entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, ChargerStatus]:
        try:
            token = await self.client.async_ensure_access_token(
                self.config_entry.data[CONF_REFRESH_TOKEN]
            )
            if token and token.refresh_token and token.refresh_token != self.config_entry.data[CONF_REFRESH_TOKEN]:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_REFRESH_TOKEN: token.refresh_token},
                )
            chargers = await self.client.async_list_chargers()
            data = {charger.serial_number: await self.client.async_get_charger_status(charger.serial_number) for charger in chargers}
        except NexBlueAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (NexBlueConnectionError, NexBlueRateLimitError) as err:
            raise UpdateFailed("Unable to update NexBlue charger data") from err

        return data
