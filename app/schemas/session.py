"""Session 与 UsageLog 相关 schemas。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: int
    session_id: str
    license_id: str
    product_id: str
    machine_id: Optional[str] = None
    client_version: Optional[str] = None
    ip: Optional[str] = None
    created_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    expire_at: Optional[str] = None
    status: str


class UsageLogOut(BaseModel):
    id: int
    license_id: Optional[str] = None
    product_id: Optional[str] = None
    session_id: Optional[str] = None
    ip: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    machine_id: Optional[str] = None
    client_version: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    action: Optional[str] = None
    request_time: Optional[str] = None
    result: str
    error_code: Optional[int] = None
