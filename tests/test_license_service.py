"""License 服务层单元测试。"""
from __future__ import annotations

import pytest

from app.core.errors import ErrorCode, LicenseError
from app.core.security import generate_api_key
from app.models import Product
from app.services import license_service


@pytest.fixture()
def sample_product(db_session):
    p = Product(
        product_id="testprod",
        product_name="Test Product",
        api_key=generate_api_key(),
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def test_batch_generate_and_verify(db_session, sample_product):
    licenses = license_service.batch_generate(
        db_session, product_id="testprod", count=3, duration=30, duration_unit="minute"
    )
    assert len(licenses) == 3
    for lic in licenses:
        assert lic.status == "UNUSED"
        assert lic.activated_at is None
        assert lic.expire_at is None

    # 首次验证激活
    first = licenses[0]
    result = license_service.verify_license(db_session, first.license_key, "testprod")
    assert result.status == "ACTIVE"
    assert result.activated_at is not None
    assert result.expire_at is not None


def test_verify_nonexistent_license(db_session, sample_product):
    with pytest.raises(LicenseError) as exc:
        license_service.verify_license(db_session, "nonexistent_key_12345678", "testprod")
    assert exc.value.code == ErrorCode.LICENSE_NOT_FOUND


def test_product_mismatch(db_session, sample_product):
    licenses = license_service.batch_generate(
        db_session, product_id="testprod", count=1, duration=10, duration_unit="minute"
    )
    with pytest.raises(LicenseError) as exc:
        license_service.verify_license(db_session, licenses[0].license_key, "other_product")
    assert exc.value.code == ErrorCode.INVALID_PRODUCT


def test_disable_enable_license(db_session, sample_product):
    licenses = license_service.batch_generate(
        db_session, product_id="testprod", count=1, duration=60, duration_unit="minute"
    )
    lic = licenses[0]
    license_service.activate_license(db_session, lic.license_key, "testprod")

    disabled = license_service.disable_license(db_session, lic.license_id)
    assert disabled.status == "DISABLED"

    with pytest.raises(LicenseError) as exc:
        license_service.verify_license(db_session, lic.license_key, "testprod")
    assert exc.value.code == ErrorCode.LICENSE_DISABLED

    enabled = license_service.enable_license(db_session, lic.license_id)
    assert enabled.status in ("ACTIVE", "UNUSED")


def test_extend_license(db_session, sample_product):
    licenses = license_service.batch_generate(
        db_session, product_id="testprod", count=1, duration=10, duration_unit="minute"
    )
    lic = licenses[0]
    license_service.activate_license(db_session, lic.license_key, "testprod")
    original_expire = lic.expire_at

    extended = license_service.extend_license(db_session, lic.license_id, 7, "day")
    assert extended.expire_at > original_expire
