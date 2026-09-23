#!/usr/bin/env python3
"""快速创建一个示例产品并生成测试卡密，用于本地验证。

用法:
    python scripts/create_demo_product.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import generate_api_key
from app.database.database import SessionLocal
from app.database.init_db import init_database
from app.models import License, Product
from app.services.license_service import batch_generate
from app.core.time_utils import utc_now


def main() -> None:
    init_database()
    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(product_id="mytool").first()
        if product is None:
            product = Product(
                product_id="mytool",
                product_name="MyTool",
                api_key=generate_api_key(),
                status="active",
                description="Demo product",
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            print(f"Created product: mytool, API Key: {product.api_key}")
        else:
            print(f"Product exists: mytool, API Key: {product.api_key}")

        licenses = batch_generate(
            db, product_id="mytool", count=5, duration=30, duration_unit="minute", remark="demo"
        )
        print(f"Generated {len(licenses)} license keys:")
        for lic in licenses:
            print(f"  {lic.license_key}  ({lic.license_id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
