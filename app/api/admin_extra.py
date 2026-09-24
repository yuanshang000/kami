"""管理后台 Product、Session、Logs、Dashboard API。"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_request_id
from app.core.ip import get_client_ip
from app.core.security import generate_api_key
from app.core.time_utils import to_iso8601, utc_now
from app.database.database import get_db
from app.models import AdminLog, AdminUser, License, Product, Session as SessionModel, UsageLog
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.response import success_response
from app.services import admin_log_service
from app.services.license_service import auto_expire

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@router.get("/products")
def list_products(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    products = db.query(Product).order_by(Product.id.desc()).all()
    data = [
        {
            "id": p.id,
            "product_id": p.product_id,
            "product_name": p.product_name,
            "api_key": p.api_key,
            "status": p.status,
            "description": p.description,
            "created_at": to_iso8601(p.created_at),
        }
        for p in products
    ]
    return success_response({"items": data, "total": len(data)}, request_id)


@router.post("/products")
def create_product(
    body: ProductCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    if db.query(Product).filter_by(product_id=body.product_id).first():
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.INVALID_REQUEST, "product_id already exists")
    api_key = generate_api_key()
    product = Product(
        product_id=body.product_id,
        product_name=body.product_name,
        api_key=api_key,
        status="active",
        description=body.description,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="create_product", target_type="product", target_id=body.product_id,
        ip=get_client_ip(request),
    )
    data = {
        "id": product.id,
        "product_id": product.product_id,
        "product_name": product.product_name,
        "api_key": product.api_key,
        "status": product.status,
        "description": product.description,
        "created_at": to_iso8601(product.created_at),
    }
    return success_response(data, request_id)


@router.get("/products/{product_id}")
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    p = db.query(Product).filter_by(product_id=product_id).first()
    if p is None:
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    data = {
        "id": p.id,
        "product_id": p.product_id,
        "product_name": p.product_name,
        "api_key": p.api_key,
        "status": p.status,
        "description": p.description,
        "created_at": to_iso8601(p.created_at),
    }
    return success_response(data, request_id)


@router.patch("/products/{product_id}")
def update_product(
    product_id: str,
    body: ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    p = db.query(Product).filter_by(product_id=product_id).first()
    if p is None:
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    if body.product_name is not None:
        p.product_name = body.product_name
    if body.description is not None:
        p.description = body.description
    if body.status is not None:
        p.status = body.status
    db.commit()
    db.refresh(p)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="update_product", target_type="product", target_id=product_id,
        ip=get_client_ip(request), details=body.model_dump_json(),
    )
    data = {
        "id": p.id,
        "product_id": p.product_id,
        "product_name": p.product_name,
        "api_key": p.api_key,
        "status": p.status,
        "description": p.description,
    }
    return success_response(data, request_id)


@router.post("/products/{product_id}/regenerate-key")
def regenerate_api_key(
    product_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    p = db.query(Product).filter_by(product_id=product_id).first()
    if p is None:
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    p.api_key = generate_api_key()
    db.commit()
    db.refresh(p)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="regenerate_api_key", target_type="product", target_id=product_id,
        ip=get_client_ip(request),
    )
    return success_response({"api_key": p.api_key}, request_id)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions")
def list_sessions(
    license_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    auto_expire(db)
    q = db.query(SessionModel)
    if license_id:
        q = q.filter_by(license_id=license_id)
    if product_id:
        q = q.filter_by(product_id=product_id)
    if status:
        q = q.filter_by(status=status)
    total = q.count()
    items = q.order_by(SessionModel.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "items": [
            {
                "id": s.id,
                "session_id": s.session_id,
                "license_id": s.license_id,
                "product_id": s.product_id,
                "machine_id": s.machine_id,
                "client_version": s.client_version,
                "ip": s.ip,
                "created_at": to_iso8601(s.created_at),
                "last_seen_at": to_iso8601(s.last_seen_at),
                "expire_at": to_iso8601(s.expire_at),
                "status": s.status,
            }
            for s in items
        ],
        "total": total,
    }
    return success_response(data, request_id)


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@router.get("/logs")
def list_logs(
    license_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
    machine_id: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    q = db.query(UsageLog)
    if license_id:
        q = q.filter_by(license_id=license_id)
    if product_id:
        q = q.filter_by(product_id=product_id)
    if ip:
        q = q.filter_by(ip=ip)
    if machine_id:
        q = q.filter_by(machine_id=machine_id)
    if result:
        q = q.filter_by(result=result)
    total = q.count()
    items = q.order_by(UsageLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "items": [
            {
                "id": l.id,
                "license_id": l.license_id,
                "product_id": l.product_id,
                "session_id": l.session_id,
                "ip": l.ip,
                "country": l.country,
                "region": l.region,
                "city": l.city,
                "machine_id": l.machine_id,
                "client_version": l.client_version,
                "user_agent": l.user_agent,
                "request_id": l.request_id,
                "action": l.action,
                "request_time": to_iso8601(l.request_time),
                "result": l.result,
                "error_code": l.error_code,
            }
            for l in items
        ],
        "total": total,
    }
    return success_response(data, request_id)


@router.get("/admin-logs")
def list_admin_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    q = db.query(AdminLog)
    total = q.count()
    items = q.order_by(AdminLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "items": [
            {
                "id": l.id,
                "admin_username": l.admin_username,
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "ip": l.ip,
                "created_at": to_iso8601(l.created_at),
                "details": l.details,
                "result": l.result,
            }
            for l in items
        ],
        "total": total,
    }
    return success_response(data, request_id)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    now = utc_now()
    auto_expire(db)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = db.query(License).count()
    unused = db.query(License).filter_by(status="UNUSED").count()
    active = db.query(License).filter_by(status="ACTIVE").count()
    expired = db.query(License).filter_by(status="EXPIRED").count()
    disabled = db.query(License).filter_by(status="DISABLED").count()
    today_verif = db.query(UsageLog).filter(UsageLog.request_time >= today_start).count()
    today_activ = db.query(UsageLog).filter(
        UsageLog.action == "activate", UsageLog.request_time >= today_start
    ).count()
    active_sessions = db.query(SessionModel).filter_by(status="active").count()
    data = {
        "total_licenses": total,
        "unused_count": unused,
        "active_count": active,
        "expired_count": expired,
        "disabled_count": disabled,
        "today_verifications": today_verif,
        "today_activations": today_activ,
        "active_sessions": active_sessions,
    }
    return success_response(data, request_id)
