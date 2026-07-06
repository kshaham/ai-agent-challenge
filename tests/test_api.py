"""Integration test for the task endpoint.

Submits a question, gets back an answer + full trace, then retrieves it and lists
tasks. Runs against the deterministic ReplayModel + the shipped baseline agent, so
it asserts the baseline's ACTUAL (mediocre) behavior: it answers simple lookups,
but attaches no citations.
"""

from __future__ import annotations


def test_submit_get_and_list_task(client):
    resp = client.post(
        "/api/tasks", json={"question": "What is the default HTTP port for Meridian?"}
    )
    assert resp.status_code == 201
    body = resp.json()

    assert "7280" in body["answer"]
    assert body["status"] == "completed"
    assert body["citations"] == []  # baseline attaches no citations
    step_types = [s["type"] for s in body["trace"]]
    assert "tool_call" in step_types
    assert "observation" in step_types
    assert "final" in step_types

    task_id = body["id"]
    got = client.get(f"/api/tasks/{task_id}")
    assert got.status_code == 200
    assert got.json()["id"] == task_id
    assert got.json()["question"] == body["question"]

    listing = client.get("/api/tasks")
    assert listing.status_code == 200
    assert any(t["id"] == task_id for t in listing.json())


def test_get_missing_task_returns_structured_404(client):
    resp = client.get("/api/tasks/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_method_not_allowed_includes_allow_header(client):
    resp = client.delete("/api/tasks")
    assert resp.status_code == 405
    assert "POST" in (resp.headers.get("allow") or "")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
