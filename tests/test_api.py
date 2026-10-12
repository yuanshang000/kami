"""API 集成测试：完整 verify 流程 + 签名验证。"""
from __future__ import annotations

import base64
import json

from app.core.crypto import crypto_service
from app.core.security import generate_api_key
from app.core.time_utils import utc_now_ts
from app.models import AdminUser, Product
from app.services.license_service import batch_generate


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _setup_product_and_license(db_session):
    p = Product(
        product_id="mytool",
        product_name="MyTool",
        api_key=generate_api_key(),
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    licenses = batch_generate(db_session, product_id="mytool", count=1, duration=30, duration_unit="minute")
    return p, licenses[0]


def test_verify_endpoint_success(client, db_session):
    product, lic = _setup_product_and_license(db_session)
    resp = client.post(
        "/api/v1/license/verify",
        headers={
            "Authorization": f"Bearer {product.api_key}",
            "X-Product-ID": "mytool",
            "X-Client-Version": "1.0.0",
        },
        json={
            "license_key": lic.license_key,
            "machine_id": "machine-test-001",
            "client_version": "1.0.0",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 0
    assert "authorization" in body["data"]
    assert "session_id" in body["data"]

    # 验证签名
    payload = crypto_service.verify_payload(body["data"]["authorization"])
    assert payload["status"] == "authorized"
    assert payload["product_id"] == "mytool"
    assert payload["license_id"] == lic.license_id


def test_verify_endpoint_not_found(client, db_session):
    product, _ = _setup_product_and_license(db_session)
    resp = client.post(
        "/api/v1/license/verify",
        headers={
            "Authorization": f"Bearer {product.api_key}",
            "X-Product-ID": "mytool",
        },
        json={"license_key": "nonexistent_key_abcdef", "machine_id": "m1"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["code"] == 4002


def test_verify_invalid_api_key(client, db_session):
    product, lic = _setup_product_and_license(db_session)
    resp = client.post(
        "/api/v1/license/verify",
        headers={
            "Authorization": "Bearer app_invalid_key_xxxxxx",
            "X-Product-ID": "mytool",
        },
        json={"license_key": lic.license_key, "machine_id": "m1"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 4006


def test_heartbeat_after_verify(client, db_session):
    product, lic = _setup_product_and_license(db_session)
    # 先 verify
    resp = client.post(
        "/api/v1/license/verify",
        headers={"Authorization": f"Bearer {product.api_key}", "X-Product-ID": "mytool"},
        json={"license_key": lic.license_key, "machine_id": "m1"},
    )
    session_id = resp.json()["data"]["session_id"]
    session_token = resp.json()["data"]["session_token"]

    # heartbeat
    resp2 = client.post(
        "/api/v1/license/heartbeat",
        headers={"Authorization": f"Bearer {product.api_key}", "X-Product-ID": "mytool"},
        json={"session_id": session_id, "session_token": session_token, "machine_id": "m1"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True


def test_admin_login_and_dashboard(client, db_session):
    resp = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]

    resp2 = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data = resp2.json()["data"]
    assert "total_licenses" in data
    assert "active_sessions" in data


def _make_expired_token(admin_id: int = 1) -> str:
    """签发一个已过期的管理员 JWT。"""
    from jose import jwt
    from app.core.config import settings
    return jwt.encode(
        {
            "sub": str(admin_id),
            "username": "admin",
            "role": "admin",
            "exp": utc_now_ts() - 60,
            "iat": utc_now_ts() - 3600,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def test_admin_expired_token_returns_session_expired(client):
    """过期 token 必须返回 4010，让前端能识别为「会话过期」而非普通错误。"""
    resp = client.get(
        "/api/v1/admin/auth/session",
        headers={"Authorization": f"Bearer {_make_expired_token()}"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["code"] == 4010


def test_admin_missing_token_returns_session_expired(client):
    resp = client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401
    assert resp.json()["code"] == 4010


def test_admin_garbage_token_returns_invalid_session(client):
    resp = client.get(
        "/api/v1/admin/auth/session",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 4009


def test_admin_session_and_refresh(client):
    """登录后 session 接口可用，refresh 可换出新 token 且新 token 仍可用。"""
    login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    )
    token = login.json()["data"]["token"]
    auth = {"Authorization": f"Bearer {token}"}

    info = client.get("/api/v1/admin/auth/session", headers=auth)
    assert info.status_code == 200
    assert info.json()["data"]["username"] == "admin"
    assert info.json()["data"]["expires_at"] > 0

    refreshed = client.post("/api/v1/admin/auth/refresh", headers=auth)
    assert refreshed.status_code == 200
    new_token = refreshed.json()["data"]["token"]
    assert new_token

    after = client.get("/api/v1/admin/auth/session", headers={"Authorization": f"Bearer {new_token}"})
    assert after.status_code == 200


def test_admin_disabled_account_invalidates_token(client, db_session):
    """管理员被禁用后，已有 token 立即失效（4009），前端会跳登录页。"""
    login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    )
    token = login.json()["data"]["token"]

    admin = db_session.query(AdminUser).filter_by(username="admin").first()
    admin.status = "disabled"
    db_session.commit()

    resp = client.get("/api/v1/admin/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 4009

    admin.status = "active"
    db_session.commit()


def test_admin_login_wrong_password_not_session_error(client):
    """登录接口自身返回 4006，前端据此展示错误而不触发跳转逻辑。"""
    resp = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 4006
