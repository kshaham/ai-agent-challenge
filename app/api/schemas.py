"""API request/response models.

Depends on the agent layer (reuses Citation/Step) — never the reverse.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.agent.types import Citation, Status, Step


class CreateTaskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v


class TaskResponse(BaseModel):
    id: str
    question: str
    created_at: str
    answer: str
    citations: list[Citation]
    status: Status
    steps_used: int
    trace: list[Step]


class TaskSummary(BaseModel):
    id: str
    question: str
    created_at: str
    status: Status
    steps_used: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
