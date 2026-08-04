"""Config flow for NexBlue end-user token authentication."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from nexblue_api import NexBlueAuthError, NexBlueClient, NexBlueConnectionError, NexBlueError

from .const import (
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_USERNAME,
    DEFAULT_API_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class NexBlueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Authenticate a NexBlue end-user and store credentials for token recovery."""

    VERSION = 1
    logger = _LOGGER

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle initial setup from the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_base_url = DEFAULT_API_URL
            refresh_token, error = await self._async_validate_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], api_base_url
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(f"{api_base_url}:{user_input[CONF_USERNAME]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NexBlue ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_API_BASE_URL: api_base_url,
                    },
                )

        return self.async_show_form(step_id="user", data_schema=_AUTH_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Ask for the password when automatic credential recovery fails."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate a fresh password and replace the stored refresh token."""
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_entry_missing")

        errors: dict[str, str] = {}
        username = self._reauth_entry.data[CONF_USERNAME]
        if user_input is not None:
            api_base_url = self._reauth_entry.data.get(CONF_API_BASE_URL, DEFAULT_API_URL)
            refresh_token, error = await self._async_validate_login(
                username, user_input[CONF_PASSWORD], api_base_url
            )
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={CONF_USERNAME: username},
        )

    async def _async_validate_login(
        self, username: str, password: str, api_base_url: str
    ) -> tuple[str | None, str | None]:
        """Return a refresh token, or an error key safe for UI display."""
        client = NexBlueClient(async_get_clientsession(self.hass), api_base_url)
        try:
            token = await client.async_login(username, password)
        except NexBlueAuthError:
            return None, "invalid_auth"
        except NexBlueConnectionError:
            return None, "cannot_connect"
        except NexBlueError:
            return None, "unknown"
        if not token.refresh_token:
            return None, "invalid_auth"
        return token.refresh_token, None


_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
