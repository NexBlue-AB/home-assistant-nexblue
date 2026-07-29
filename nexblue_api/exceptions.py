"""Exceptions deliberately safe to show in user-facing Home Assistant flows."""


class NexBlueError(Exception):
    """Base client error."""


class NexBlueAuthError(NexBlueError):
    """Credentials or refresh token are no longer valid."""


class NexBlueConnectionError(NexBlueError):
    """The NexBlue API cannot currently be reached."""


class NexBlueRateLimitError(NexBlueError):
    """The NexBlue API asked the client to slow down."""


class NexBlueCommandError(NexBlueError):
    """A charger rejected a requested command."""


class NexBlueDeviceOfflineError(NexBlueCommandError):
    """A single charger is offline and cannot answer a command/status request."""
