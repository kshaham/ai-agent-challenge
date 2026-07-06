"""The stable seam between the API and the candidate's loop.

`run_agent` owns the Trace and the error boundary so the AgentResult contract
always holds — even when the candidate's loop misbehaves. It deliberately does
NOT enforce max_steps, select citations, or decide refusals; those are the
candidate's graded responsibilities inside `agent_loop`. run_agent only:
  * creates the Trace (so a partial trace survives an exception),
  * runs the loop under try/except (uncaught -> status='error' + partial trace),
  * assembles the AgentResult.
"""

from __future__ import annotations

import json

from app.agent.loop import agent_loop
from app.agent.tools.registry import ToolRegistry
from app.agent.trace import Trace
from app.agent.types import AgentResult, Step
from app.model.base import ModelClient
from app.model.replay import FixtureMissingError


def _json_default(o: object) -> object:
    if isinstance(o, (set, frozenset)):
        try:
            return sorted(o)
        except TypeError:
            return sorted(o, key=repr)
    return str(o)


def _json_safe(value: object) -> object:
    """Return a JSON-serializable equivalent, degrading a cyclic / over-deep /
    otherwise-unserializable value to a placeholder. Applied to the trace we
    return so the HTTP response and the persisted row are byte-identical and
    NEITHER can 500 (Step.tool_result / tool_args are typed Any)."""
    if value is None:
        return None
    try:
        json.dumps(value)  # already pure JSON?
        return value
    except (TypeError, ValueError, RecursionError):
        pass
    try:
        return json.loads(json.dumps(value, default=_json_default))
    except (TypeError, ValueError, RecursionError):
        return {"_unserializable": True}


def _safe_steps(steps: list[Step]) -> list[Step]:
    return [
        s.model_copy(
            update={"tool_result": _json_safe(s.tool_result), "tool_args": _json_safe(s.tool_args)}
        )
        for s in steps
    ]


def run_agent(
    question: str,
    *,
    model: ModelClient,
    tools: ToolRegistry,
    max_steps: int = 8,
    reraise_fixture_missing: bool = False,
) -> AgentResult:
    trace = Trace()
    try:
        outcome = agent_loop(
            question, model=model, tools=tools, trace=trace, max_steps=max_steps
        )
        return AgentResult(
            answer=outcome.answer,
            citations=outcome.citations,
            status=outcome.status,
            steps_used=outcome.steps_used,
            trace=_safe_steps(trace.steps),
        )
    except FixtureMissingError:
        # A missing recorded response means "re-record me", not a runtime error.
        # The eval runner opts in to see it (so it can exit 2, distinct from a
        # quality regression); the API leaves it off and degrades to status=error.
        if reraise_fixture_missing:
            raise
        trace.add("error", content="model fixture missing (re-record needed)")
        return AgentResult(
            answer="",
            citations=[],
            status="error",
            steps_used=trace.count("plan", "tool_call"),
            trace=_safe_steps(trace.steps),
        )
    except Exception as exc:  # the loop is candidate code — never let it 500 blindly
        trace.add(
            "error",
            content=f"agent loop raised {type(exc).__name__}: {exc}",
        )
        return AgentResult(
            answer="",
            citations=[],
            status="error",
            steps_used=trace.count("plan", "tool_call"),
            trace=_safe_steps(trace.steps),
        )
