"""Task persistence.

Stores each run as one row: scalar columns for the fields you query on, and the
citations + full trace as JSON blobs (they're read back whole and returned via
GET, never filtered in SQL — so JSON is the right, simple choice at this scale).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.agent.types import AgentResult
from app.storage import db

_SQLITE_INT_MAX = 2**63 - 1
_SQLITE_INT_MIN = -(2**63)


def _clamp_int(value: Any) -> int:
    """Clamp to SQLite's 64-bit INTEGER range so a pathological steps_used from a
    misbehaving loop can't raise OverflowError and 500 the write."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return max(_SQLITE_INT_MIN, min(_SQLITE_INT_MAX, value))


def _safe_dump(items: list[Any]) -> str:
    """JSON-serialize model items (Step/Citation). Step.tool_result is typed Any;
    mode="json" + default=str handle datetime/set/bytes, and any item that still
    can't serialize (a cyclic / very-deep / exotic-keyed value) degrades to a
    placeholder rather than crashing the whole write and losing the task."""
    payload: list[Any] = []
    for item in items:
        try:
            payload.append(item.model_dump(mode="json"))
        except (ValueError, TypeError, RecursionError):
            safe: dict[str, Any] = {"_unserializable": True}
            for attr in ("index", "type", "tool_name", "doc_id", "chunk_id"):
                if hasattr(item, attr):
                    safe[attr] = getattr(item, attr)
            payload.append(safe)
    return json.dumps(payload, default=str)


def save_task(
    task_id: str, question: str, created_at: str, result: AgentResult
) -> None:
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO tasks (id, question, created_at, status, answer, "
            "steps_used, citations, trace) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                question,
                created_at,
                result.status,
                result.answer,
                _clamp_int(result.steps_used),
                _safe_dump(result.citations),
                _safe_dump(result.trace),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "question": row["question"],
        "created_at": row["created_at"],
        "status": row["status"],
        "answer": row["answer"],
        "steps_used": row["steps_used"],
        "citations": json.loads(row["citations"]),
        "trace": json.loads(row["trace"]),
    }


def get_task(task_id: str) -> Optional[dict[str, Any]]:
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row else None


def list_tasks() -> list[dict[str, Any]]:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, question, created_at, status, steps_used "
            "FROM tasks ORDER BY rowid DESC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r["id"],
            "question": r["question"],
            "created_at": r["created_at"],
            "status": r["status"],
            "steps_used": r["steps_used"],
        }
        for r in rows
    ]
