"""SQLite connection management + schema.

A fresh connection per operation (check_same_thread=False) keeps things simple and
thread-safe under FastAPI's threadpool. Schema is created idempotently on every
connect, so there's no import-time side effect and module-scope `TestClient(app)`
works without a lifespan handler. The DB path is read from the environment each
call (default ./data/tasks.db), which lets tests point at a throwaway file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         TEXT PRIMARY KEY,
    question   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL,
    answer     TEXT NOT NULL,
    steps_used INTEGER NOT NULL,
    citations  TEXT NOT NULL,
    trace      TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    path = settings.db_path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def reset_for_tests(path: str) -> None:
    """Drop the tasks table at `path` so a test starts from a clean slate."""
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE IF EXISTS tasks")
        conn.commit()
    finally:
        conn.close()
