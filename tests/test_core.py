"""核心工具单元测试：crypto、security、time_utils、errors。"""
from __future__ import annotations

import base64

from app.core.crypto import crypto_service
from app.core.security import generate_license_key, generate_api_key, hash_password, verify_password


def test_license_key_generation():
    key = generate_license_key(32)
    assert len(key) > 0
    key2 = generate_license_key(32)
    assert key != key2


def test_api_key_generation():
    ak = generate_api_key()
    assert ak.startswith("app_")
    assert len(ak) > 10


def test_password_hash_verify():
    h = hash_password("mypassword")
    assert verify_password("mypassword", h)
    assert not verify_password("wrong", h)


def test_ed25519_sign_verify_roundtrip():
    payload = {"version": 1, "status": "authorized", "license_id": "L-test"}
    signed = crypto_service.sign_payload(payload)
    result = crypto_service.verify_payload(signed)
    assert result["status"] == "authorized"
    assert result["license_id"] == "L-test"


def test_ed25519_tamper_detection():
    payload = {"version": 1, "status": "authorized"}
    signed = crypto_service.sign_payload(payload)
    # 篡改最后一个字符
    tampered = signed[:-1] + ("A" if signed[-1] != "A" else "B")
    from app.core.errors import LicenseError, ErrorCode
    try:
        crypto_service.verify_payload(tampered)
        assert False, "should have raised"
    except LicenseError as e:
        assert e.code == ErrorCode.INVALID_SIGNATURE
