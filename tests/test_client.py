"""Library tests cover token handling and non-sensitive error handling."""

import unittest

from nexblue_api import (
    NexBlueAuthError,
    NexBlueClient,
    NexBlueDeviceOfflineError,
    NexBlueRateLimitError,
)


class Response:
    def __init__(self, status, data):
        self.status = status
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._data


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class NexBlueClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_login_keeps_refresh_token_not_password(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
        ])
        client = NexBlueClient(session, "https://example.test")

        token = await client.async_login("user@example.test", "secret-password")

        self.assertEqual(token.refresh_token, "refresh")
        self.assertEqual(client.refresh_token, "refresh")
        self.assertNotIn("secret-password", repr(client.__dict__))
        self.assertEqual(session.calls[0][1], "https://example.test/openapi/account/login")

    async def test_refresh_token_sets_bearer_for_status_requests(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh2", "expires_in": 3600}),
            Response(200, {"data": [{"serial_number": "NB1"}]}),
            Response(200, {"charging_state": "charging", "power": 7.2, "lifetime_energy": 11.3, "current_list": [16], "voltage_list": [230]}),
        ])
        client = NexBlueClient(session, "https://example.test")

        token = await client.async_refresh_access_token("refresh1")
        chargers = await client.async_list_chargers()
        status = await client.async_get_charger_status(chargers[0].serial_number)

        self.assertEqual(token.refresh_token, "refresh2")
        self.assertEqual(status.power_kw, 7.2)
        self.assertEqual(session.calls[1][2]["headers"], {"Authorization": "Bearer access"})

    async def test_unauthorized_request_does_not_retry_in_a_loop(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
            Response(401, {}),
        ])
        client = NexBlueClient(session, "https://example.test")
        await client.async_refresh_access_token("refresh")

        with self.assertRaises(NexBlueAuthError):
            await client.async_list_chargers()
        self.assertEqual(len(session.calls), 2)

    async def test_rate_limit_is_safe_exception(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
            Response(429, {}),
        ])
        client = NexBlueClient(session, "https://example.test")
        await client.async_refresh_access_token("refresh")

        with self.assertRaises(NexBlueRateLimitError):
            await client.async_list_chargers()

    async def test_start_command_uses_documented_endpoint(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
            Response(200, {"result": 0}),
        ])
        client = NexBlueClient(session, "https://example.test")
        await client.async_refresh_access_token("refresh")

        await client.async_start_charging("NB1")

        self.assertEqual(session.calls[1][0], "POST")
        self.assertTrue(session.calls[1][1].endswith("/openapi/chargers/NB1/cmd/start_charging"))
        self.assertEqual(session.calls[1][2]["json"], {})

    async def test_rejected_command_reports_user_safe_reason(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
            Response(200, {"result": 5}),
        ])
        client = NexBlueClient(session, "https://example.test")
        await client.async_refresh_access_token("refresh")

        with self.assertRaisesRegex(Exception, "occupied by another user"):
            await client.async_start_charging("NB1")

    async def test_http_command_error_reports_safe_code(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
            Response(400, {"code": 3001, "message": "Detailed backend message"}),
        ])
        client = NexBlueClient(session, "https://example.test")
        await client.async_refresh_access_token("refresh")

        with self.assertRaisesRegex(Exception, "code 3001"):
            await client.async_start_charging("NB1")

    async def test_device_offline_error_is_single_device_exception(self):
        session = Session([
            Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
            Response(400, {"code": 2105, "message": "NB1 device offline, command can not be sent"}),
        ])
        client = NexBlueClient(session, "https://example.test")
        await client.async_refresh_access_token("refresh")

        with self.assertRaises(NexBlueDeviceOfflineError):
            await client.async_get_charger_status("NB1")
