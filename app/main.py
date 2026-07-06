"""FastAPI application entrypoint.

    uvicorn app.main:app --reload

Runs fully offline by default (MODEL_MODE=replay).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.config import settings

app = FastAPI(title="Grounded Doc-QA Agent", version="0.1.0")
register_error_handlers(app)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Readiness probe. Reports which model backend is active."""
    return {"status": "ok", "model_mode": settings.model_mode}
