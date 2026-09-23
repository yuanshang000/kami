"""管理后台认证 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import create_admin_token, get_current_admin, get_request_id
from app.core.ip import get_client_ip
from app.core.security import verify_password
from app.core.time_utils import utc_now, utc_now_ts
from app.database.database import get_db
from app.models import AdminUser
from app.schemas.admin import AdminLoginRequest, ChangePasswordRequest
from app.schemas.response import success_response
from app.services import admin_log_service

router = APIRouter(prefix="/api/v1/admin/auth", tags=["admin-auth"])


@router.post("/login")
def login(
    body: AdminLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    admin = db.query(AdminUser).filter_by(username=body.username, status="active").first()
    if admin is None or not verify_password(body.password, admin.password_hash):
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.INVALID_API_KEY, "invalid credentials")
    token = create_admin_token(admin)
    admin.last_login_at = utc_now()
    db.commit()
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="login", ip=get_client_ip(request),
    )
    data = {
        "token": token,
        "username": admin.username,
        "role": admin.role,
        "expires_at": utc_now_ts() + 480 * 60,
    }
    return success_response(data, request_id)


@router.post("/logout")
def logout(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="logout", ip=get_client_ip(request),
    )
    return success_response({"logged_out": True}, request_id)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    if not verify_password(body.old_password, admin.password_hash):
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.INVALID_API_KEY, "old password incorrect")
    from app.core.security import hash_password
    admin.password_hash = hash_password(body.new_password)
    db.commit()
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="change_password", ip=get_client_ip(request),
    )
    return success_response({"changed": True}, request_id)
