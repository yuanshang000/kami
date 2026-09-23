"""密码哈希、API Key 生成、License Key 生成、Session Token 生成。"""
from __future__ import annotations

import base64
import hashlib
import secrets
import string

from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# License key alphabet: letters + digits, URL-safe
_LICENSE_ALPHABET = string.ascii_letters + string.digits


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def generate_license_key(length: int | None = None) -> str:
    """生成随机 Base64 风格的卡密，不含业务信息。"""
    n = length or settings.license_key_length
    raw = secrets.token_bytes(n)
    key = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    prefix = settings.license_key_prefix
    return f"{prefix}{key}" if prefix else key


def generate_api_key() -> str:
    """生成产品 API Key，前缀 app_。"""
    return "app_" + secrets.token_urlsafe(32)


def generate_session_token() -> str:
    """生成高强度随机 session token（返回明文，服务端只存 hash）。"""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """对 session token 做 SHA-256 哈希存储。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_id() -> str:
    return "sess_" + secrets.token_urlsafe(16)


def generate_license_id() -> str:
    return "L-" + secrets.token_urlsafe(8)


def generate_request_id() -> str:
    import uuid
    return str(uuid.uuid4())


def mask_license_key(key: str) -> str:
    """部分隐藏卡密用于日志展示。"""
    if len(key) <= 12:
        return key[:3] + "..." + key[-3:]
    return key[:6] + "..." + key[-6:]


def constant_time_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
