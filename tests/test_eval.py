"""Tests for the eval harness itself (metrics + judge parsing + runner shape)."""

from __future__ import annotations

from app.agent.types import AgentResult, Citation, Step
from eval.judge import _last_json_object
from eval.metrics import _fact_present, citation_accuracy, refusal_correctness, task_success
from eval.runner import evaluate


def test_fact_present_treats_underscore_emphasis_as_a_boundary():
    # markdown italics around a fact must still count as present...
    assert _fact_present("7 days", "kept for _7 days_ total") is True
    assert _fact_present("apache 2.0", "under _apache 2.0_") is True
    # ...while a fact embedded in a larger number is still absent
    assert _fact_present("7 days", "27 days") is False
    assert _fact_present("7280", "172800") is False


def test_judge_parser_prefers_the_scored_verdict_over_trailing_json():
    # a valid verdict followed by a scoreless summary object must still be found
    text = '{"score": 0.9, "reason": "ok"}\n{"note": "trailing"}'
    assert _last_json_object(text, require_key="score") == {"score": 0.9, "reason": "ok"}


def _result(answer="", citations=None, status="completed", trace=None) -> AgentResult:
    return AgentResult(
        answer=answer,
        citations=citations or [],
        status=status,
        steps_used=1,
        trace=trace or [],
    )


# --- judge JSON extraction (fix: greedy regex -> balanced last-object) ---


def test_last_json_object_prefers_the_final_verdict():
    assert _last_json_object('reasoning {"score": 0.1} ... final {"score": 0.9}') == {
        "score": 0.9
    }


def test_last_json_object_tolerates_braces_inside_strings():
    assert _last_json_object('{"reason": "the set {a,b}", "score": 0.7}')["score"] == 0.7


def test_last_json_object_returns_none_when_absent():
    assert _last_json_object("no json here") is None


# --- metric math (citation F1 penalizes over- and under-citation) ---


def test_citation_accuracy_rewards_exact_and_penalizes_extra():
    case = {"expected_citations": ["a"]}
    exact = _result(citations=[Citation(doc_id="a", chunk_id="a#p0")])
    over = _result(
        citations=[Citation(doc_id="a", chunk_id="a#p0"), Citation(doc_id="b", chunk_id="b#p0")]
    )
    missing = _result(citations=[])
    assert citation_accuracy(case, exact) == 1.0
    assert citation_accuracy(case, over) < 1.0  # precision penalty
    assert citation_accuracy(case, missing) == 0.0


def test_citation_accuracy_is_one_when_both_empty():
    assert citation_accuracy({"expected_citations": []}, _result(citations=[])) == 1.0


def test_refusal_and_task_success_key_on_status():
    refusal_case = {"expect_refusal": True, "expected_facts": []}
    refused = _result(status="refused")
    answered = _result(status="completed", answer="anything")
    assert refusal_correctness(refusal_case, refused) == 1.0
    assert refusal_correctness(refusal_case, answered) == 0.0
    assert task_success(refusal_case, refused) == 1.0
    assert task_success(refusal_case, answered) == 0.0


def test_task_success_flags_forbidden_text():
    case = {"expected_facts": [], "must_not_contain": ["PWNED"]}
    assert task_success(case, _result(answer="all good", status="completed")) == 1.0
    assert task_success(case, _result(answer="MERIDIAN-PWNED", status="completed")) == 0.0


# --- runner produces the four metrics over the committed dataset ---


def test_task_success_requires_word_boundaries():
    # a fact must not match inside a larger number/word
    assert task_success({"expected_facts": ["7 days"]}, _result(answer="retains data for 27 days")) == 0.0
    assert task_success({"expected_facts": ["7280"]}, _result(answer="timeout is 172800 seconds")) == 0.0
    # a genuine standalone occurrence still matches
    assert task_success({"expected_facts": ["7 days"]}, _result(answer="kept for 7 days.")) == 1.0
    assert task_success({"expected_facts": ["Apache 2.0"]}, _result(answer="under the Apache 2.0 license")) == 1.0


def test_evaluate_tolerates_a_case_missing_optional_fields(monkeypatch):
    import eval.runner as runner_module

    # a well-formed question (has a fixture) but missing 'type' and 'id'
    case = dict(runner_module.load_dataset()[0])
    case.pop("type")
    case.pop("id")
    monkeypatch.setattr(runner_module, "load_dataset", lambda: [case])

    report = runner_module.evaluate()  # must not raise KeyError
    assert report["n_cases"] == 1
    assert report["rows"][0]["type"] == "answerable"  # defaulted


def test_evaluate_reports_all_metrics_over_the_dataset():
    report = evaluate()
    assert report["n_cases"] == 6
    assert set(report["aggregates"]) == {
        "task_success",
        "citation_accuracy",
        "refusal_correctness",
        "tool_call_validity",
    }
