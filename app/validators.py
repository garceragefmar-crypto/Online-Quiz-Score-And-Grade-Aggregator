"""Small, reusable input validators. All raise ValidationError with a friendly message."""
import math
import re

from .errors import ValidationError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME = re.compile(r"^[A-Za-z0-9._-]{3,30}$")


def require_text(value, field: str, max_len: int = 100) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_len:
        raise ValidationError(f"{field} must be at most {max_len} characters.")
    return text


def optional_text(value, field: str, max_len: int = 100) -> str:
    text = (value or "").strip()
    if len(text) > max_len:
        raise ValidationError(f"{field} must be at most {max_len} characters.")
    return text


def validate_email(value) -> str:
    text = (value or "").strip()
    if text and not _EMAIL.match(text):
        raise ValidationError("Email address is not valid.")
    return text


def parse_number(value, field: str) -> float:
    try:
        number = float(str(value).strip())
    except ValueError:
        raise ValidationError(f"{field} must be a number.") from None
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be a finite number.")
    return number


def validate_username(value) -> str:
    text = (value or "").strip()
    if not _USERNAME.match(text):
        raise ValidationError(
            "Username must be 3-30 characters: letters, digits, dot, dash or underscore."
        )
    return text


def validate_password(value) -> str:
    if not value or len(value) < 6:
        raise ValidationError("Password must be at least 6 characters.")
    return value
