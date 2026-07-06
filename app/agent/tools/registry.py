"""Tool registry + dispatch.

`dispatch` is where malformed and hallucinated tool calls are turned into typed
errors (`unknown_tool`, `bad_arguments`, `tool_error`). The loop is expected to
catch ToolDispatchError, record an `error` Step, and recover — which is exactly
what the `tool_call_validity` metric reads (a tool_call Step with no following
error Step counts as valid).
"""

from __future__ import annotations

from typing import Any, Optional

from app.agent.tools.base import Tool, ToolError

DispatchErrorKind = str  # "unknown_tool" | "bad_arguments" | "tool_error"


class ToolDispatchError(Exception):
    def __init__(self, message: str, *, kind: DispatchErrorKind) -> None:
        super().__init__(message)
        self.kind = kind


_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def _type_ok(expected: Any, value: Any) -> bool:
    """Whether `value` satisfies a JSON-Schema `type`.

    `expected` may be a single type name or a union list (e.g. ["string","null"]).
    Unknown type names are treated as satisfied so we never over-validate — and,
    critically, a list `type` must not be used as a dict key (it's unhashable).
    """
    names = expected if isinstance(expected, list) else [expected]
    recognized = [n for n in names if n in _JSON_TYPES]
    if not recognized:
        return True
    # bool is a subclass of int; reject it where only numeric types are allowed.
    if (
        isinstance(value, bool)
        and "boolean" not in recognized
        and any(n in ("integer", "number") for n in recognized)
    ):
        return False
    allowed = tuple({t for n in recognized for t in _JSON_TYPES[n]})
    return isinstance(value, allowed)


def _validate_args(schema: dict[str, Any], arguments: dict[str, Any]) -> Optional[str]:
    """Minimal JSON-Schema check: required keys present, declared types match
    (scalar or union), numeric minimum/maximum honored, and no unexpected keys
    when additionalProperties is False. Returns an error string or None."""
    if not isinstance(arguments, dict):
        return "arguments must be an object"
    props: dict[str, Any] = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in arguments:
            return f"missing required argument {key!r}"
    if schema.get("additionalProperties") is False:
        for key in arguments:
            if key not in props:
                return f"unexpected argument {key!r}"
    for key, value in arguments.items():
        spec = props.get(key, {})
        expected = spec.get("type")
        if expected is not None and not _type_ok(expected, value):
            return f"argument {key!r} must be {expected}"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum, maximum = spec.get("minimum"), spec.get("maximum")
            if minimum is not None and value < minimum:
                return f"argument {key!r} must be >= {minimum}"
            if maximum is not None and value > maximum:
                return f"argument {key!r} must be <= {maximum}"
    return None


class ToolRegistry:
    def __init__(self, tools: Optional[list[Tool]] = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def specs(self) -> list:
        # name-sorted for a stable tool order in the request hash
        return [self._tools[name].spec() for name in sorted(self._tools)]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolDispatchError(
                f"unknown tool {name!r}; available: {sorted(self._tools)}",
                kind="unknown_tool",
            )
        err = _validate_args(tool.parameters, arguments)
        if err:
            raise ToolDispatchError(
                f"invalid arguments for {name!r}: {err}", kind="bad_arguments"
            )
        try:
            return tool.run(**arguments)
        except ToolError as exc:
            raise ToolDispatchError(str(exc), kind="tool_error") from exc
