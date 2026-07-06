"""The tool abstraction.

A tool is a name + description + a static JSON-Schema for its arguments + a `run`
implementation. `search_documents` (retrieval.py) is the worked example; adding a
second tool means subclassing Tool and registering it — the loop and the model
wiring don't change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.model.base import ToolSpec


class ToolError(Exception):
    """Raised by a tool's `run` when it cannot fulfil a well-formed request
    (e.g. a downstream failure). The registry turns this into a typed dispatch
    error so the loop can record it and recover."""


class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]  # static JSON Schema (hand-written, not generated)

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, parameters=self.parameters
        )

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        raise NotImplementedError
