"""Request validation + structured error envelope."""

from __future__ import annotations


def test_blank_question_is_rejected(client):
    resp = client.post("/api/tasks", json={"question": "   "})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_missing_question_is_rejected(client):
    resp = client.post("/api/tasks", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert "message" in body["error"]


def test_too_long_question_is_rejected(client):
    resp = client.post("/api/tasks", json={"question": "x" * 3000})
    assert resp.status_code == 422


def test_deeply_nested_body_returns_clean_422(client):
    # a deeply-nested JSON body must not blow the recursion limit in the error
    # handler and turn a 422 into a 500.
    body = b'{"question": ' + b"[" * 1500 + b"]" * 1500 + b"}"
    resp = client.post(
        "/api/tasks", content=body, headers={"content-type": "application/json"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_unencodable_question_returns_clean_422(client):
    # a lone Unicode surrogate is valid JSON but not utf-8 encodable; it must
    # yield a clean structured 422, not crash the error handler.
    resp = client.post(
        "/api/tasks",
        content=b'{"question": "lone \\ud83d here"}',
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
