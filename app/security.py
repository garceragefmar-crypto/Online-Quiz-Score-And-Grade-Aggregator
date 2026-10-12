"""Password hashing helpers (PBKDF2-HMAC-SHA256 with a random per-user salt)."""
from __future__ import annotations

import hashlib
import hmac
import os

ITERATIONS = 120_000


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Return (salt_hex, hash_hex). A new random salt is made when none is given."""
    salt = os.urandom(16) if salt_hex is None else bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    _, digest = hash_password(password, salt_hex)
    return hmac.compare_digest(digest, expected_hash_hex)
