"""Custom exceptions. Every AppError carries a message that is safe to show to the user."""


class AppError(Exception):
    """Base class for all expected, user-facing errors."""


class ValidationError(AppError):
    """Input failed validation (empty field, bad number, duplicate value...)."""


class AuthenticationError(AppError):
    """Login failed or the account is temporarily locked."""


class PermissionDenied(AppError):
    """The signed-in user's role is not allowed to do this."""


class NotFoundError(AppError):
    """A requested record does not exist."""
