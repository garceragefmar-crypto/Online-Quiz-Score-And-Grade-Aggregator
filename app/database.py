"""SQLite connection wrapper and schema."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .errors import ValidationError

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "grades.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_no  TEXT NOT NULL UNIQUE,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT,
    course      TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'instructor', 'student')),
    salt          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    student_id    INTEGER REFERENCES students(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS modules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    instructor_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id  INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    max_score  REAL NOT NULL CHECK (max_score > 0),
    UNIQUE (module_id, title)
);

CREATE TABLE IF NOT EXISTS student_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    score         REAL NOT NULL CHECK (score >= 0),
    date_recorded TEXT NOT NULL DEFAULT (date('now')),
    UNIQUE (student_id, assessment_id)
);

CREATE INDEX IF NOT EXISTS idx_scores_student ON student_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_scores_assessment ON student_scores(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assess_module ON assessments(module_id);
"""


class DatabaseConnection:
    """Thin wrapper so the rest of the app never touches sqlite3 directly."""

    def __init__(self, path: str | Path = DB_PATH):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params=()) -> sqlite3.Row | None:
        return self._conn.execute(sql, tuple(params)).fetchone()

    def execute(self, sql: str, params=()) -> int:
        """Run INSERT/UPDATE/DELETE, commit, and return lastrowid."""
        try:
            cursor = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ValidationError(self._friendly(exc)) from None

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _friendly(exc: sqlite3.IntegrityError) -> str:
        text = str(exc).upper()
        if "UNIQUE" in text:
            return "That record already exists (duplicate value)."
        if "FOREIGN KEY" in text:
            return "A related record could not be found."
        if "CHECK" in text:
            return "A value is outside the allowed range."
        return "The data could not be saved."
