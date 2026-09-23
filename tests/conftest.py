"""测试公共 fixture：临时 SQLite + 内存密钥 + TestClient。"""
from __future__ import annotations

import base64
import os
import sys
from collections.abc import Generator

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nacl.signing import SigningKey


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture(scope="session")
def ed25519_keys() -> tuple[str, str]:
    sk = SigningKey.generate()
    priv = _b64url(bytes(sk))
    pub = _b64url(bytes(sk.verify_key))
    return priv, pub


@pytest.fixture(scope="session", autouse=True)
def setup_env(ed25519_keys) -> Generator[None, None, None]:
    priv, pub = ed25519_keys
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_NAME"] = "test_license"
    os.environ["ED25519_PRIVATE_KEY"] = priv
    os.environ["ED25519_PUBLIC_KEY"] = pub
    os.environ["JWT_SECRET"] = "test_secret_for_jwt_signing_64chars_padding_xxxxxx"
    os.environ["ADMIN_DEFAULT_USERNAME"] = "admin"
    os.environ["ADMIN_DEFAULT_PASSWORD"] = "testpassword123"
    os.environ["REDIS_HOST"] = "127.0.0.1"
    os.environ["GEOIP_DB_PATH"] = ""

    from app.core.config import get_settings
    get_settings.cache_clear()
    import app.core.config as cfg_mod
    cfg_mod.settings = get_settings()
    from app.core.config import settings

    # 重建 engine / SessionLocal，因为它们在模块导入时已用旧配置创建
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.database.database as db_mod
    db_mod.engine = create_engine(settings.database_url, echo=False)
    db_mod.SessionLocal = sessionmaker(bind=db_mod.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    # 初始化 crypto_service
    from app.core.crypto import crypto_service
    crypto_service.init_with_keys(priv, pub)

    db_file = "test_license.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    # 建表 + 默认管理员
    from app.database.init_db import init_database
    init_database()

    yield

    # Windows 下需先释放引擎才能删除 db 文件
    try:
        import app.database.database as db_mod
        db_mod.engine.dispose()
    except Exception:
        pass
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except PermissionError:
            pass


@pytest.fixture(autouse=True)
def reset_db():
    """每个测试前清空表数据，保留 admin_users。"""
    from app.models import Base
    import app.database.database as db_mod
    from sqlalchemy import delete
    for table in reversed(Base.metadata.sorted_tables):
        if table.name == "admin_users":
            continue
        with db_mod.engine.connect() as conn:
            conn.execute(delete(table))
            conn.commit()
    yield


@pytest.fixture()
def db_session() -> Generator:
    import app.database.database as db_mod
    db = db_mod.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session) -> Generator:
    from fastapi.testclient import TestClient
    from app.main import app
    import app.database.database as db_mod

    app.dependency_overrides[db_mod.get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
