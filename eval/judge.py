"""LLM-as-judge plumbing (opt-in).

This is fully wired — building the prompt, calling the model, parsing the score,
aggregating — so the candidate writes only the rubric in app/prompts/judge.md and
a note on judge risks. It is OFF by default: it needs a model call, so it only
runs under `make eval-judge` (live model or recorded judge fixtures). Keeping it
off the default path is what preserves "green out of the box".
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.agent.prompts import load_prompt
from app.agent.types import AgentResult
from app.model.base import ModelClient, ModelMessage


def _last_json_object(text: str, require_key: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Return the LAST top-level ``{...}`` object that parses as a dict.

    Scans for balanced top-level objects (ignoring braces inside strings), so a
    stray brace fragment before OR a trailing JSON object after the real verdict
    doesn't defeat it. When ``require_key`` is given, prefer the last object that
    contains that key (falling back to the last dict), so a valid verdict followed
    by a scoreless summary object is still returned.
    """
    spans: list[str] = []
    depth = 0
    start: Optional[int] = None
    in_str = False
    escaped = False
    for i, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                spans.append(text[start : i + 1])
    fallback: Optional[dict[str, Any]] = None
    for span in reversed(spans):
        try:
            obj = json.loads(span)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if require_key is None or require_key in obj:
            return obj
        if fallback is None:
            fallback = obj
    return fallback


def _context_from_trace(result: AgentResult) -> str:
    parts = [s.content or "" for s in result.trace if s.type == "observation"]
    return "\n\n".join(parts)


def judge_case(
    case: dict[str, Any], result: AgentResult, model: ModelClient
) -> Optional[float]:
    """Return a 0..1 faithfulness/answer score, or None if parsing failed."""
    template = load_prompt("judge.md")
    prompt = (
        template.replace("{question}", case["question"])
        .replace("{answer}", result.answer)
        .replace("{context}", _context_from_trace(result))
    )
    resp = model.chat([ModelMessage(role="user", content=prompt)])
    obj = _last_json_object(resp.content or "", require_key="score")
    if obj is None:
        return None
    try:
        score = float(obj["score"])
    except (KeyError, TypeError, ValueError):
        return None
    return max(0.0, min(1.0, score))
