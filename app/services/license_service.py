"""License 核心业务服务：生成、激活、验证、状态管理、批量操作。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, LicenseError
from app.core.security import generate_license_id, generate_license_key
from app.core.time_utils import compute_expiry, ensure_aware, extend_expiry, utc_now
from app.models import License, Product, Session as SessionModel


# ---------------------------------------------------------------------------
# 自动过期处理
# ---------------------------------------------------------------------------

def auto_expire(db: Session) -> int:
    """扫描已过期的 ACTIVE 卡密和活跃会话，自动更新状态并撤销会话。返回过期卡密数量。"""
    now = utc_now()
    expired_licenses = db.query(License).filter(
        License.status == "ACTIVE",
        License.expire_at.isnot(None),
        License.expire_at < now,
    ).all()
    count = 0
    for lic in expired_licenses:
        lic.status = "EXPIRED"
        _revoke_all_sessions(db, lic.license_id)
        count += 1
    expired_sessions = db.query(SessionModel).filter(
        SessionModel.status == "active",
        SessionModel.expire_at < now,
    ).all()
    for s in expired_sessions:
        s.status = "expired"
    if count or expired_sessions:
        db.commit()
    return count


def _revoke_all_sessions(db: Session, license_id: str) -> int:
    """撤销指定卡密下的所有活跃会话。"""
    sessions = db.query(SessionModel).filter_by(license_id=license_id, status="active").all()
    for s in sessions:
        s.status = "revoked"
    return len(sessions)


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def get_license_by_key(db: Session, license_key: str) -> Optional[License]:
    return db.query(License).filter_by(license_key=license_key).first()


def get_license_by_id(db: Session, license_id: str) -> Optional[License]:
    return db.query(License).filter_by(license_id=license_id).first()


def get_product_by_api_key(db: Session, api_key: str) -> Optional[Product]:
    return db.query(Product).filter_by(api_key=api_key, status="active").first()


def get_product_by_id(db: Session, product_id: str) -> Optional[Product]:
    return db.query(Product).filter_by(product_id=product_id).first()


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------

def batch_generate(
    db: Session,
    *,
    product_id: str,
    count: int,
    duration: int,
    duration_unit: str,
    remark: Optional[str] = None,
    bind_machine: bool = False,
) -> list[License]:
    product = get_product_by_id(db, product_id)
    if product is None:
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    if product.status != "active":
        raise LicenseError(ErrorCode.PRODUCT_DISABLED)

    licenses: list[License] = []
    now = utc_now()
    for _ in range(count):
        key = generate_license_key()
        lic = License(
            license_id=generate_license_id(),
            license_key=key,
            product_id=product_id,
            duration=duration,
            duration_unit=duration_unit,
            status="UNUSED",
            remark=remark,
            bind_machine=bind_machine,
            created_at=now,
        )
        db.add(lic)
        licenses.append(lic)
    db.commit()
    for lic in licenses:
        db.refresh(lic)
    return licenses


# ---------------------------------------------------------------------------
# 激活与验证
# ---------------------------------------------------------------------------

def activate_license(
    db: Session,
    license_key: str,
    product_id: str,
) -> License:
    lic = get_license_by_key(db, license_key)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    if lic.product_id != product_id:
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    now = utc_now()
    if lic.status == "UNUSED":
        lic.activated_at = now
        lic.expire_at = compute_expiry(now, lic.duration, lic.duration_unit)
        lic.status = "ACTIVE"
        db.commit()
        db.refresh(lic)
        return lic
    if lic.status == "DISABLED":
        raise LicenseError(ErrorCode.LICENSE_DISABLED)
    if lic.status == "ACTIVE":
        if lic.expire_at and now > ensure_aware(lic.expire_at):
            lic.status = "EXPIRED"
            db.commit()
            raise LicenseError(ErrorCode.LICENSE_EXPIRED)
        return lic
    if lic.status == "EXPIRED":
        raise LicenseError(ErrorCode.LICENSE_EXPIRED)
    raise LicenseError(ErrorCode.INVALID_LICENSE)


def verify_license(
    db: Session,
    license_key: str,
    product_id: str,
    machine_id: Optional[str] = None,
    force: bool = False,
) -> License:
    lic = get_license_by_key(db, license_key)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    if lic.product_id != product_id:
        raise LicenseError(ErrorCode.INVALID_PRODUCT)
    now = utc_now()
    lic.last_verify_at = now

    if lic.status == "DISABLED":
        db.commit()
        raise LicenseError(ErrorCode.LICENSE_DISABLED)

    if lic.status == "UNUSED":
        lic.activated_at = now
        lic.expire_at = compute_expiry(now, lic.duration, lic.duration_unit)
        lic.status = "ACTIVE"
        db.commit()
        db.refresh(lic)
        return lic

    if lic.status == "ACTIVE":
        if lic.expire_at and now > ensure_aware(lic.expire_at):
            lic.status = "EXPIRED"
            _revoke_all_sessions(db, lic.license_id)
            db.commit()
            raise LicenseError(ErrorCode.LICENSE_EXPIRED)

        if lic.bind_machine and machine_id:
            existing = db.query(SessionModel).filter(
                SessionModel.license_id == lic.license_id,
                SessionModel.status == "active",
            ).first()
            if existing and existing.machine_id and existing.machine_id != machine_id:
                if not force:
                    db.commit()
                    raise LicenseError(
                        ErrorCode.INVALID_LICENSE,
                        "该卡密已绑定其他设备，继续验证将顶替原有设备，是否确认？",
                    )
                existing.status = "revoked"
                db.commit()

        db.commit()
        db.refresh(lic)
        return lic

    if lic.status == "EXPIRED":
        db.commit()
        raise LicenseError(ErrorCode.LICENSE_EXPIRED)

    db.commit()
    raise LicenseError(ErrorCode.INVALID_LICENSE)


# ---------------------------------------------------------------------------
# 状态管理
# ---------------------------------------------------------------------------

def disable_license(db: Session, license_id: str) -> License:
    lic = get_license_by_id(db, license_id)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    lic.status = "DISABLED"
    db.commit()
    db.refresh(lic)
    return lic


def enable_license(db: Session, license_id: str) -> License:
    lic = get_license_by_id(db, license_id)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    if lic.status == "DISABLED":
        if lic.expire_at and utc_now() > ensure_aware(lic.expire_at):
            lic.status = "EXPIRED"
        else:
            lic.status = "ACTIVE" if lic.activated_at else "UNUSED"
    db.commit()
    db.refresh(lic)
    return lic


def extend_license(
    db: Session,
    license_id: str,
    duration: int,
    duration_unit: str,
) -> License:
    lic = get_license_by_id(db, license_id)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    now = utc_now()
    if lic.expire_at and ensure_aware(lic.expire_at) > now:
        base = ensure_aware(lic.expire_at)
    else:
        base = now
    lic.expire_at = extend_expiry(base, duration, duration_unit)
    if lic.status == "EXPIRED":
        lic.status = "ACTIVE"
    if lic.activated_at is None:
        lic.activated_at = now
    db.commit()
    db.refresh(lic)
    return lic


def delete_license(db: Session, license_id: str) -> None:
    lic = get_license_by_id(db, license_id)
    if lic is None:
        raise LicenseError(ErrorCode.LICENSE_NOT_FOUND)
    db.delete(lic)
    db.commit()


def batch_disable(db: Session, license_ids: list[str]) -> int:
    count = (
        db.query(License)
        .filter(License.license_id.in_(license_ids))
        .update({License.status: "DISABLED"}, synchronize_session=False)
    )
    db.commit()
    return count


def batch_enable(db: Session, license_ids: list[str]) -> int:
    lics = db.query(License).filter(License.license_id.in_(license_ids)).all()
    now = utc_now()
    count = 0
    for lic in lics:
        if lic.status == "DISABLED":
            if lic.expire_at and now > ensure_aware(lic.expire_at):
                lic.status = "EXPIRED"
            else:
                lic.status = "ACTIVE" if lic.activated_at else "UNUSED"
            count += 1
    db.commit()
    return count


def batch_extend(db: Session, license_ids: list[str], duration: int, duration_unit: str) -> int:
    lics = db.query(License).filter(License.license_id.in_(license_ids)).all()
    now = utc_now()
    count = 0
    for lic in lics:
        base = ensure_aware(lic.expire_at) if (lic.expire_at and ensure_aware(lic.expire_at) > now) else now
        lic.expire_at = extend_expiry(base, duration, duration_unit)
        if lic.status == "EXPIRED":
            lic.status = "ACTIVE"
        if lic.activated_at is None:
            lic.activated_at = now
        count += 1
    db.commit()
    return count


# ---------------------------------------------------------------------------
# 分页查询
# ---------------------------------------------------------------------------

def query_licenses(
    db: Session,
    *,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> tuple[list[License], int]:
    q = db.query(License)
    if product_id:
        q = q.filter(License.product_id == product_id)
    if status:
        q = q.filter(License.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(License.license_key.like(like) | License.license_id.like(like) | License.remark.like(like))
    if start_time:
        q = q.filter(License.created_at >= start_time)
    if end_time:
        q = q.filter(License.created_at <= end_time)
    total = q.count()
    items = q.order_by(License.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
