"""统一业务错误码与异常体系。

依据开发文档第 22、69、112 节定义完整错误码表。
所有 API 错误均通过 LicenseError 抛出，由全局异常处理器转换为统一响应。
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any, Optional


class ErrorCode(IntEnum):
    SUCCESS = 0
    INVALID_LICENSE = 4001
    LICENSE_NOT_FOUND = 4002
    LICENSE_EXPIRED = 4003
    LICENSE_DISABLED = 4004
    INVALID_PRODUCT = 4005
    INVALID_API_KEY = 4006
    INVALID_REQUEST = 4007
    INVALID_SIGNATURE = 4008
    INVALID_SESSION = 4009
    SESSION_EXPIRED = 4010
    REQUEST_EXPIRED = 4011
    NONCE_REPLAYED = 4012
    RATE_LIMITED = 4013
    CLIENT_VERSION_UNSUPPORTED = 4014
    PRODUCT_DISABLED = 4015
    INTERNAL_ERROR = 5001
    DATABASE_ERROR = 5002
    SIGNING_ERROR = 5003
    GEOIP_ERROR = 5004


ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.SUCCESS: 200,
    ErrorCode.INVALID_LICENSE: 400,
    ErrorCode.LICENSE_NOT_FOUND: 404,
    ErrorCode.LICENSE_EXPIRED: 200,
    ErrorCode.LICENSE_DISABLED: 200,
    ErrorCode.INVALID_PRODUCT: 400,
    ErrorCode.INVALID_API_KEY: 401,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.INVALID_SIGNATURE: 401,
    ErrorCode.INVALID_SESSION: 401,
    ErrorCode.SESSION_EXPIRED: 401,
    ErrorCode.REQUEST_EXPIRED: 400,
    ErrorCode.NONCE_REPLAYED: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.CLIENT_VERSION_UNSUPPORTED: 400,
    ErrorCode.PRODUCT_DISABLED: 403,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.SIGNING_ERROR: 500,
    ErrorCode.GEOIP_ERROR: 500,
}

ERROR_TYPE: dict[ErrorCode, str] = {
    ErrorCode.INVALID_LICENSE: "license_error",
    ErrorCode.LICENSE_NOT_FOUND: "not_found_error",
    ErrorCode.LICENSE_EXPIRED: "license_error",
    ErrorCode.LICENSE_DISABLED: "license_error",
    ErrorCode.INVALID_PRODUCT: "authorization_error",
    ErrorCode.INVALID_API_KEY: "authentication_error",
    ErrorCode.INVALID_REQUEST: "validation_error",
    ErrorCode.INVALID_SIGNATURE: "security_error",
    ErrorCode.INVALID_SESSION: "session_error",
    ErrorCode.SESSION_EXPIRED: "session_error",
    ErrorCode.REQUEST_EXPIRED: "security_error",
    ErrorCode.NONCE_REPLAYED: "security_error",
    ErrorCode.RATE_LIMITED: "rate_limit_error",
    ErrorCode.CLIENT_VERSION_UNSUPPORTED: "authorization_error",
    ErrorCode.PRODUCT_DISABLED: "authorization_error",
    ErrorCode.INTERNAL_ERROR: "server_error",
    ErrorCode.DATABASE_ERROR: "dependency_error",
    ErrorCode.SIGNING_ERROR: "server_error",
    ErrorCode.GEOIP_ERROR: "dependency_error",
}

ERROR_MESSAGE: dict[ErrorCode, str] = {
    ErrorCode.SUCCESS: "成功",
    ErrorCode.INVALID_LICENSE: "卡密无效",
    ErrorCode.LICENSE_NOT_FOUND: "卡密不存在",
    ErrorCode.LICENSE_EXPIRED: "卡密已过期",
    ErrorCode.LICENSE_DISABLED: "卡密已禁用",
    ErrorCode.INVALID_PRODUCT: "产品不匹配",
    ErrorCode.INVALID_API_KEY: "API Key 无效",
    ErrorCode.INVALID_REQUEST: "请求参数无效",
    ErrorCode.INVALID_SIGNATURE: "签名验证失败",
    ErrorCode.INVALID_SESSION: "会话无效",
    ErrorCode.SESSION_EXPIRED: "会话已过期",
    ErrorCode.REQUEST_EXPIRED: "请求已过期",
    ErrorCode.NONCE_REPLAYED: "请求已被重放",
    ErrorCode.RATE_LIMITED: "请求频率超限",
    ErrorCode.CLIENT_VERSION_UNSUPPORTED: "客户端版本不支持",
    ErrorCode.PRODUCT_DISABLED: "产品已禁用",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
    ErrorCode.DATABASE_ERROR: "数据库错误",
    ErrorCode.SIGNING_ERROR: "签名服务错误",
    ErrorCode.GEOIP_ERROR: "地理信息查询错误",
}

RETRYABLE_CODES: frozenset[ErrorCode] = frozenset({
    ErrorCode.RATE_LIMITED,
    ErrorCode.INTERNAL_ERROR,
    ErrorCode.DATABASE_ERROR,
    ErrorCode.SIGNING_ERROR,
    ErrorCode.GEOIP_ERROR,
})


class LicenseError(Exception):
    """业务异常基类，携带错误码与可选扩展信息。"""

    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        *,
        http_status: Optional[int] = None,
        field: Optional[str] = None,
        details: Optional[list[dict[str, str]]] = None,
        retry_after: Optional[int] = None,
        docs_url: Optional[str] = None,
        extra_data: Any = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGE.get(code, "error")
        self.http_status = http_status or ERROR_HTTP_STATUS.get(code, 500)
        self.error_type = ERROR_TYPE.get(code, "server_error")
        self.field = field
        self.details = details
        self.retryable = code in RETRYABLE_CODES
        self.retry_after = retry_after
        self.docs_url = docs_url
        self.extra_data = extra_data
        super().__init__(self.message)


class ValidationError(LicenseError):
    """参数校验错误，支持多字段 details。"""

    def __init__(self, details: list[dict[str, str]], message: str = "invalid request") -> None:
        super().__init__(ErrorCode.INVALID_REQUEST, message, details=details)


def success_message() -> str:
    return ERROR_MESSAGE[ErrorCode.SUCCESS]
