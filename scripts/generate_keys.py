#!/usr/bin/env python3
"""生成 Ed25519 密钥对并输出 .env 配置行。

用法:
    python scripts/generate_keys.py
    python scripts/generate_keys.py --write   # 直接写入 .env
"""
from __future__ import annotations

import argparse
import base64
import os
import sys

from nacl.signing import SigningKey


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Ed25519 key pair for License Server")
    parser.add_argument("--write", action="store_true", help="Write keys into .env file")
    args = parser.parse_args()

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    priv_b64 = b64url(bytes(signing_key))
    pub_b64 = b64url(bytes(verify_key))

    print("=" * 60)
    print("Ed25519 Private Key (server only, NEVER expose to client):")
    print(f"  ED25519_PRIVATE_KEY={priv_b64}")
    print()
    print("Ed25519 Public Key (embed in client SDK):")
    print(f"  ED25519_PUBLIC_KEY={pub_b64}")
    print("=" * 60)

    if args.write:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        lines: list[str] = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("ED25519_PRIVATE_KEY=") or line.startswith("ED25519_PUBLIC_KEY="):
                        continue
                    lines.append(line)
        else:
            with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.example"), "r", encoding="utf-8") as f:
                lines = f.readlines()
        lines.append(f"ED25519_PRIVATE_KEY={priv_b64}\n")
        lines.append(f"ED25519_PUBLIC_KEY={pub_b64}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"\nKeys written to {env_path}")


if __name__ == "__main__":
    main()
