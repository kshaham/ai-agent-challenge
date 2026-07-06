"""Core agent data types.

These live in the agent layer (not the API layer) so the dependency arrow always
points api -> agent, never the reverse — no import cycles.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

StepType = Literal["plan", "tool_call", "observation", "final", "error"]
Status = Literal["completed", "refused", "error"]


class Step(BaseModel):
    """One entry in the agent's trace. Every plan / tool call / observation /
    final answer / error the loop produces becomes a Step."""

    # validate_assignment so mutating a step to an invalid type (e.g. a typo'd
    # `step.type = "toolcall"`) raises at the point of the mistake, instead of
    # silently persisting a row that then 500s when read back.
    model_config = ConfigDict(validate_assignment=True)

    index: int
    type: StepType
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_result: Optional[Any] = None


class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    snippet: Optional[str] = None


class LoopOutcome(BaseModel):
    """What the candidate's `agent_loop` returns. Deliberately small: the loop
    owns the answer, the citations it chose, and whether it refused."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    status: Status = "completed"
    steps_used: int = 0


class AgentResult(BaseModel):
    """The full, inspectable result of a run — answer + citations + the complete
    step trace. Persisted and returned verbatim by the API."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    status: Status
    steps_used: int
    trace: list[Step] = Field(default_factory=list)
