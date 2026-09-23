"""使用日志记录服务。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.models import UsageLog


def record_usage(
    db: Session,
    *,
    license_id: Optional[str],
    product_id: Optional[str],
    session_id: Optional[str],
    ip: Optional[str],
    country: Optional[str],
    region: Optional[str],
    city: Optional[str],
    machine_id: Optional[str],
    client_version: Optional[str],
    user_agent: Optional[str],
    request_id: Optional[str],
    action: str,
    result: str = "SUCCESS",
    error_code: Optional[int] = None,
) -> UsageLog:
    log = UsageLog(
        license_id=license_id,
        product_id=product_id,
        session_id=session_id,
        ip=ip,
        country=country,
        region=region,
        city=city,
        machine_id=machine_id,
        client_version=client_version,
        user_agent=user_agent,
        request_id=request_id,
        action=action,
        request_time=utc_now(),
        result=result,
        error_code=error_code,
    )
    db.add(log)
    db.commit()
    return log
