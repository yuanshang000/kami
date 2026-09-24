"""管理后台 License 管理 API。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_request_id
from app.core.ip import get_client_ip
from app.core.time_utils import from_iso8601, to_iso8601, utc_now
from app.database.database import get_db
from app.models import AdminUser, License, UsageLog
from app.schemas.license import (
    BatchGenerateRequest,
    BatchIdsRequest,
    ExtendRequest,
    LicenseOut,
)
from app.schemas.response import success_response
from app.services import admin_log_service, license_service, log_service, session_service

router = APIRouter(prefix="/api/v1/admin/licenses", tags=["admin-licenses"])


def _to_out(lic: License) -> dict:
    return {
        "id": lic.id,
        "license_id": lic.license_id,
        "license_key": lic.license_key,
        "product_id": lic.product_id,
        "duration": lic.duration,
        "duration_unit": lic.duration_unit,
        "status": lic.status,
        "remark": lic.remark,
        "bind_machine": lic.bind_machine,
        "created_at": to_iso8601(lic.created_at),
        "activated_at": to_iso8601(lic.activated_at),
        "expire_at": to_iso8601(lic.expire_at),
        "last_verify_at": to_iso8601(lic.last_verify_at),
    }


@router.get("")
def list_licenses(
    product_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    st = from_iso8601(start_time) if start_time else None
    en = from_iso8601(end_time) if end_time else None
    license_service.auto_expire(db)
    items, total = license_service.query_licenses(
        db, product_id=product_id, status=status, keyword=keyword,
        page=page, page_size=page_size, start_time=st, end_time=en,
    )
    data = {"items": [_to_out(i) for i in items], "total": total, "page": page, "page_size": page_size}
    return success_response(data, request_id)


@router.post("/batch-generate")
def batch_generate(
    body: BatchGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    licenses = license_service.batch_generate(
        db,
        product_id=body.product_id,
        count=body.count,
        duration=body.duration,
        duration_unit=body.duration_unit,
        remark=body.remark,
        bind_machine=body.bind_machine,
    )
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="batch_generate", target_type="product", target_id=body.product_id,
        ip=get_client_ip(request),
        details=f"count={body.count}, duration={body.duration} {body.duration_unit}",
    )
    data = {"licenses": [_to_out(l) for l in licenses], "count": len(licenses)}
    return success_response(data, request_id)


@router.post("/batch-enable")
def batch_enable(
    body: BatchIdsRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    count = license_service.batch_enable(db, body.license_ids)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="batch_enable", target_type="license",
        ip=get_client_ip(request), details=f"count={count}",
    )
    return success_response({"enabled": count}, request_id)


@router.post("/batch-disable")
def batch_disable(
    body: BatchIdsRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    count = license_service.batch_disable(db, body.license_ids)
    for lid in body.license_ids:
        session_service.revoke_license_sessions(db, lid)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="batch_disable", target_type="license",
        ip=get_client_ip(request), details=f"count={count}",
    )
    return success_response({"disabled": count}, request_id)


@router.post("/batch-extend")
def batch_extend(
    body: BatchIdsRequest,
    request: Request,
    duration: int = Query(..., ge=1),
    duration_unit: str = Query("minute", pattern="^(minute|hour|day)$"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    count = license_service.batch_extend(db, body.license_ids, duration, duration_unit)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="batch_extend", target_type="license",
        ip=get_client_ip(request), details=f"count={count}, +{duration} {duration_unit}",
    )
    return success_response({"extended": count}, request_id)


@router.get("/{license_id}")
def get_license(
    license_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    lic = license_service.get_license_by_id(db, license_id)
    if lic is None:
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    return success_response(_to_out(lic), request_id)


@router.patch("/{license_id}")
def update_license(
    license_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    lic = license_service.get_license_by_id(db, license_id)
    if lic is None:
        from app.core.errors import LicenseError, ErrorCode
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    if "remark" in body:
        lic.remark = body["remark"]
    if "status" in body:
        if body["status"] == "DISABLED":
            lic.status = "DISABLED"
        elif body["status"] == "ACTIVE":
            lic.status = "ACTIVE"
    db.commit()
    db.refresh(lic)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="update_license", target_type="license", target_id=license_id,
        ip=get_client_ip(request), details=str(body),
    )
    return success_response(_to_out(lic), request_id)


@router.delete("/{license_id}")
def delete_license(
    license_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    license_service.delete_license(db, license_id)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="delete_license", target_type="license", target_id=license_id,
        ip=get_client_ip(request),
    )
    return success_response({"deleted": True}, request_id)


@router.post("/{license_id}/extend")
def extend_license(
    license_id: str,
    body: ExtendRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    lic = license_service.extend_license(db, license_id, body.duration, body.duration_unit)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="extend_license", target_type="license", target_id=license_id,
        ip=get_client_ip(request), details=f"+{body.duration} {body.duration_unit}",
    )
    return success_response(_to_out(lic), request_id)


@router.post("/{license_id}/disable")
def disable_license(
    license_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    lic = license_service.disable_license(db, license_id)
    session_service.revoke_license_sessions(db, license_id)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="disable_license", target_type="license", target_id=license_id,
        ip=get_client_ip(request),
    )
    return success_response(_to_out(lic), request_id)


@router.post("/{license_id}/enable")
def enable_license(
    license_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    lic = license_service.enable_license(db, license_id)
    admin_log_service.record_admin_action(
        db, admin_id=admin.id, admin_username=admin.username,
        action="enable_license", target_type="license", target_id=license_id,
        ip=get_client_ip(request),
    )
    return success_response(_to_out(lic), request_id)


@router.get("/{license_id}/logs")
def license_logs(
    license_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    q = db.query(UsageLog).filter_by(license_id=license_id)
    total = q.count()
    items = q.order_by(UsageLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "items": [
            {
                "id": l.id,
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


@router.post("/export")
def export_licenses(
    body: dict,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    request_id: str = Depends(get_request_id),
):
    fmt = body.get("format", "txt")
    product_id = body.get("product_id")
    status = body.get("status")
    license_ids = body.get("license_ids")
    if license_ids:
        items = (
            db.query(License)
            .filter(License.license_id.in_(license_ids))
            .order_by(License.id.desc())
            .all()
        )
    else:
        items, _ = license_service.query_licenses(
            db, product_id=product_id, status=status, page=1, page_size=100000
        )
    keys = [l.license_key for l in items]
    if fmt == "csv":
        lines = ["license_key,license_id,product_id,status,duration,duration_unit,created_at,expire_at"]
        for l in items:
            lines.append(
                f"{l.license_key},{l.license_id},{l.product_id},{l.status},"
                f"{l.duration},{l.duration_unit},{to_iso8601(l.created_at)},{to_iso8601(l.expire_at)}"
            )
        content = "\n".join(lines)
    else:
        content = "\n".join(keys)
    return success_response({"format": fmt, "count": len(keys), "content": content}, request_id)
