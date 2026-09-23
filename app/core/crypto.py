"""Ed25519 签名与授权载荷封装。

格式: base64url(version_b64.payload_b64.signature_b64)
依据文档第 17、74 节。
"""
from __future__ import annotations

import base64
import json
import secrets
from typing import Any

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from app.core.config import settings
from app.core.errors import ErrorCode, LicenseError


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class CryptoService:
    """Ed25519 签名服务，单例持有私钥/公钥。"""

    def __init__(self) -> None:
        self._signing_key: SigningKey | None = None
        self._verify_key: VerifyKey | None = None
        self._public_key_b64: str = ""

    def init_from_settings(self) -> None:
        from app.core.config import settings as _s
        priv = _s.ed25519_private_key.strip()
        pub = _s.ed25519_public_key.strip()
        self.init_with_keys(priv, pub)

    def init_with_keys(self, priv: str, pub: str) -> None:
        if not priv or not pub:
            raise LicenseError(
                ErrorCode.SIGNING_ERROR,
                "Ed25519 keys not configured. Run scripts/generate_keys.py.",
            )
        self._signing_key = SigningKey(_b64url_decode(priv))
        self._verify_key = VerifyKey(_b64url_decode(pub))
        self._public_key_b64 = pub

    @property
    def public_key_b64(self) -> str:
        return self._public_key_b64

    def sign_payload(self, payload: dict[str, Any]) -> str:
        """对 payload 签名，返回 base64url(version.payload.signature)。"""
        if self._signing_key is None:
            raise LicenseError(ErrorCode.SIGNING_ERROR, "signing key not initialized")
        version = 1
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = self._signing_key.sign(payload_bytes).signature
        parts = [
            _b64url_encode(str(version).encode("ascii")),
            _b64url_encode(payload_bytes),
            _b64url_encode(signature),
        ]
        return _b64url_encode(".".join(parts).encode("ascii"))

    def verify_payload(self, authorization: str) -> dict[str, Any]:
        """验证客户端收到的 authorization 字符串，返回 payload dict。"""
        if self._verify_key is None:
            raise LicenseError(ErrorCode.SIGNING_ERROR, "verify key not initialized")
        try:
            raw = _b64url_decode(authorization).decode("ascii")
            version_b64, payload_b64, sig_b64 = raw.split(".")
            payload_bytes = _b64url_decode(payload_b64)
            signature = _b64url_decode(sig_b64)
            self._verify_key.verify(payload_bytes, signature)
            return json.loads(payload_bytes)
        except (ValueError, BadSignatureError, json.JSONDecodeError) as exc:
            raise LicenseError(ErrorCode.INVALID_SIGNATURE) from exc

    @staticmethod
    def generate_nonce(length: int = 32) -> str:
        return secrets.token_urlsafe(length)


crypto_service = CryptoService()
