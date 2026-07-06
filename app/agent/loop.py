"""CANDIDATE WORKSPACE — the agent loop.

>>> This is the core of the challenge. Replace the baseline below. <<<

It ships as a DELIBERATELY MEDIOCRE baseline so the repo runs end to end and the
eval has a real (poor) score to improve on. The baseline:
  * does a single hard-coded retrieval — the MODEL never decides to call a tool,
  * makes exactly one model call to write an answer,
  * NEVER refuses, even when the corpus doesn't support an answer,
  * attaches NO citations,
  * pipes retrieved text straight into the prompt, so a document containing an
    injected instruction can hijack the answer.

Run `make eval` to see where it fails. Then build a real loop: let the model plan
and call tools, observe results and iterate, enforce `max_steps`, ground the
answer with citations, and refuse when the corpus doesn't support an answer. See
CHALLENGE.md ("The Agent") and ARCHITECTURE.md ("The seam") for the contract.
"""

from __future__ import annotations

from app.agent.prompts import load_prompt
from app.agent.tools.registry import ToolRegistry
from app.agent.trace import Trace
from app.agent.types import LoopOutcome
from app.model.base import ModelClient, ModelMessage

_MAX_CONTEXT_CHUNKS = 3


def agent_loop(
    question: str,
    *,
    model: ModelClient,
    tools: ToolRegistry,
    trace: Trace,
    max_steps: int = 8,
) -> LoopOutcome:
    # 1) Retrieve (hard-coded — a real loop would let the model decide this).
    args = {"query": question, "k": _MAX_CONTEXT_CHUNKS}
    trace.add("tool_call", tool_name="search_documents", tool_args=args)
    result = tools.dispatch("search_documents", args)
    chunks = result["results"]
    observation = "\n\n".join(f"[{c['doc_id']}] {c['text']}" for c in chunks)
    trace.add("observation", content=observation, tool_result=result)

    # 2) One model call to write an answer from whatever was retrieved.
    system = load_prompt("system.md")
    user = f"Question: {question}\n\nContext:\n{observation}"
    messages = [
        ModelMessage(role="system", content=system),
        ModelMessage(role="user", content=user),
    ]
    response = model.chat(messages)
    answer = (response.content or "").strip()
    trace.add("final", content=answer)

    # 3) No citations, never refuses. status is always 'completed'.
    return LoopOutcome(answer=answer, citations=[], status="completed", steps_used=1)
