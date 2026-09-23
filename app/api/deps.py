"""FastAPI 依赖注入：API Key 鉴权、管理员 JWT 鉴权、request_id 提取。"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorCode, LicenseError
from app.core.security import constant_time_compare
from app.database.database import get_db
from app.models import AdminUser, Product
from app.services.license_service import get_product_by_api_key


def get_request_id(
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
) -> str:
    from app.core.security import generate_request_id
    return x_request_id or generate_request_id()


def get_api_key_product(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Product:
    """从 Authorization: Bearer {api_key} 提取并验证产品。"""
    if not authorization:
        raise LicenseError(ErrorCode.INVALID_API_KEY)
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise LicenseError(ErrorCode.INVALID_API_KEY)
    api_key = parts[1].strip()
    product = get_product_by_api_key(db, api_key)
    if product is None:
        raise LicenseError(ErrorCode.INVALID_API_KEY)
    return product


def get_product_id_from_header(
    x_product_id: Optional[str] = Header(None, alias="X-Product-ID"),
) -> Optional[str]:
    return x_product_id


# ---------------------------------------------------------------------------
# Admin JWT
# ---------------------------------------------------------------------------

def create_admin_token(admin: AdminUser) -> str:
    from jose import jwt
    from app.core.time_utils import utc_now_ts
    payload = {
        "sub": str(admin.id),
        "username": admin.username,
        "role": admin.role,
        "exp": utc_now_ts() + settings.jwt_expire_minutes * 60,
        "iat": utc_now_ts(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_admin_token(token: str) -> dict:
    from jose import jwt, JWTError
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise LicenseError(ErrorCode.INVALID_SESSION) from exc


def get_current_admin(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> AdminUser:
    if not authorization:
        raise LicenseError(ErrorCode.INVALID_API_KEY, "missing admin token")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise LicenseError(ErrorCode.INVALID_API_KEY, "invalid admin token format")
    token = parts[1].strip()
    payload = decode_admin_token(token)
    admin_id = int(payload.get("sub", 0))
    admin = db.query(AdminUser).filter_by(id=admin_id, status="active").first()
    if admin is None:
        raise LicenseError(ErrorCode.INVALID_SESSION)
    return admin
