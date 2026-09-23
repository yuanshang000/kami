#!/usr/bin/env python3
"""数据库初始化脚本：建表 + 默认管理员。

用法:
    python scripts/init_db.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.init_db import init_database


def main() -> None:
    print("Initializing database...")
    init_database()
    print("Done. Tables created, default admin ensured.")


if __name__ == "__main__":
    main()
