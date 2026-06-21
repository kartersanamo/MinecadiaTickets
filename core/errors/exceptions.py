"""Application exceptions with safe user-facing messages."""

from __future__ import annotations

from core.errors.error_types import (
    CHANNEL_HISTORY_ERRORS,
    CONFIG_IO_ERRORS,
    DISCORD_API_ERRORS,
    DM_BROADCAST_ERRORS,
    MESSAGE_CONTENT_ERRORS,
    UI_CALLBACK_ERRORS,
)

__all__ = [
    "CHANNEL_HISTORY_ERRORS",
    "CONFIG_IO_ERRORS",
    "DISCORD_API_ERRORS",
    "DM_BROADCAST_ERRORS",
    "MESSAGE_CONTENT_ERRORS",
    "UI_CALLBACK_ERRORS",
    "UserFacingError",
    "PermissionDenied",
    "NotConfigured",
    "ExternalServiceError",
]


class UserFacingError(Exception):
    """Raised when the user should see a specific message (not a stack trace)."""

    def __init__(self, message: str, *, log_message: str | None = None):
        super().__init__(message)
        self.user_message = message
        self.log_message = log_message or message


class PermissionDenied(UserFacingError):
    def __init__(self, message: str = "You don't have permission to do that."):
        super().__init__(message)


class NotConfigured(UserFacingError):
    def __init__(self, message: str = "This feature is not configured. Contact staff."):
        super().__init__(message)


class ExternalServiceError(UserFacingError):
    def __init__(
        self,
        message: str = "An external service is unavailable. Please try again later.",
        *,
        log_message: str | None = None,
    ):
        super().__init__(message, log_message=log_message)
