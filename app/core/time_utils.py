"""时间工具：统一 UTC。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime | None) -> datetime | None:
    """将 naive datetime 视为 UTC 并附加 tzinfo（SQLite 不保留时区）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def utc_now_ts() -> int:
    return int(utc_now().timestamp())


BEIJING_TZ = timezone(timedelta(hours=8))


def to_iso8601(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def from_iso8601(s: str) -> datetime:
    if s.endswith("+08:00"):
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S+08:00").replace(tzinfo=BEIJING_TZ)
        return dt.astimezone(timezone.utc)
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


DURATION_UNITS = {"minute", "hour", "day"}


def compute_expiry(activated_at: datetime, duration: int, unit: str) -> datetime:
    if unit == "minute":
        return activated_at + timedelta(minutes=duration)
    if unit == "hour":
        return activated_at + timedelta(hours=duration)
    if unit == "day":
        return activated_at + timedelta(days=duration)
    raise ValueError(f"unknown duration unit: {unit}")


def extend_expiry(current_expire: datetime, duration: int, unit: str) -> datetime:
    return compute_expiry(current_expire, duration, unit)
