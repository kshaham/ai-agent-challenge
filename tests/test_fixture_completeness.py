"""Every dataset question must have a committed fixture.

Runs the shipped baseline over each eval case in replay mode. A missing fixture
would make run_agent return status='error', which this test flags with the
offending case id — so fixture drift fails loudly instead of surfacing as a
mysterious eval regression.
"""

from __future__ import annotations

from app.agent.runner import run_agent
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.retrieval import RetrievalTool
from app.model.replay import ReplayModel
from eval.runner import load_dataset


def test_all_dataset_questions_replay_without_missing_fixtures():
    model = ReplayModel()
    registry = ToolRegistry([RetrievalTool()])
    for case in load_dataset():
        result = run_agent(case["question"], model=model, tools=registry)
        assert result.status != "error", (
            f"case {case['id']!r} produced status=error — likely a missing fixture. "
            f"Run `make seed`."
        )
