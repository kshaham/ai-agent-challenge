"""Deterministic, offline model backend — the default everywhere.

Reads a previously recorded response for the exact request. This is what makes
the whole service testable and the eval suite reproducible with no GPU, no API
key, and no network. A miss is loud and actionable rather than silently falling
back to a live call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.model.base import ModelClient, ModelMessage, ModelResponse, ToolSpec
from app.model.hashing import canonical_request_key
from app.paths import FIXTURES_DIR


class FixtureMissingError(RuntimeError):
    """No recorded response exists for a request.

    Almost always means the loop or the system prompt changed (which changes the
    messages, hence the hash). Re-record with `make record` against a live model.
    """


class ReplayModel(ModelClient):
    def __init__(self, fixtures_dir: Optional[Path] = None) -> None:
        self.dir = fixtures_dir or FIXTURES_DIR

    def chat(
        self,
        messages: list[ModelMessage],
        *,
        tools: Optional[list[ToolSpec]] = None,
        format: Optional[dict[str, Any]] = None,
    ) -> ModelResponse:
        key = canonical_request_key(messages, tools, format)
        path = self.dir / f"{key}.json"
        if not path.exists():
            last = messages[-1].content if messages else None
            preview = (last or "")[:160]
            raise FixtureMissingError(
                f"No recorded model response for request hash {key}.\n"
                f"This usually means the agent loop or the system prompt changed.\n"
                f"Re-record fixtures against a live model with:  make record\n"
                f"(last message preview: {preview!r})"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return ModelResponse(**data["response"])
