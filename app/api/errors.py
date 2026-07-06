"""Structured error responses.

Every error the API returns has the same envelope shape:
    {"error": {"code": "...", "message": "...", "details": ...}}
so clients (and the tests) can rely on it regardless of which layer failed. The
handlers are written so that serializing the error body can NEVER itself raise
(no un-encodable echoes, no unbounded recursion over the rejected input).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.api.schemas import ErrorDetail, ErrorEnvelope


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    # Build through the Pydantic models so the runtime body can't drift from the
    # documented ErrorEnvelope schema.
    return ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, details=details)
    ).model_dump()


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Optional[dict[str, str]] = None,
) -> Response:
    envelope = _envelope(code, message, details)
    # ensure_ascii=True escapes any non-ASCII (including a lone surrogate) to
    # \\uXXXX, so serializing the error body can never raise UnicodeEncodeError.
    body = json.dumps(envelope, ensure_ascii=True).encode("utf-8")
    return Response(
        content=body, status_code=status_code, media_type="application/json", headers=headers
    )


def _safe_validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    # Keep type/loc/msg (small, JSON-native) but DROP the echoed `input` and
    # `ctx`: input can be arbitrarily large/deeply-nested user data and recursing
    # over it (via jsonable_encoder) would blow the recursion limit and turn a
    # clean 422 into a 500. loc elements are str/int, so this never recurses.
    out: list[dict[str, Any]] = []
    for err in exc.errors():
        out.append(
            {
                "type": err.get("type"),
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": err.get("msg"),
            }
        )
    return out


_STATUS_CODES = {
    400: "bad_request",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> Response:
        return _error_response(
            422, "validation_error", "Request validation failed", _safe_validation_details(exc)
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> Response:
        code = _STATUS_CODES.get(exc.status_code, "error")
        # forward exc.headers so, e.g., a 405 keeps its mandatory `Allow` header.
        return _error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        return _error_response(500, "internal_error", "An unexpected error occurred")
