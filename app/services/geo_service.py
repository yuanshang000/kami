"""GeoIP 查询服务。无 mmdb 时返回空。"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings

try:
    import maxminddb
except ImportError:
    maxminddb = None


class GeoService:
    def __init__(self) -> None:
        self._reader = None

    def init(self) -> None:
        if not settings.geoip_db_path or maxminddb is None:
            return
        try:
            self._reader = maxminddb.open_database(settings.geoip_db_path)
        except Exception:
            self._reader = None

    def lookup(self, ip: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if self._reader is None or not ip:
            return None, None, None
        try:
            record = self._reader.get(ip)
            if not record:
                return None, None, None
            country = record.get("country", {}).get("names", {}).get("en")
            subdiv = record.get("subdivisions", [])
            region = subdiv[0].get("names", {}).get("en") if subdiv else None
            city = record.get("city", {}).get("names", {}).get("en")
            return country, region, city
        except Exception:
            return None, None, None

    def close(self) -> None:
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None


geo_service = GeoService()
