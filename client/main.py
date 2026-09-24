"""卡密授权系统 - 简单测试客户端。

用法:
    python client/main.py

首次运行会引导配置服务器地址和 API Key，之后通过交互菜单测试各项功能。
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path

import requests

CONFIG_FILE = Path(__file__).parent / "config.json"


def get_machine_id() -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, platform.node()))


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")


def print_sep(title: str = ""):
    print("\n" + "=" * 50)
    if title:
        print(f"  {title}")
        print("=" * 50)


def print_resp(resp: requests.Response):
    try:
        data = resp.json()
    except Exception:
        print(f"  [HTTP {resp.status_code}] {resp.text[:200]}")
        return
    success = data.get("success", False)
    code = data.get("code", -1)
    msg = data.get("message", "")
    print(f"  HTTP {resp.status_code} | code={code} | {msg}")
    if not success:
        err = data.get("error", {})
        if err:
            print(f"  错误类型: {err.get('type', '?')}")
        return
    d = data.get("data", {})
    if d:
        for k, v in d.items():
            if k == "authorization":
                print(f"  {k}: <签名数据>")
            else:
                print(f"  {k}: {v}")


class LicenseClient:
    def __init__(self, server_url: str, api_key: str, product_id: str = ""):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.product_id = product_id
        self.machine_id = get_machine_id()
        self.client_version = "1.0.0"
        self.session_id = None
        self.session_token = None
        self.license_key = None

    @property
    def headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Client-Version": self.client_version,
        }
        if self.product_id:
            h["X-Product-ID"] = self.product_id
        return h

    def _url(self, path: str) -> str:
        return f"{self.server_url}/api/v1/license/{path}"

    def verify(self, license_key: str, force: bool = False) -> bool:
        body = {"license_key": license_key, "machine_id": self.machine_id, "client_version": self.client_version, "force": force}
        resp = requests.post(self._url("verify"), headers=self.headers, json=body, timeout=10)
        print_resp(resp)
        if resp.ok and resp.json().get("success"):
            d = resp.json()["data"]
            self.session_id = d.get("session_id")
            self.session_token = d.get("session_token")
            self.license_key = license_key
            return True
        if not force and resp.ok:
            data = resp.json()
            if data.get("code") == 4001 and "顶替" in data.get("message", ""):
                choice = input("\n  该卡密已在其他设备使用，是否顶号？(y/N): ").strip().lower()
                if choice == "y":
                    return self.verify(license_key, force=True)
        return False

    def activate(self, license_key: str) -> bool:
        body = {"license_key": license_key, "machine_id": self.machine_id, "client_version": self.client_version}
        resp = requests.post(self._url("activate"), headers=self.headers, json=body, timeout=10)
        print_resp(resp)
        if resp.ok and resp.json().get("success"):
            d = resp.json()["data"]
            self.session_id = d.get("session_id")
            self.session_token = d.get("session_token")
            self.license_key = license_key
            return True
        return False

    def heartbeat(self) -> bool:
        if not self.session_id:
            print("  [!] 没有活跃会话，请先验证/激活卡密")
            return False
        body = {
            "session_id": self.session_id,
            "session_token": self.session_token,
            "machine_id": self.machine_id,
            "client_version": self.client_version,
        }
        resp = requests.post(self._url("heartbeat"), headers=self.headers, json=body, timeout=10)
        print_resp(resp)
        return resp.ok and resp.json().get("success", False)

    def deactivate(self) -> bool:
        if not self.session_id:
            print("  [!] 没有活跃会话")
            return False
        body = {"session_id": self.session_id, "session_token": self.session_token}
        resp = requests.post(self._url("deactivate"), headers=self.headers, json=body, timeout=10)
        print_resp(resp)
        if resp.ok and resp.json().get("success"):
            self.session_id = None
            self.session_token = None
            return True
        return False

    def info(self) -> bool:
        if not self.session_id:
            print("  [!] 没有活跃会话，请先验证/激活卡密")
            return False
        params = {"session_id": self.session_id, "session_token": self.session_token or ""}
        resp = requests.get(self._url("info"), headers=self.headers, params=params, timeout=10)
        print_resp(resp)
        return resp.ok and resp.json().get("success", False)

    def heartbeat_loop(self, interval: int = 30):
        print(f"  开始心跳循环，间隔 {interval} 秒，Ctrl+C 停止...")
        try:
            while True:
                ok = self.heartbeat()
                if not ok:
                    print("  心跳失败，停止循环")
                    break
                print(f"  下次心跳: {interval} 秒后")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  心跳循环已停止")


def setup_config() -> dict:
    print_sep("初始配置")
    cfg = load_config()
    server = input(f"  服务器地址 [{cfg.get('server_url', 'http://localhost:8000')}]: ").strip()
    if server:
        cfg["server_url"] = server
    cfg.setdefault("server_url", "http://localhost:8000")

    api_key = input(f"  API Key [{cfg.get('api_key', '')}]: ").strip()
    if api_key:
        cfg["api_key"] = api_key
    if not cfg.get("api_key"):
        print("  [!] API Key 不能为空")
        sys.exit(1)

    product_id = input(f"  产品ID (可选) [{cfg.get('product_id', '')}]: ").strip()
    if product_id:
        cfg["product_id"] = product_id

    save_config(cfg)
    print(f"  配置已保存到 {CONFIG_FILE}")
    return cfg


def main():
    print_sep("卡密授权系统 - 测试客户端")

    cfg = load_config()
    if not cfg.get("api_key"):
        cfg = setup_config()
    else:
        print(f"  服务器: {cfg.get('server_url', 'http://localhost:8000')}")
        print(f"  API Key: {cfg.get('api_key', '')[:20]}...")
        print(f"  产品ID:  {cfg.get('product_id', '(未设置)')}")
        reconfig = input("\n  重新配置? (y/N): ").strip().lower()
        if reconfig == "y":
            cfg = setup_config()

    client = LicenseClient(
        server_url=cfg.get("server_url", "http://localhost:8000"),
        api_key=cfg["api_key"],
        product_id=cfg.get("product_id", ""),
    )

    while True:
        print_sep("功能菜单")
        print(f"  机器ID:   {client.machine_id[:20]}...")
        print(f"  当前会话: {client.session_id or '无'}")
        print()
        print("  [1] 验证卡密 (verify)")
        print("  [2] 激活卡密 (activate)")
        print("  [3] 发送心跳 (heartbeat)")
        print("  [4] 查询信息 (info)")
        print("  [5] 注销会话 (deactivate)")
        print("  [6] 心跳循环 (持续发送)")
        print("  [7] 重新配置")
        print("  [0] 退出")

        choice = input("\n  请选择: ").strip()

        if choice == "1":
            key = input("  输入卡密: ").strip()
            if key:
                print_sep("验证卡密")
                client.verify(key)
        elif choice == "2":
            key = input("  输入卡密: ").strip()
            if key:
                print_sep("激活卡密")
                client.activate(key)
        elif choice == "3":
            print_sep("发送心跳")
            client.heartbeat()
        elif choice == "4":
            print_sep("查询信息")
            client.info()
        elif choice == "5":
            print_sep("注销会话")
            client.deactivate()
        elif choice == "6":
            interval = input("  心跳间隔秒数 [30]: ").strip()
            interval = int(interval) if interval else 30
            print_sep("心跳循环")
            client.heartbeat_loop(interval)
        elif choice == "7":
            cfg = setup_config()
            client = LicenseClient(
                server_url=cfg.get("server_url", "http://localhost:8000"),
                api_key=cfg["api_key"],
                product_id=cfg.get("product_id", ""),
            )
        elif choice == "0":
            print("  再见!")
            break
        else:
            print("  无效选择")

        if choice not in ("6", "0", "7"):
            input("\n  按回车继续...")


if __name__ == "__main__":
    main()
