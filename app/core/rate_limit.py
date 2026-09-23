"""基于 Redis 的滑动窗口限流。"""
from __future__ import annotations

import time
from typing import Optional

import redis

from app.core.config import settings
from app.core.errors import ErrorCode, LicenseError


class RateLimiter:
    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    def init(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def check(
        self,
        key: str,
        limit: int,
        window: int | None = None,
        retry_after: Optional[int] = None,
    ) -> None:
        if self._redis is None:
            return
        window = window or settings.rate_limit_window_seconds
        now = int(time.time())
        pipe = self._redis.pipeline()
        member = f"{now}:{secrets_module()}"
        zkey = f"rl:{key}"
        pipe.zremrangebyscore(zkey, 0, now - window)
        pipe.zcard(zkey)
        pipe.zadd(zkey, {member: now})
        pipe.expire(zkey, window + 1)
        _, count, _, _ = pipe.execute()
        if count >= limit:
            raise LicenseError(
                ErrorCode.RATE_LIMITED,
                retry_after=retry_after or window,
            )

    def check_ip(self, ip: str) -> None:
        self.check(f"ip:{ip}", settings.rate_limit_per_ip)

    def check_api_key(self, api_key: str) -> None:
        self.check(f"ak:{api_key}", settings.rate_limit_per_api_key)


def secrets_module() -> str:
    import secrets as _s
    return _s.token_hex(8)


rate_limiter = RateLimiter()
