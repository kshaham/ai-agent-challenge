"""A programmable model for TESTS ONLY.

Returns a fixed sequence of responses by call index, ignoring message content.
This is how the agent-loop orchestration test scripts a deterministic run —
"first the model calls search, then it emits a malformed call, then it answers" —
and how the robustness failure modes (malformed args, unknown tool, tool error,
non-termination) are exercised without any recorded fixtures.

Why not hash-keyed replay fixtures for those? Because a robustness fixture would
be keyed to one exact message history; the moment a candidate changes their loop
the hash changes and the fixture is never hit. A call-indexed script is immune to
that and is the right tool for unit-testing orchestration.
"""

from __future__ import annotations

from typing import Any, Optional

from app.model.base import ModelClient, ModelMessage, ModelResponse, ToolSpec


class ScriptedModel(ModelClient):
    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self._i = 0
        self.seen_messages: list[list[ModelMessage]] = []

    def chat(
        self,
        messages: list[ModelMessage],
        *,
        tools: Optional[list[ToolSpec]] = None,
        format: Optional[dict[str, Any]] = None,
    ) -> ModelResponse:
        self.seen_messages.append(list(messages))
        if self._i >= len(self._responses):
            # A well-behaved loop should have stopped by now; running out of
            # scripted turns usually means the loop failed to terminate.
            raise AssertionError(
                "ScriptedModel exhausted: the loop asked for more model turns "
                f"than were scripted ({len(self._responses)})."
            )
        resp = self._responses[self._i]
        self._i += 1
        return resp

    @property
    def call_count(self) -> int:
        return self._i
