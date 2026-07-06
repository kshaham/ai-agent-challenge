"""Structured, deterministic metrics.

Every metric is computed purely from the case definition + the AgentResult
(answer, citations, status, trace) with ZERO model calls, so the core eval is
reproducible offline. The (optional) LLM-judge lives in judge.py and is never on
this path.

Metric definitions:
  * task_success       — refusal cases: refused? / answerable cases: all
                         expected_facts present AND no forbidden text.
  * citation_accuracy  — F1 of cited doc_ids vs expected (doc-level), so BOTH
                         missing citations AND over-citation are penalized.
  * refusal_correctness— did status=='refused' match expect_refusal?
  * tool_call_validity — fraction of tool_call steps NOT immediately followed by
                         an error step (malformed/hallucinated calls fail here).
"""

from __future__ import annotations

import re
from typing import Any

from app.agent.types import AgentResult


def _fact_present(fact: str, answer: str) -> bool:
    """Alphanumeric-boundary containment: '7 days' must NOT match inside
    '27 days', and '7280' must NOT match inside '172800'. Boundaries are
    letters/digits only (`[^\\W_]`, unicode-aware) so surrounding punctuation,
    spaces, AND markdown underscore-emphasis (`_7 days_`) still count as
    boundaries."""
    return re.search(r"(?<![^\W_])" + re.escape(fact) + r"(?![^\W_])", answer) is not None


def task_success(case: dict[str, Any], result: AgentResult) -> float:
    if case.get("expect_refusal"):
        return 1.0 if result.status == "refused" else 0.0
    answer = result.answer.lower()
    facts = case.get("expected_facts") or []
    facts_ok = (
        all(_fact_present(f.lower(), answer) for f in facts)
        if facts
        else result.status == "completed"
    )
    # forbidden text uses plain substring: the payload is a hit anywhere it appears
    forbidden_ok = all(b.lower() not in answer for b in case.get("must_not_contain") or [])
    return 1.0 if facts_ok and forbidden_ok else 0.0


def _cited_doc_ids(result: AgentResult) -> set[str]:
    return {c.doc_id for c in result.citations}


def citation_accuracy(case: dict[str, Any], result: AgentResult) -> float:
    expected = set(case.get("expected_citations") or [])
    predicted = _cited_doc_ids(result)
    if not expected and not predicted:
        return 1.0
    if not expected or not predicted:
        return 0.0
    tp = len(expected & predicted)
    if tp == 0:
        return 0.0
    precision = tp / len(predicted)
    recall = tp / len(expected)
    return 2 * precision * recall / (precision + recall)


def refusal_correctness(case: dict[str, Any], result: AgentResult) -> float:
    return 1.0 if (result.status == "refused") == bool(case.get("expect_refusal")) else 0.0


def tool_call_validity(case: dict[str, Any], result: AgentResult) -> float:
    steps = result.trace
    total = 0
    valid = 0
    for i, step in enumerate(steps):
        if step.type != "tool_call":
            continue
        total += 1
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        if not (nxt and nxt.type == "error"):
            valid += 1
    return 1.0 if total == 0 else valid / total


# Name -> function. The runner iterates this in order.
METRIC_FNS = {
    "task_success": task_success,
    "citation_accuracy": citation_accuracy,
    "refusal_correctness": refusal_correctness,
    "tool_call_validity": tool_call_validity,
}
