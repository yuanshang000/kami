"""Product 相关 schemas。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64, pattern="^[a-zA-Z0-9_-]+$")
    product_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    status: Optional[str] = Field(None, pattern="^(active|disabled)$")


class ProductOut(BaseModel):
    id: int
    product_id: str
    product_name: str
    api_key: str
    status: str
    description: Optional[str] = None
    created_at: Optional[str] = None
