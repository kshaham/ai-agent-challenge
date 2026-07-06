"""LiveModel: tool-arg coercion + the OpenAI-compatible backend.

These test request construction / parsing with a mocked httpx, so no network or
real model is needed.
"""

from __future__ import annotations

import httpx

from app.model.base import ModelMessage
from app.model.live import LiveModel, _coerce_args


def test_coerce_non_dict_tool_args_degrades_uniformly():
    assert _coerce_args('{"a": 1}') == {"a": 1}  # JSON string -> object
    assert _coerce_args("[1, 2]") == {"_raw": [1, 2]}  # JSON string -> non-object
    assert _coerce_args([1, 2]) == {"_raw": [1, 2]}  # direct non-dict
    assert _coerce_args("{oops") == {"_raw": "{oops"}  # unparseable
    assert _coerce_args({"x": 1}) == {"x": 1}  # already a dict


def test_openai_backend_targets_chat_completions_with_auth(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://host/v1")

    captured: dict = {}

    def fake_post(url, *, json=None, headers=None, timeout=None):
        captured.update(url=url, headers=headers, payload=json)

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "hi",
                                "tool_calls": [
                                    {"id": "c0", "function": {"name": "search_documents", "arguments": '{"query": "x"}'}}
                                ],
                            }
                        }
                    ]
                }

        return _Resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    resp = LiveModel(record=False).chat([ModelMessage(role="user", content="q")])

    assert captured["url"] == "https://host/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert resp.content == "hi"
    assert resp.tool_calls[0].name == "search_documents"
    assert resp.tool_calls[0].arguments == {"query": "x"}


def test_openai_backend_forwards_structured_output_schema(monkeypatch):
    """The no-GPU (OpenAI-compatible) route must forward the full JSON schema —
    not degrade to schema-less json_object mode — so small hosted models keep
    their structured-output constraint (regression guard for the Round-3 bug)."""
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://host/v1")

    captured: dict = {}

    def fake_post(url, *, json=None, headers=None, timeout=None):
        captured.update(payload=json)

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "{}"}}]}

        return _Resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    LiveModel(record=False).chat([ModelMessage(role="user", content="q")], format=schema)

    rf = captured["payload"]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] == schema  # the schema is preserved, not dropped
