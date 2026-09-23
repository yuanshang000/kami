"""应用配置，从环境变量 / .env 加载。"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "License Server"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "info"

    # Database
    db_type: str = "postgresql"
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_user: str = "license"
    db_password: str = "change_me"
    db_name: str = "license_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Security
    ed25519_private_key: str = ""
    ed25519_public_key: str = ""
    jwt_secret: str = "change_me_to_random_64_chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Admin
    admin_default_username: str = "admin"
    admin_default_password: str = "change_me_immediately"

    # Rate limit
    rate_limit_per_ip: int = 60
    rate_limit_per_api_key: int = 300
    rate_limit_window_seconds: int = 60

    # Session
    session_expire_seconds: int = 86400
    session_heartbeat_grace_seconds: int = 300

    # License
    license_key_length: int = 32
    license_key_prefix: str = ""
    offline_grace_period: int = 0

    # GeoIP
    geoip_db_path: str = ""
    geoip_license_key: str = ""

    # CORS
    cors_origins: str = "*"

    # Request security
    request_max_timestamp_skew_seconds: int = 300
    nonce_ttl_seconds: int = 600

    @property
    def database_url(self) -> str:
        if self.db_type == "sqlite":
            return f"sqlite:///./{self.db_name}.db"
        if self.db_type == "mysql":
            return (
                f"mysql+pymysql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
            )
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
