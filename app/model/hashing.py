"""Canonical request hashing — the heart of deterministic record/replay.

Every model backend that RECORDS a fixture (RecordingStubModel, LiveModel) and
the one that READS fixtures (ReplayModel) must key on the exact same bytes. That
key is computed here, from the *abstract* request (messages + tools + format)
BEFORE any provider-specific translation, so a fixture recorded live against
Ollama replays identically offline.

Invariants that keep the key stable across processes/machines (do not break these):
  * volatile fields are stripped: tool_call ids, tool_call_id — never hashed.
  * no timestamps / uuids / RNG ever reach the messages.
  * tools are serialized in name-sorted order with sorted keys.
  * json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=True) — a fixed,
    whitespace- and encoding-stable canonical form.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from app.model.base import ModelMessage, ToolSpec


def _message_payload(m: ModelMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": m.role}
    if m.content is not None:
        payload["content"] = m.content
    if m.tool_calls:
        # id intentionally omitted (volatile).
        payload["tool_calls"] = [
            {"name": tc.name, "arguments": tc.arguments} for tc in m.tool_calls
        ]
    if m.name is not None:
        payload["name"] = m.name
    # tool_call_id intentionally omitted (volatile).
    return payload


def _tool_payload(t: ToolSpec) -> dict[str, Any]:
    return {"name": t.name, "description": t.description, "parameters": t.parameters}


def canonical_request(
    messages: list[ModelMessage],
    tools: Optional[list[ToolSpec]] = None,
    format: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "messages": [_message_payload(m) for m in messages],
        "tools": [_tool_payload(t) for t in sorted(tools or [], key=lambda x: x.name)],
        "format": format,
    }


def canonical_request_key(
    messages: list[ModelMessage],
    tools: Optional[list[ToolSpec]] = None,
    format: Optional[dict[str, Any]] = None,
) -> str:
    payload = canonical_request(messages, tools, format)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
