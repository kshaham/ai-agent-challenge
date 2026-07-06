"""Eval runner + regression gate.

    python -m eval.runner                 # offline, replay, diff vs baseline
    python -m eval.runner --update-baseline
    python -m eval.runner --judge         # also run the LLM judge (needs a model)
    python -m eval.runner --json

Reads eval/dataset.jsonl, runs the agent against each case in replay mode, computes
the structured metrics, and compares the aggregates to eval/baseline.json. Exit 0
if no metric dropped past the threshold, 1 on a regression, 2 if a fixture is
missing (a distinct failure, not a quality regression).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from app.agent.runner import run_agent
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.retrieval import RetrievalTool
from app.agent.types import AgentResult
from app.model.base import ModelClient
from app.model.replay import FixtureMissingError, ReplayModel
from app.paths import EVAL_DIR
from eval.metrics import METRIC_FNS

DATASET_PATH = EVAL_DIR / "dataset.jsonl"
BASELINE_PATH = EVAL_DIR / "baseline.json"
DROP_THRESHOLD = 0.05
_INJECTION_DOC = "10-faq"


def load_dataset() -> list[dict[str, Any]]:
    lines = DATASET_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _injection_surfaced(result: AgentResult) -> bool:
    for step in result.trace:
        if step.type == "observation" and _INJECTION_DOC in (str(step.content) + str(step.tool_result)):
            return True
    return any(c.doc_id == _INJECTION_DOC for c in result.citations)


def evaluate(
    model: Optional[ModelClient] = None, judge: bool = False
) -> dict[str, Any]:
    model = model or ReplayModel()
    registry = ToolRegistry([RetrievalTool()])
    cases = load_dataset()

    rows: list[dict[str, Any]] = []
    judge_scores: list[float] = []
    for i, case in enumerate(cases):
        # be tolerant of a candidate-added case that omits an optional field —
        # `.get()` everywhere (like eval/metrics.py) so one under-specified case
        # can't abort the whole run with a bare KeyError.
        case_id = case.get("id", f"case_{i}")
        case_type = case.get("type", "answerable")
        question = case.get("question")
        if not question:
            print(f"skipping case {case_id!r}: no 'question' field", file=sys.stderr)
            continue
        # opt in to FixtureMissingError so a stale/missing fixture surfaces as the
        # distinct exit-2 path, not a swallowed status='error' scored as a regression
        result = run_agent(
            question, model=model, tools=registry, reraise_fixture_missing=True
        )
        row: dict[str, Any] = {"id": case_id, "type": case_type, "status": result.status}
        for name, fn in METRIC_FNS.items():
            row[name] = fn(case, result)
        if case_type == "adversarial" and not _injection_surfaced(result):
            row["warning"] = (
                "injected doc was not retrieved — adversarial case may be vacuous"
            )
        if judge:
            from eval.judge import judge_case

            score = judge_case(case, result, model)
            row["judge"] = score
            if score is not None:
                judge_scores.append(score)
        rows.append(row)

    metric_names = list(METRIC_FNS)
    n = len(rows)
    aggregates = {
        name: (round(sum(r[name] for r in rows) / n, 4) if n else 0.0)
        for name in metric_names
    }
    if judge and judge_scores:
        aggregates["judge"] = round(sum(judge_scores) / len(judge_scores), 4)
    report: dict[str, Any] = {"rows": rows, "aggregates": aggregates, "n_cases": len(cases)}
    if judge:
        # the judge average is over PARSED verdicts; surface coverage so cases the
        # judge couldn't score aren't silently dropped from the reported mean.
        report["judge_coverage"] = [len(judge_scores), len(rows)]
    return report


def _load_baseline() -> Optional[dict[str, float]]:
    if not BASELINE_PATH.exists():
        return None
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("metrics")


def _print_report(report: dict[str, Any], baseline: Optional[dict[str, float]]) -> list[str]:
    regressions: list[str] = []
    print(f"\nEval over {report['n_cases']} cases\n" + "-" * 52)
    print(f"{'case':<28} {'status':<10} metrics")
    for r in report["rows"]:
        scores = " ".join(
            f"{k[:4]}={r[k]:.2f}" for k in METRIC_FNS if k in r
        )
        print(f"{r['id']:<28} {r['status']:<10} {scores}")
        if "warning" in r:
            print(f"    ! {r['warning']}")
    print("-" * 52)
    for name, value in report["aggregates"].items():
        base = (baseline or {}).get(name)
        flag = ""
        if base is not None and value < base - DROP_THRESHOLD:
            flag = f"  <-- REGRESSION (baseline {base:.4f})"
            regressions.append(name)
        print(f"  {name:<22} {value:.4f}{flag}")
    if "judge_coverage" in report:
        scored, total = report["judge_coverage"]
        if scored < total:
            print(f"  (judge scored {scored}/{total} cases; {total - scored} unparseable, excluded from the mean)")
    print()
    return regressions


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the eval suite.")
    parser.add_argument("--judge", action="store_true", help="also run the LLM judge")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    parser.add_argument("--live", action="store_true", help="use the live model")
    args = parser.parse_args(argv)

    model: Optional[ModelClient] = None
    if args.live:
        from app.model.live import LiveModel

        model = LiveModel()

    try:
        report = evaluate(model=model, judge=args.judge)
    except FixtureMissingError as exc:
        print(f"\nFIXTURE MISSING (not a regression):\n{exc}\n", file=sys.stderr)
        return 2

    if report["n_cases"] == 0:
        print("No eval cases found in eval/dataset.jsonl", file=sys.stderr)
        return 2

    # In --json mode, stdout must be PURE JSON (machine-readable). All the
    # human-readable status lines below are therefore gated on `not args.json`;
    # the exit code still carries the pass/fail/regression signal.
    if args.json:
        print(json.dumps(report, indent=2))
    baseline = _load_baseline()
    if not args.json:
        regressions = _print_report(report, baseline)
    else:
        regressions = [
            name
            for name, value in report["aggregates"].items()
            if baseline and name in baseline and value < baseline[name] - DROP_THRESHOLD
        ]

    if args.update_baseline:
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "metrics": report["aggregates"],
                    "drop_threshold": DROP_THRESHOLD,
                    "n_cases": report["n_cases"],
                    "generated_from": "eval.runner --update-baseline",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if not args.json:
            print(f"baseline updated -> {BASELINE_PATH}")
        return 0

    if regressions:
        if not args.json:
            print(f"FAIL: {len(regressions)} metric(s) regressed: {regressions}")
        return 1
    if not args.json:
        print("OK: no regressions vs baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
