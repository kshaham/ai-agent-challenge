"""Live model backend — used only when MODEL_MODE=live (to record fixtures via
`make record`). Never touched by the offline test/eval path.

Two wire protocols, selected by LLM_BACKEND:
  * "ollama"  (default) — a local Ollama server's native /api/chat.
  * "openai"  — any OpenAI-compatible /chat/completions endpoint (Groq, OpenRouter,
                etc.), so a candidate without a local GPU can record fixtures
                against a free-tier hosted model. Needs OPENAI_BASE_URL + OPENAI_API_KEY.

Either way, each response is recorded into fixtures/ keyed by the SAME canonical
hash ReplayModel reads (the hash is over the abstract, provider-agnostic request),
so a live recording replays deterministically afterwards. Writes are additive
(never overwrite an existing key) so a reverted prompt re-hits its old fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import settings
from app.model.base import ModelClient, ModelMessage, ModelResponse, ToolCall, ToolSpec
from app.model.hashing import canonical_request_key
from app.paths import FIXTURES_DIR


def _tools_payload(tools: Optional[list[ToolSpec]]) -> Optional[list[dict[str, Any]]]:
    # Ollama and OpenAI use the same tool shape.
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in tools
    ]


def _to_ollama_messages(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        msg: dict[str, Any] = {"role": m.role, "content": m.content or ""}
        if m.tool_calls:
            msg["tool_calls"] = [
                {"function": {"name": tc.name, "arguments": tc.arguments}} for tc in m.tool_calls
            ]
        out.append(msg)
    return out


def _to_openai_messages(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        msg: dict[str, Any] = {"role": m.role, "content": m.content or ""}
        if m.tool_calls:
            # OpenAI wants string-encoded arguments + an id per tool call.
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        out.append(msg)
    return out


def _coerce_args(args: Any) -> dict[str, Any]:
    """Tool-call arguments must be a dict. Degrade any other shape (a JSON string
    that parses to a non-object, or a direct non-dict) to {"_raw": ...} rather
    than crashing with a ValidationError, matching the handling of malformed args."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {"_raw": args}
    if not isinstance(args, dict):
        return {"_raw": args}
    return args


class LiveModel(ModelClient):
    def __init__(
        self,
        record: bool = True,
        fixtures_dir: Optional[Path] = None,
        backend: Optional[str] = None,
    ) -> None:
        self.backend = (backend or settings.llm_backend).lower()
        self.record = record
        self.dir = fixtures_dir or FIXTURES_DIR

    def chat(
        self,
        messages: list[ModelMessage],
        *,
        tools: Optional[list[ToolSpec]] = None,
        format: Optional[dict[str, Any]] = None,
    ) -> ModelResponse:
        if self.backend == "openai":
            result = self._chat_openai(messages, tools, format)
        else:
            result = self._chat_ollama(messages, tools, format)
        if self.record:
            self._record(messages, tools, format, result)
        return result

    def _chat_ollama(
        self,
        messages: list[ModelMessage],
        tools: Optional[list[ToolSpec]],
        format: Optional[dict[str, Any]],
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": settings.ollama_model,
            "messages": _to_ollama_messages(messages),
            "stream": False,
            "options": {"temperature": 0},
        }
        if _tools_payload(tools):
            payload["tools"] = _tools_payload(tools)
        if format:
            payload["format"] = format

        resp = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat", json=payload, timeout=120.0
        )
        resp.raise_for_status()
        body = resp.json()
        message = body.get("message", {})
        tool_calls = [
            ToolCall(id=f"call_{i}", name=tc.get("function", {}).get("name", ""),
                     arguments=_coerce_args(tc.get("function", {}).get("arguments", {})))
            for i, tc in enumerate(message.get("tool_calls") or [])
        ]
        return ModelResponse(content=message.get("content") or None, tool_calls=tool_calls, raw=body)

    def _chat_openai(
        self,
        messages: list[ModelMessage],
        tools: Optional[list[ToolSpec]],
        format: Optional[dict[str, Any]],
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": _to_openai_messages(messages),
            "temperature": 0,
        }
        if _tools_payload(tools):
            payload["tools"] = _tools_payload(tools)
        if format:
            # Forward the full JSON schema (as the Ollama path does) instead of
            # degrading to schema-less json_object mode — otherwise the exact
            # route we push at no-GPU candidates (Groq/OpenRouter) loses the
            # structured-output constraint and small models emit flakier tool
            # calls. `format` is already a JSON Schema dict, so wrap it in the
            # OpenAI-compatible json_schema envelope.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": format,
                    "strict": True,
                },
            }

        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        resp = httpx.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        resp.raise_for_status()
        body = resp.json()
        message = (body.get("choices") or [{}])[0].get("message", {})
        tool_calls = [
            ToolCall(id=tc.get("id") or f"call_{i}", name=tc.get("function", {}).get("name", ""),
                     arguments=_coerce_args(tc.get("function", {}).get("arguments", {})))
            for i, tc in enumerate(message.get("tool_calls") or [])
        ]
        return ModelResponse(content=message.get("content") or None, tool_calls=tool_calls, raw=body)

    def _record(
        self,
        messages: list[ModelMessage],
        tools: Optional[list[ToolSpec]],
        format: Optional[dict[str, Any]],
        result: ModelResponse,
    ) -> None:
        key = canonical_request_key(messages, tools, format)
        path = self.dir / f"{key}.json"
        if path.exists():  # additive — never clobber an existing recording
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        # Drop the bulky raw provider body from the committed fixture; keep a
        # human-readable meta so a reviewer can see what the request was.
        stored = result.model_copy(update={"raw": {}})
        meta = {
            "backend": self.backend,
            "last_message": (messages[-1].content or "")[:200] if messages else "",
        }
        blob = (
            json.dumps(
                {"_meta": meta, "response": stored.model_dump(exclude_none=False)},
                indent=2,
                ensure_ascii=True,
            )
            + "\n"
        )
        # write_bytes (not write_text) so line endings stay LF on every OS.
        path.write_bytes(blob.encode("utf-8"))
