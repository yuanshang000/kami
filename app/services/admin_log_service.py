"""管理员操作日志服务。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.models import AdminLog


def record_admin_action(
    db: Session,
    *,
    admin_id: Optional[int],
    admin_username: Optional[str],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip: Optional[str] = None,
    details: Optional[str] = None,
    result: str = "SUCCESS",
) -> AdminLog:
    log = AdminLog(
        admin_id=admin_id,
        admin_username=admin_username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip=ip,
        created_at=utc_now(),
        details=details,
        result=result,
    )
    db.add(log)
    db.commit()
    return log
