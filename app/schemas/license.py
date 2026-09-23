"""License 相关 Pydantic schemas。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LicenseVerifyRequest(BaseModel):
    license_key: str = Field(..., min_length=8, max_length=255)
    machine_id: Optional[str] = Field(None, max_length=255)
    client_version: Optional[str] = Field(None, max_length=64)


class LicenseActivateRequest(BaseModel):
    license_key: str = Field(..., min_length=8, max_length=255)
    machine_id: Optional[str] = Field(None, max_length=255)
    client_version: Optional[str] = Field(None, max_length=64)


class HeartbeatRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    session_token: Optional[str] = Field(None, max_length=128)
    machine_id: Optional[str] = Field(None, max_length=255)
    client_version: Optional[str] = Field(None, max_length=64)


class DeactivateRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    session_token: Optional[str] = Field(None, max_length=128)


class LicenseInfoRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    session_token: Optional[str] = Field(None, max_length=128)


class AuthorizationPayload(BaseModel):
    version: int
    status: str
    license_id: str
    product_id: str
    issued_at: int
    expire_at: int
    server_time: int
    session_id: str
    nonce: str


class LicenseOut(BaseModel):
    id: int
    license_id: str
    license_key: str
    product_id: str
    duration: int
    duration_unit: str
    status: str
    remark: Optional[str] = None
    created_at: Optional[str] = None
    activated_at: Optional[str] = None
    expire_at: Optional[str] = None
    last_verify_at: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    count: int = Field(..., ge=1, le=10000)
    duration: int = Field(..., ge=1, le=100000)
    duration_unit: str = Field("minute", pattern="^(minute|hour|day)$")
    remark: Optional[str] = Field(None, max_length=255)

    @field_validator("duration_unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        if v not in ("minute", "hour", "day"):
            raise ValueError("duration_unit must be minute, hour, or day")
        return v


class BatchIdsRequest(BaseModel):
    license_ids: list[str] = Field(..., min_length=1, max_length=1000)


class ExtendRequest(BaseModel):
    duration: int = Field(..., ge=1, le=100000)
    duration_unit: str = Field("minute", pattern="^(minute|hour|day)$")


class LicenseQuery(BaseModel):
    product_id: Optional[str] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 20
    start_time: Optional[str] = None
    end_time: Optional[str] = None
