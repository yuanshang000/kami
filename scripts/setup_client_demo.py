#!/usr/bin/env python3
"""为统一客户端模板创建演示产品与测试卡密。

用法:
    python scripts/setup_client_demo.py

会在当前数据库中创建产品 nova_studio，并生成若干测试卡密，
其中包含一张已绑定其他机器的卡密用于演示「顶号」流程。
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

PRODUCT_ID = "nova_studio"


def main() -> None:
    init_database()
    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(product_id=PRODUCT_ID).first()
        if product is None:
            product = Product(
                product_id=PRODUCT_ID,
                product_name="Nova Studio",
                api_key=generate_api_key(),
                status="active",
                description="统一客户端 UI 演示产品",
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            print(f"[产品已创建] {product.product_id}")
        else:
            print(f"[产品已存在] {product.product_id}")

        print(f"\n{'=' * 60}")
        print(f"  API Key : {product.api_key}")
        print(f"{'=' * 60}\n")

        # 演示用卡密：一张可用，一张已被其他机器绑定（触发顶号），一张短有效期
        licenses = batch_generate(
            db, product_id=PRODUCT_ID, count=3,
            duration=30, duration_unit="day", remark="client-ui-demo",
        )
        if licenses:
            print("\n[可用卡密] 30 天有效期")
            for lic in licenses[:2]:
                print(f"  {lic.license_key}   ({lic.license_id})")

        # 第二张卡密模拟「已被其他机器使用」，用于演示顶号确认弹窗。
        # 机器码存在 session 表上，licenses.bind_machine 只是「是否绑定」的布尔开关。
        if len(licenses) >= 2:
            from datetime import timedelta

            from app.core.security import generate_session_id, generate_session_token, hash_token
            from app.core.time_utils import ensure_aware, utc_now
            from app.models import Session as SessionModel

            bound = licenses[1]
            now = utc_now()
            bound.status = "ACTIVE"
            bound.bind_machine = True
            bound.activated_at = now
            bound.expire_at = ensure_aware(now + timedelta(days=30))
            db.commit()

            token = generate_session_token()
            db.add(SessionModel(
                session_id=generate_session_id(),
                license_id=bound.license_id,
                product_id=PRODUCT_ID,
                session_token_hash=hash_token(token),
                machine_id="M-OTHERDEVICE9999",
                client_version="1.0.0",
                ip="127.0.0.1",
                created_at=now,
                last_seen_at=now,
                expire_at=ensure_aware(now + timedelta(days=30)),
                status="active",
            ))
            db.commit()
            print("\n[已占用卡密] 模拟其他机器在用，验证时会弹出顶号确认")
            print(f"  {bound.license_key}   (绑定于 M-OTHERDEVICE9999)")

        # 一张极短有效期卡密，方便观察倒计时归零后的自动跳转
        short = batch_generate(
            db, product_id=PRODUCT_ID, count=1,
            duration=2, duration_unit="minute", remark="client-ui-short",
        )
        if short:
            print(f"\n[短时卡密] 2 分钟有效期，用于观察倒计时到期行为")
            print(f"  {short[0].license_key}   ({short[0].license_id})")

        print("\n请把上面的 API Key 填入 client/template/client-core.js 的 CONFIG.server.apiKey")
    finally:
        db.close()


if __name__ == "__main__":
    main()