"""Agent-loop orchestration + robustness — worked examples and a candidate stub.

These test YOUR CODE, not the model. `ScriptedModel` lets you script an exact
sequence of model turns (tool calls, then a final answer, or a deliberately
malformed call) and assert your loop orchestrates and terminates correctly.

Two robustness failure modes are shown here as worked examples (hallucinated tool,
malformed arguments). The other two — a tool that errors, and a model that never
stops calling tools (non-termination) — are left for you to add against your own
`agent_loop`. See the skipped stub at the bottom.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.runner import run_agent
from app.agent.tools.registry import ToolDispatchError, ToolRegistry, _validate_args
from app.agent.tools.retrieval import RetrievalTool
from app.agent.types import Step
from app.model.base import ModelResponse, ToolCall
from app.model.replay import FixtureMissingError, ReplayModel
from app.model.scripted import ScriptedModel


def test_run_agent_reraises_missing_fixture_only_when_opted_in():
    registry = ToolRegistry([RetrievalTool()])
    novel = "a totally novel unseeded question 1234567 zzz"
    # API path: a missing fixture degrades to status='error'
    assert run_agent(novel, model=ReplayModel(), tools=registry).status == "error"
    # eval path: opts in so it surfaces (runner turns this into exit code 2)
    with pytest.raises(FixtureMissingError):
        run_agent(novel, model=ReplayModel(), tools=registry, reraise_fixture_missing=True)


def test_step_type_is_validated_on_assignment():
    step = Step(index=0, type="observation")
    with pytest.raises(ValidationError):
        step.type = "toolcall"  # a typo'd literal must fail loudly, not persist


def test_run_agent_returns_a_json_safe_trace(monkeypatch):
    import json

    from app.agent import runner as runner_module
    from app.agent.types import LoopOutcome

    def bad_loop(question, *, model, tools, trace, max_steps=8):
        # a candidate loop stashing non-JSON-native values in the Any-typed trace
        trace.add("observation", tool_result={"digest": b"\xff\xfe", "tags": {"b", "a"}})
        return LoopOutcome(answer="a", citations=[], status="completed", steps_used=1)

    monkeypatch.setattr(runner_module, "agent_loop", bad_loop)
    result = run_agent("q", model=ScriptedModel([]), tools=ToolRegistry([]))

    # the returned trace must serialize cleanly (so response + persistence never 500)
    json.dumps([s.model_dump(mode="json") for s in result.trace])
    tool_result = result.trace[0].tool_result
    assert isinstance(tool_result["digest"], str)  # bytes degraded
    assert tool_result["tags"] == ["a", "b"]  # set -> sorted list


def test_scripted_model_returns_responses_by_call_index():
    model = ScriptedModel(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_0", name="search_documents", arguments={"query": "port"})]
            ),
            ModelResponse(content="The port is 7280."),
        ]
    )
    first = model.chat([])
    assert first.tool_calls[0].name == "search_documents"
    second = model.chat([])
    assert second.content == "The port is 7280."
    assert model.call_count == 2


def test_dispatch_of_a_hallucinated_tool_is_a_typed_error():
    registry = ToolRegistry([RetrievalTool()])
    with pytest.raises(ToolDispatchError) as exc:
        registry.dispatch("web_search", {"query": "anything"})
    assert exc.value.kind == "unknown_tool"


def test_dispatch_with_malformed_arguments_is_a_typed_error():
    registry = ToolRegistry([RetrievalTool()])
    with pytest.raises(ToolDispatchError) as exc:
        registry.dispatch("search_documents", {"not_a_real_arg": 1})
    assert exc.value.kind == "bad_arguments"


def test_union_typed_param_does_not_crash_validation():
    # a legal JSON-Schema union type (e.g. optional string) must validate,
    # never raise a raw TypeError from hashing a list.
    schema = {"properties": {"x": {"type": ["string", "null"]}}, "additionalProperties": False}
    assert _validate_args(schema, {"x": "ok"}) is None
    assert _validate_args(schema, {"x": None}) is None
    assert _validate_args(schema, {"x": 5}) is not None  # wrong type -> error string


def test_out_of_range_k_is_a_typed_bad_arguments_error():
    registry = ToolRegistry([RetrievalTool()])
    with pytest.raises(ToolDispatchError) as exc:
        registry.dispatch("search_documents", {"query": "x", "k": -1})
    assert exc.value.kind == "bad_arguments"


@pytest.mark.skip(reason="CANDIDATE: write an orchestration test for YOUR agent_loop")
def test_candidate_loop_terminates_and_handles_bad_output():
    """Fill this in once you've built a real loop.

    Suggested coverage (script these with ScriptedModel + run_agent):
      * a normal run: model calls search_documents, observes, then answers;
        assert the trace has tool_call -> observation -> final and citations.
      * NON-TERMINATION: a model that ALWAYS returns a tool call; assert your
        loop stops at max_steps with a graceful final answer/refusal, not an
        exception and not an infinite loop.
      * TOOL ERROR: register a tool whose run() raises ToolError; assert your
        loop records an error step and recovers.
      * OFF-FORMAT OUTPUT: a model that returns prose where a tool call was
        expected; assert your loop doesn't crash.
    """
