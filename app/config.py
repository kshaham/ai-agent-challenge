"""Runtime configuration, read from the environment.

Defaults are chosen so the service runs fully offline with no .env file:
MODEL_MODE=replay means the deterministic recorded-fixture backend, so `make run`
and `make test` never touch a model or the network. If a `.env` file exists at
the repo root it is loaded on import (without overriding variables already set in
the shell), so the documented "copy .env.example to .env" workflow works.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.paths import DATA_DIR, ROOT


def _load_dotenv(env_path: object = None) -> None:
    """Minimal .env loader (no dependency): KEY=VALUE lines at the repo root fill
    in variables not already set in the environment (shell/inline wins)."""
    path = env_path if env_path is not None else (ROOT / ".env")
    try:
        text = path.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    except (OSError, UnicodeDecodeError):
        # unreadable OR not valid UTF-8 (e.g. a Windows UTF-16 save): skip it and
        # fall back to shell env + offline defaults, never crash every import.
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    @property
    def model_mode(self) -> str:
        return os.getenv("MODEL_MODE", "replay").lower()

    # Which live backend to use when MODEL_MODE=live: "ollama" (default, local)
    # or "openai" (any OpenAI-compatible endpoint: Groq, OpenRouter, etc.).
    @property
    def llm_backend(self) -> str:
        return os.getenv("LLM_BACKEND", "ollama").lower()

    @property
    def ollama_base_url(self) -> str:
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def ollama_model(self) -> str:
        return os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    @property
    def openai_base_url(self) -> str:
        return os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")

    @property
    def openai_api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def openai_model(self) -> str:
        return os.getenv("OPENAI_MODEL", "llama-3.1-8b-instant")

    @property
    def db_path(self) -> str:
        return os.getenv("DB_PATH") or str(DATA_DIR / "tasks.db")


settings = Settings()
