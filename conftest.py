"""Root conftest.

Ensures the repo root is importable (so `from app...` and `from eval...` resolve
no matter where pytest is invoked from) and gives every test an isolated,
throwaway SQLite database so `GET /api/tasks` never sees state from a prior run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at a fresh SQLite file under pytest's tmp_path."""
    db_path = tmp_path / "test_tasks.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    # DB_PATH is read fresh on every connect (config.db_path is a property), so
    # pointing it at a fresh tmp file per test is what gives isolation. The reset
    # below just drops the table in case a test ever reuses a path.
    from app.storage import db

    db.reset_for_tests(str(db_path))
    yield


@pytest.fixture
def client():
    """A TestClient wired to the deterministic ReplayModel (never Ollama)."""
    from fastapi.testclient import TestClient

    from app.deps import get_model
    from app.main import app
    from app.model.replay import ReplayModel

    app.dependency_overrides[get_model] = lambda: ReplayModel()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
