"""Model-agnostic interface.

Everything the agent knows about "a language model" is this small surface. Swapping
Ollama for another runner (or the deterministic ReplayModel used in tests/evals)
means implementing `ModelClient.chat` — nothing else in the codebase changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """A model's request to invoke a tool.

    `id` is assigned deterministically by the loop (``call_{index}``) and is
    **excluded from the request hash** (see app/model/hashing.py) so that
    record-time and replay-time message histories are byte-identical.
    `arguments` is ALWAYS a dict (never a JSON string) across every model
    implementation, the trace, and tool dispatch.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ModelMessage(BaseModel):
    role: Role
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None  # only on assistant messages
    tool_call_id: Optional[str] = None  # only on tool messages (volatile; unhashed)
    name: Optional[str] = None  # tool name on tool messages


class ModelResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    """A tool advertised to the model.

    `parameters` is a hand-written static JSON Schema dict (NOT generated from a
    Pydantic model) so a library upgrade can never shift the bytes that feed the
    request hash and silently invalidate every recorded fixture.
    """

    name: str
    description: str
    parameters: dict[str, Any]


class ModelClient(ABC):
    """The one method the whole system depends on."""

    @abstractmethod
    def chat(
        self,
        messages: list[ModelMessage],
        *,
        tools: Optional[list[ToolSpec]] = None,
        format: Optional[dict[str, Any]] = None,
    ) -> ModelResponse:
        """Return the model's next message given the conversation so far.

        `tools` advertises callable tools (the model may respond with tool_calls).
        `format` optionally constrains output to a JSON schema (structured
        outputs) — the recommended way to keep a small local model's tool calls
        well-formed.
        """
        raise NotImplementedError
