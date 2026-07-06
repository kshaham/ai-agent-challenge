"""REST endpoints.

POST /api/tasks runs the agent synchronously and returns the id, answer, and full
trace; the two GETs retrieve a task and list tasks. The agent runs behind
`run_agent` (the seam), so wiring the candidate's loop in requires no change here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent.runner import run_agent
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.retrieval import RetrievalTool
from app.api.schemas import (
    CreateTaskRequest,
    ErrorEnvelope,
    TaskResponse,
    TaskSummary,
)
from app.deps import get_model
from app.model.base import ModelClient
from app.storage import repository

router = APIRouter(prefix="/api", tags=["tasks"])

# Built once at import: the retrieval tool wraps the process-wide BM25 index.
# A second tool would simply be added to this list.
_registry = ToolRegistry([RetrievalTool()])


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorEnvelope, "description": "Validation error"}},
)
def create_task(
    body: CreateTaskRequest, model: ModelClient = Depends(get_model)
) -> TaskResponse:
    result = run_agent(body.question, model=model, tools=_registry)
    task_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    repository.save_task(task_id, body.question, created_at, result)
    return TaskResponse(
        id=task_id,
        question=body.question,
        created_at=created_at,
        answer=result.answer,
        citations=result.citations,
        status=result.status,
        steps_used=result.steps_used,
        trace=result.trace,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    responses={404: {"model": ErrorEnvelope, "description": "Task not found"}},
)
def get_task(task_id: str) -> TaskResponse:
    row = repository.get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"task {task_id!r} not found")
    return TaskResponse(**row)


@router.get("/tasks", response_model=list[TaskSummary])
def list_tasks() -> list[TaskSummary]:
    return [TaskSummary(**t) for t in repository.list_tasks()]
