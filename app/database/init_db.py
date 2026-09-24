"""数据库初始化：建表、创建默认管理员。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.database.database import SessionLocal, engine
from app.models import AdminUser, Base


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_add_bind_machine()
    _ensure_default_admin()


def _migrate_add_bind_machine() -> None:
    """为已有 licenses 表添加 bind_machine 列（如果不存在）。"""
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    if "licenses" not in inspector.get_table_names():
        return
    columns = [c["name"] for c in inspector.get_columns("licenses")]
    if "bind_machine" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE licenses ADD COLUMN bind_machine BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()


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
