"""SQLAlchemy 模型基类与所有表定义。"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# SQLite 不支持 BigInteger 自增主键，用 variant 处理
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(64), unique=True, nullable=False, index=True)
    product_name = Column(String(128), nullable=False)
    api_key = Column(String(128), unique=True, nullable=False, index=True)
    api_key_hash = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, default="active")  # active|disabled
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    licenses = relationship("License", back_populates="product")


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    license_id = Column(String(64), unique=True, nullable=False, index=True)
    license_key = Column(String(255), unique=True, nullable=False, index=True)
    product_id = Column(String(64), ForeignKey("products.product_id"), nullable=False, index=True)
    duration = Column(Integer, nullable=False)
    duration_unit = Column(String(16), nullable=False, default="minute")
    status = Column(String(16), nullable=False, default="UNUSED", index=True)
    # UNUSED | ACTIVE | EXPIRED | DISABLED
    remark = Column(String(255), nullable=True)
    bind_machine = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    expire_at = Column(DateTime(timezone=True), nullable=True)
    last_verify_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("Product", back_populates="licenses")
    sessions = relationship("Session", back_populates="license")

    __table_args__ = (
        Index("ix_licenses_product_status", "product_id", "status"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    license_id = Column(String(64), ForeignKey("licenses.license_id"), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    session_token_hash = Column(String(128), nullable=False)
    machine_id = Column(String(255), nullable=True)
    client_version = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    expire_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, default="active", index=True)
    # active | expired | revoked

    license = relationship("License", back_populates="sessions")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    license_id = Column(String(64), nullable=True, index=True)
    product_id = Column(String(64), nullable=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    ip = Column(String(64), nullable=True, index=True)
    country = Column(String(64), nullable=True)
    region = Column(String(64), nullable=True)
    city = Column(String(128), nullable=True)
    machine_id = Column(String(255), nullable=True, index=True)
    client_version = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    action = Column(String(32), nullable=True)  # verify|activate|heartbeat|deactivate|info
    request_time = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    result = Column(String(16), nullable=False, default="SUCCESS")
    error_code = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_usage_logs_time", "request_time"),
        Index("ix_usage_logs_license_time", "license_id", "request_time"),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="admin")  # super|admin|readonly
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=True, index=True)
    admin_username = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=True)
    target_id = Column(String(128), nullable=True)
    ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    details = Column(Text, nullable=True)
    result = Column(String(16), nullable=False, default="SUCCESS")
