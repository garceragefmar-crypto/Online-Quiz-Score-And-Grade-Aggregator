"""Authentication and user-account management."""
from __future__ import annotations

import time

from .database import DatabaseConnection
from .errors import AuthenticationError, NotFoundError, ValidationError
from .models import Perm, ROLE_CLASSES, User
from .security import hash_password, verify_password
from . import validators as v


class AuthManager:
    MAX_ATTEMPTS = 5
    LOCK_SECONDS = 30

    def __init__(self, db: DatabaseConnection):
        self._db = db
        self._failures: dict[str, tuple[int, float]] = {}  # username -> (count, locked_until)

    # ------------------------------------------------------------- login
    def login(self, username: str, password: str) -> User:
        key = (username or "").strip().lower()
        if not key or not password:
            raise AuthenticationError("Enter your username and password.")
        self._check_lock(key)
        row = self._db.query_one("SELECT * FROM users WHERE username = ?", (key,))
        if row is None or not verify_password(password, row["salt"], row["password_hash"]):
            self._register_failure(key)
            raise AuthenticationError("Invalid username or password.")
        self._failures.pop(key, None)
        return User.from_row(row)

    def _check_lock(self, key: str) -> None:
        count, locked_until = self._failures.get(key, (0, 0.0))
        remaining = locked_until - time.monotonic()
        if remaining > 0:
            raise AuthenticationError(f"Too many failed attempts. Try again in {int(remaining) + 1}s.")

    def _register_failure(self, key: str) -> None:
        count, _ = self._failures.get(key, (0, 0.0))
        count += 1
        locked_until = time.monotonic() + self.LOCK_SECONDS if count >= self.MAX_ATTEMPTS else 0.0
        self._failures[key] = (0 if locked_until else count, locked_until)

    # ------------------------------------------------------------- accounts
    def list_users(self, actor: User, role: str | None = None) -> list[dict]:
        actor.require(Perm.MANAGE_USERS)
        sql = ("SELECT u.id, u.username, u.full_name, u.role, u.student_id, "
               "s.student_no AS student_no FROM users u "
               "LEFT JOIN students s ON s.id = u.student_id")
        params: list = []
        if role:
            sql += " WHERE u.role = ?"
            params.append(role)
        sql += " ORDER BY u.role, u.username"
        return [dict(r) for r in self._db.query(sql, params)]

    def create_user(self, actor: User, username: str, full_name: str, role: str,
                    password: str, student_id: int | None = None) -> int:
        actor.require(Perm.MANAGE_USERS)
        username = v.validate_username(username)
        full_name = v.require_text(full_name, "Full name")
        v.validate_password(password)
        if role not in ROLE_CLASSES:
            raise ValidationError("Choose a valid role.")
        if role == "student":
            if not student_id:
                raise ValidationError("A student account must be linked to a student record.")
        else:
            student_id = None
        salt, digest = hash_password(password)
        return self._db.execute(
            "INSERT INTO users (username, full_name, role, salt, password_hash, student_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username.lower(), full_name, role, salt, digest, student_id))

    def reset_password(self, actor: User, user_id: int, new_password: str) -> None:
        actor.require(Perm.MANAGE_USERS)
        v.validate_password(new_password)
        if self._db.query_one("SELECT 1 FROM users WHERE id = ?", (user_id,)) is None:
            raise NotFoundError("User not found.")
        salt, digest = hash_password(new_password)
        self._db.execute("UPDATE users SET salt = ?, password_hash = ? WHERE id = ?",
                         (salt, digest, user_id))

    def delete_user(self, actor: User, user_id: int) -> None:
        actor.require(Perm.MANAGE_USERS)
        if user_id == actor.id:
            raise ValidationError("You cannot delete the account you are signed in with.")
        row = self._db.query_one("SELECT role FROM users WHERE id = ?", (user_id,))
        if row is None:
            raise NotFoundError("User not found.")
        if row["role"] == "admin":
            admins = self._db.query_one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
            if admins <= 1:
                raise ValidationError("At least one administrator account must remain.")
        self._db.execute("DELETE FROM users WHERE id = ?", (user_id,))
