"""数据库初始化：建表、创建默认管理员。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.database.database import SessionLocal, engine
from app.models import AdminUser, Base


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_default_admin()


def _ensure_default_admin() -> None:
    db: Session = SessionLocal()
    try:
        existing = db.query(AdminUser).filter_by(username=settings.admin_default_username).first()
        if existing is None:
            admin = AdminUser(
                username=settings.admin_default_username,
                password_hash=hash_password(settings.admin_default_password),
                role="super",
                status="active",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


def drop_all() -> None:
    Base.metadata.drop_all(bind=engine)
