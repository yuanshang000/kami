"""FastAPI 应用入口：装配路由、中间件、异常处理、生命周期。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import admin, admin_extra, auth, license
from app.core.config import settings
from app.core.crypto import crypto_service
from app.core.errors import ErrorCode, LicenseError, ERROR_HTTP_STATUS
from app.core.rate_limit import rate_limiter
from app.core.redis_client import close_redis, get_redis
from app.core.security import generate_request_id
from app.database.init_db import init_database
from app.schemas.response import error_response, success_response
from app.services.geo_service import geo_service

logger = logging.getLogger("license_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_database()
    logger.info("Initializing crypto service...")
    crypto_service.init_from_settings()
    try:
        redis_client = get_redis()
        redis_client.ping()
        rate_limiter.init(redis_client)
        logger.info("Redis connected.")
    except Exception as e:
        logger.warning(f"Redis unavailable, rate limiting disabled: {e}")
    geo_service.init()
    logger.info("License Server started.")
    yield
    geo_service.close()
    close_redis()
    logger.info("License Server stopped.")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="通用 License / 卡密授权系统",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(license.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(admin_extra.router)


# ---------------------------------------------------------------------------
# 异常处理
# ---------------------------------------------------------------------------

@app.exception_handler(LicenseError)
async def license_error_handler(request: Request, exc: LicenseError) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    body = error_response(
        exc.code,
        request_id,
        message=exc.message,
        error_type=exc.error_type,
        field=exc.field,
        details=exc.details,
        retry_after=exc.retry_after,
        docs_url=exc.docs_url,
    )
    status = ERROR_HTTP_STATUS.get(exc.code, 500)
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=status, content=body, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        details.append({
            "field": loc or "body",
            "reason": err.get("type", "invalid"),
            "message": err.get("msg", "invalid value"),
        })
    body = error_response(
        ErrorCode.INVALID_REQUEST,
        request_id,
        message="invalid request",
        error_type="validation_error",
        details=details,
    )
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    logger.exception(f"Unhandled error [request_id={request_id}]: {exc}")
    body = error_response(
        ErrorCode.INTERNAL_ERROR,
        request_id,
        message="internal server error",
        error_type="server_error",
        retryable=True,
    )
    return JSONResponse(status_code=500, content=body)


@app.get("/health")
async def health():
    return success_response({"status": "ok"}, generate_request_id())


@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(html_path, media_type="text/html")
