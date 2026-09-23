"""客户端 License API: verify / activate / heartbeat / deactivate / info。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.crypto import crypto_service
from app.core.errors import ErrorCode, LicenseError
from app.core.ip import get_client_ip
from app.core.rate_limit import rate_limiter
from app.core.security import generate_request_id
from app.core.time_utils import ensure_aware, to_iso8601, utc_now, utc_now_ts
from app.database.database import get_db
from app.models import Product
from app.schemas.license import (
    DeactivateRequest,
    HeartbeatRequest,
    LicenseActivateRequest,
    LicenseInfoRequest,
    LicenseVerifyRequest,
)
from app.schemas.response import success_response
from app.api.deps import get_api_key_product, get_request_id
from app.services import license_service, log_service, session_service
from app.services.geo_service import geo_service

router = APIRouter(prefix="/api/v1/license", tags=["license"])


def _build_authorization(lic, product: Product, session_id: str) -> str:
    payload = {
        "version": 1,
        "status": "authorized",
        "license_id": lic.license_id,
        "product_id": product.product_id,
        "issued_at": utc_now_ts(),
        "expire_at": int(ensure_aware(lic.expire_at).timestamp()) if lic.expire_at else 0,
        "server_time": utc_now_ts(),
        "session_id": session_id,
        "nonce": crypto_service.generate_nonce(),
    }
    return crypto_service.sign_payload(payload)


def _resolve_product_id(
    header_product_id: Optional[str],
    body_product_id: Optional[str],
    product: Product,
) -> str:
    pid = header_product_id or body_product_id
    if pid is None:
        return product.product_id
    if pid != product.product_id:
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    return pid


# ---------------------------------------------------------------------------
# POST /verify
# ---------------------------------------------------------------------------

@router.post("/verify")
def verify_license(
    request: Request,
    body: LicenseVerifyRequest,
    db: Session = Depends(get_db),
    product: Product = Depends(get_api_key_product),
    request_id: str = Depends(get_request_id),
    x_product_id: Optional[str] = Header(None, alias="X-Product-ID"),
    x_client_version: Optional[str] = Header(None, alias="X-Client-Version"),
):
    ip = get_client_ip(request)
    rate_limiter.check_ip(ip)
    rate_limiter.check_api_key(product.api_key)

    product_id = _resolve_product_id(x_product_id, None, product)
    client_version = body.client_version or x_client_version
    user_agent = request.headers.get("User-Agent", "")

    try:
        lic = license_service.verify_license(db, body.license_key, product_id)
    except LicenseError as e:
        _log_usage(db, lic_id=None, product_id=product_id, ip=ip, body=body,
                   client_version=client_version, user_agent=user_agent,
                   request_id=request_id, action="verify", error=e)
        raise

    session, token = session_service.create_session(
        db,
        license_id=lic.license_id,
        product_id=product_id,
        machine_id=body.machine_id,
        client_version=client_version,
        ip=ip,
    )
    country, region, city = geo_service.lookup(ip)
    log_service.record_usage(
        db,
        license_id=lic.license_id,
        product_id=product_id,
        session_id=session.session_id,
        ip=ip,
        country=country,
        region=region,
        city=city,
        machine_id=body.machine_id,
        client_version=client_version,
        user_agent=user_agent,
        request_id=request_id,
        action="verify",
    )
    authorization = _build_authorization(lic, product, session.session_id)
    data = {
        "authorization": authorization,
        "session_id": session.session_id,
        "session_token": token,
        "expire_at": to_iso8601(lic.expire_at),
        "server_time": to_iso8601(utc_now()),
    }
    return success_response(data, request_id)


# ---------------------------------------------------------------------------
# POST /activate
# ---------------------------------------------------------------------------

@router.post("/activate")
def activate_license(
    request: Request,
    body: LicenseActivateRequest,
    db: Session = Depends(get_db),
    product: Product = Depends(get_api_key_product),
    request_id: str = Depends(get_request_id),
    x_product_id: Optional[str] = Header(None, alias="X-Product-ID"),
    x_client_version: Optional[str] = Header(None, alias="X-Client-Version"),
):
    ip = get_client_ip(request)
    rate_limiter.check_ip(ip)
    rate_limiter.check_api_key(product.api_key)

    product_id = _resolve_product_id(x_product_id, None, product)
    client_version = body.client_version or x_client_version
    user_agent = request.headers.get("User-Agent", "")

    try:
        lic = license_service.activate_license(db, body.license_key, product_id)
    except LicenseError as e:
        _log_usage(db, lic_id=None, product_id=product_id, ip=ip, body=body,
                   client_version=client_version, user_agent=user_agent,
                   request_id=request_id, action="activate", error=e)
        raise

    session, token = session_service.create_session(
        db,
        license_id=lic.license_id,
        product_id=product_id,
        machine_id=body.machine_id,
        client_version=client_version,
        ip=ip,
    )
    country, region, city = geo_service.lookup(ip)
    log_service.record_usage(
        db,
        license_id=lic.license_id,
        product_id=product_id,
        session_id=session.session_id,
        ip=ip,
        country=country,
        region=region,
        city=city,
        machine_id=body.machine_id,
        client_version=client_version,
        user_agent=user_agent,
        request_id=request_id,
        action="activate",
    )
    authorization = _build_authorization(lic, product, session.session_id)
    data = {
        "authorization": authorization,
        "session_id": session.session_id,
        "session_token": token,
        "expire_at": to_iso8601(lic.expire_at),
        "server_time": to_iso8601(utc_now()),
    }
    return success_response(data, request_id)


# ---------------------------------------------------------------------------
# POST /heartbeat
# ---------------------------------------------------------------------------

@router.post("/heartbeat")
def heartbeat(
    request: Request,
    body: HeartbeatRequest,
    db: Session = Depends(get_db),
    product: Product = Depends(get_api_key_product),
    request_id: str = Depends(get_request_id),
    x_client_version: Optional[str] = Header(None, alias="X-Client-Version"),
):
    ip = get_client_ip(request)
    rate_limiter.check_ip(ip)
    rate_limiter.check_api_key(product.api_key)

    client_version = body.client_version or x_client_version
    user_agent = request.headers.get("User-Agent", "")

    try:
        session = session_service.validate_session(db, body.session_id, body.session_token)
    except LicenseError as e:
        log_service.record_usage(
            db, license_id=None, product_id=product.product_id,
            session_id=body.session_id, ip=ip, country=None, region=None, city=None,
            machine_id=body.machine_id, client_version=client_version,
            user_agent=user_agent, request_id=request_id, action="heartbeat",
            result="FAILED", error_code=int(e.code),
        )
        raise

    if session.product_id != product.product_id:
        raise LicenseError(ErrorCode.INVALID_PRODUCT)

    try:
        lic = license_service.verify_license(db, _get_license_key_by_id(db, session.license_id), product.product_id)
    except LicenseError as e:
        log_service.record_usage(
            db, license_id=session.license_id, product_id=product.product_id,
            session_id=session.session_id, ip=ip, country=None, region=None, city=None,
            machine_id=body.machine_id, client_version=client_version,
            user_agent=user_agent, request_id=request_id, action="heartbeat",
            result="FAILED", error_code=int(e.code),
        )
        raise

    country, region, city = geo_service.lookup(ip)
    log_service.record_usage(
        db,
        license_id=lic.license_id,
        product_id=product.product_id,
        session_id=session.session_id,
        ip=ip,
        country=country,
        region=region,
        city=city,
        machine_id=body.machine_id,
        client_version=client_version,
        user_agent=user_agent,
        request_id=request_id,
        action="heartbeat",
    )
    authorization = _build_authorization(lic, product, session.session_id)
    data = {
        "authorization": authorization,
        "session_id": session.session_id,
        "expire_at": to_iso8601(lic.expire_at),
        "server_time": to_iso8601(utc_now()),
    }
    return success_response(data, request_id)


# ---------------------------------------------------------------------------
# POST /deactivate
# ---------------------------------------------------------------------------

@router.post("/deactivate")
def deactivate(
    request: Request,
    body: DeactivateRequest,
    db: Session = Depends(get_db),
    product: Product = Depends(get_api_key_product),
    request_id: str = Depends(get_request_id),
):
    ip = get_client_ip(request)
    session_service.revoke_session(db, body.session_id)
    log_service.record_usage(
        db, license_id=None, product_id=product.product_id,
        session_id=body.session_id, ip=ip, country=None, region=None, city=None,
        machine_id=None, client_version=None,
        user_agent=request.headers.get("User-Agent", ""),
        request_id=request_id, action="deactivate",
    )
    return success_response({"deactivated": True}, request_id)


# ---------------------------------------------------------------------------
# GET /info
# ---------------------------------------------------------------------------

@router.get("/info")
def license_info(
    request: Request,
    session_id: str,
    session_token: Optional[str] = None,
    db: Session = Depends(get_db),
    product: Product = Depends(get_api_key_product),
    request_id: str = Depends(get_request_id),
):
    ip = get_client_ip(request)
    session = session_service.validate_session(db, session_id, session_token)
    if session.product_id != product.product_id:
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    lic = license_service.get_license_by_id(db, session.license_id)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    data = {
        "product_id": product.product_id,
        "license_id": lic.license_id,
        "status": lic.status,
        "activated_at": to_iso8601(lic.activated_at),
        "expire_at": to_iso8601(lic.expire_at),
        "server_time": to_iso8601(utc_now()),
    }
    return success_response(data, request_id)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _get_license_key_by_id(db: Session, license_id: str) -> str:
    from app.models import License
    lic = db.query(License).filter_by(license_id=license_id).first()
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    return lic.license_key


def _log_usage(
    db: Session,
    *,
    lic_id: Optional[str],
    product_id: str,
    ip: str,
    body,
    client_version: Optional[str],
    user_agent: str,
    request_id: str,
    action: str,
    error: LicenseError,
) -> None:
    country, region, city = geo_service.lookup(ip)
    machine_id = getattr(body, "machine_id", None)
    log_service.record_usage(
        db,
        license_id=lic_id,
        product_id=product_id,
        session_id=None,
        ip=ip,
        country=country,
        region=region,
        city=city,
        machine_id=machine_id,
        client_version=client_version,
        user_agent=user_agent,
        request_id=request_id,
        action=action,
        result="FAILED",
        error_code=int(error.code),
    )
