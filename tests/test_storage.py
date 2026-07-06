"""Persistence tolerates non-JSON-native trace content.

Step.tool_result is typed Any, so a candidate loop may stash a datetime or a set
in the trace. Saving must not crash (it used to 500 the whole request); the
values are serialized the same way the HTTP response serializes them.
"""

from __future__ import annotations

import datetime

from app.agent.types import AgentResult, Step
from app.storage import repository


def test_non_json_native_trace_content_round_trips():
    step = Step(
        index=0,
        type="observation",
        tool_result={
            "at": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            "tags": {"a", "b"},
        },
    )
    result = AgentResult(answer="x", citations=[], status="completed", steps_used=1, trace=[step])

    repository.save_task("tid", "q", "2026-01-01T00:00:00+00:00", result)
    got = repository.get_task("tid")

    assert got is not None
    tool_result = got["trace"][0]["tool_result"]
    assert isinstance(tool_result["at"], str)  # datetime -> ISO string
    assert sorted(tool_result["tags"]) == ["a", "b"]  # set -> list


def test_pathological_trace_content_persists_without_crashing():
    # a cyclic tool_result + an out-of-range steps_used must not 500 / lose the
    # task: the bad item degrades to a placeholder and steps_used is clamped.
    cyclic: dict = {}
    cyclic["self"] = cyclic
    step = Step(index=0, type="observation", tool_result=cyclic)
    result = AgentResult(
        answer="x", citations=[], status="completed", steps_used=10**19, trace=[step]
    )

    repository.save_task("path", "q", "2026-01-01T00:00:00+00:00", result)  # must not raise
    got = repository.get_task("path")

    assert got is not None
    assert got["trace"][0]["_unserializable"] is True
    assert isinstance(got["steps_used"], int)  # clamped, not an OverflowError
