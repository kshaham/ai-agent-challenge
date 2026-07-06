"""The trace recorder.

An append-only list of Steps. The candidate's loop calls `trace.add(...)` for
every step it takes; `run_agent` owns the Trace object so that even if the loop
raises, the partial trace survives and is returned (that's what makes the error
and non-termination cases inspectable).
"""

from __future__ import annotations

from typing import Any, Optional

from app.agent.types import Step, StepType


class Trace:
    def __init__(self) -> None:
        self._steps: list[Step] = []

    def add(
        self,
        type: StepType,
        *,
        content: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict[str, Any]] = None,
        tool_result: Optional[Any] = None,
    ) -> Step:
        step = Step(
            index=len(self._steps),
            type=type,
            content=content,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
        )
        self._steps.append(step)
        return step

    def append(self, step: Step) -> None:
        """Append a pre-built Step, re-indexing it to keep indices contiguous."""
        self._steps.append(step.model_copy(update={"index": len(self._steps)}))

    @property
    def steps(self) -> list[Step]:
        return list(self._steps)

    def count(self, *types: StepType) -> int:
        return sum(1 for s in self._steps if s.type in types)
