"""IP 提取与可信代理头处理。"""
from __future__ import annotations

from fastapi import Request

# 可信代理数量：取 X-Forwarded-For 最右侧第 N 个 IP
TRUSTED_PROXIES = 1


def get_client_ip(request: Request) -> str:
    """从请求中提取真实客户端 IP，考虑反向代理。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            idx = max(0, len(parts) - TRUSTED_PROXIES)
            return parts[idx]
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"
