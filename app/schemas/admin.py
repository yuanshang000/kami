"""Admin 相关 schemas。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AdminLoginResponse(BaseModel):
    token: str
    username: str
    role: str
    expires_at: int


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminLogOut(BaseModel):
    id: int
    admin_username: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    ip: Optional[str] = None
    created_at: Optional[str] = None
    details: Optional[str] = None
    result: str


class DashboardOut(BaseModel):
    total_licenses: int
    unused_count: int
    active_count: int
    expired_count: int
    disabled_count: int
    today_verifications: int
    today_activations: int
    active_sessions: int
