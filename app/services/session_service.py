"""Session 管理服务：创建、验证、心跳、撤销。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorCode, LicenseError
from app.core.security import generate_session_id, generate_session_token, hash_token
from app.core.time_utils import ensure_aware, utc_now
from app.models import Session as SessionModel


def create_session(
    db: Session,
    *,
    license_id: str,
    product_id: str,
    machine_id: Optional[str],
    client_version: Optional[str],
    ip: Optional[str],
) -> tuple[SessionModel, str]:
    """创建新 session，返回 (session_model, plaintext_token)。"""
    now = utc_now()
    from datetime import timedelta
    expire = now + timedelta(seconds=settings.session_expire_seconds)
    token = generate_session_token()
    session = SessionModel(
        session_id=generate_session_id(),
        license_id=license_id,
        product_id=product_id,
        session_token_hash=hash_token(token),
        machine_id=machine_id,
        client_version=client_version,
        ip=ip,
        created_at=now,
        last_seen_at=now,
        expire_at=expire,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, token


def validate_session(
    db: Session,
    session_id: str,
    session_token: Optional[str] = None,
) -> SessionModel:
    session = db.query(SessionModel).filter_by(session_id=session_id).first()
    if session is None:
        raise LicenseError(ErrorCode.INVALID_SESSION)
    if session.status != "active":
        raise LicenseError(ErrorCode.INVALID_SESSION)
    now = utc_now()
    if session.expire_at and now > ensure_aware(session.expire_at):
        session.status = "expired"
        db.commit()
        raise LicenseError(ErrorCode.SESSION_EXPIRED)
    if session_token:
        if not _safe_compare(hash_token(session_token), session.session_token_hash):
            raise LicenseError(ErrorCode.INVALID_SESSION)
    session.last_seen_at = now
    db.commit()
    db.refresh(session)
    return session


def revoke_session(db: Session, session_id: str) -> None:
    session = db.query(SessionModel).filter_by(session_id=session_id).first()
    if session is not None:
        session.status = "revoked"
        db.commit()


def revoke_license_sessions(db: Session, license_id: str) -> int:
    sessions = db.query(SessionModel).filter_by(license_id=license_id, status="active").all()
    count = 0
    for s in sessions:
        s.status = "revoked"
        count += 1
    if count:
        db.commit()
    return count


import secrets as _secrets


def _safe_compare(a: str, b: str) -> bool:
    return _secrets.compare_digest(a, b)
