"""Dependency wiring.

`get_model` is a FastAPI dependency so tests can override it
(`app.dependency_overrides[get_model] = ...`). It defaults to the deterministic
ReplayModel; only MODEL_MODE=live selects the Ollama-backed LiveModel. That's why
`make run` and `make test` never need a model server.
"""

from __future__ import annotations

from app.config import settings
from app.model.base import ModelClient


def build_model() -> ModelClient:
    if settings.model_mode == "live":
        from app.model.live import LiveModel

        return LiveModel()
    from app.model.replay import ReplayModel

    return ReplayModel()


def get_model() -> ModelClient:  # FastAPI dependency
    return build_model()
