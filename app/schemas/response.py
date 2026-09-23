"""统一响应封装。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.errors import ErrorCode, ERROR_MESSAGE


class ErrorDetail(BaseModel):
    field: str
    reason: str
    message: str


class ErrorBody(BaseModel):
    type: str
    field: Optional[str] = None
    details: Optional[list[ErrorDetail]] = None
    retryable: bool = False
    retry_after: Optional[int] = None
    docs_url: Optional[str] = None


class ApiResponse(BaseModel):
    success: bool
    code: int
    message: str
    request_id: str
    data: Optional[Any] = None
    error: Optional[ErrorBody] = None


def success_response(data: Any, request_id: str, message: str = "success") -> dict[str, Any]:
    return {
        "success": True,
        "code": 0,
        "message": message,
        "request_id": request_id,
        "data": data,
    }


def error_response(
    code: ErrorCode,
    request_id: str,
    message: Optional[str] = None,
    error_type: Optional[str] = None,
    field: Optional[str] = None,
    details: Optional[list[dict[str, str]]] = None,
    retryable: Optional[bool] = None,
    retry_after: Optional[int] = None,
    docs_url: Optional[str] = None,
) -> dict[str, Any]:
    from app.core.errors import ERROR_TYPE, RETRYABLE_CODES
    return {
        "success": False,
        "code": int(code),
        "message": message or ERROR_MESSAGE.get(code, "error"),
        "request_id": request_id,
        "data": None,
        "error": {
            "type": error_type or ERROR_TYPE.get(code, "server_error"),
            "field": field,
            "details": details,
            "retryable": retryable if retryable is not None else (code in RETRYABLE_CODES),
            "retry_after": retry_after,
            "docs_url": docs_url,
        },
    }
