# 卡密授权系统

通用 License / 卡密授权系统，包含管理后台、授权服务端 API，以及一套可复用的客户端 UI 模板。

---

## 项目结构

```
kami/
├── app/                    授权服务端（FastAPI）
│   ├── api/                接口层
│   │   ├── license.py      客户端接口：verify / activate / heartbeat / deactivate / info
│   │   ├── auth.py         管理后台认证：login / logout / session / refresh
│   │   ├── admin.py        卡密管理
│   │   ├── admin_extra.py  产品、会话、日志、仪表盘
│   │   └── deps.py         鉴权依赖（API Key / 管理员 JWT）
│   ├── core/               配置、加密、错误码、限流、Redis
│   ├── database/           数据库连接与初始化
│   ├── models/             ORM 模型
│   ├── schemas/            请求校验
│   ├── services/           业务逻辑
│   └── static/index.html   管理后台前端（单文件）
│
├── client/                 客户端
│   ├── template/           ★ 统一客户端 UI 模板（接入新应用看这里）
│   ├── index.html          简易测试客户端
│   ├── main.py             命令行测试客户端
│   └── config.json         本地配置（含 API Key，不应提交）
│
├── scripts/                运维脚本
│   ├── generate_keys.py    生成 Ed25519 密钥对
│   ├── init_db.py          初始化数据库
│   ├── create_demo_product.py  创建演示产品
│   └── setup_client_demo.py    创建客户端演示数据
│
├── tests/                  pytest 测试
├── docs/                   接口文档与客户端接入说明
└── 开发文档.md              完整开发文档
```

---

## 快速开始

### 1. 环境准备

```bash
pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

生成 Ed25519 密钥对（填入 `.env`）：

```bash
python scripts/generate_keys.py
```

### 2. 初始化数据库

```bash
python scripts/init_db.py
```

### 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

管理后台：http://127.0.0.1:8000

默认账号取自 `.env` 中的 `ADMIN_DEFAULT_USERNAME` / `ADMIN_DEFAULT_PASSWORD`。

### 4. 接入自己的应用

**统一客户端 UI 模板** → [`client/template/README.md`](client/template/README.md)

里面包含：界面截图、功能清单、完整接口文档、配置项详解、接入流程图。

---

## 开发新应用接入卡密

如果要给新产品接入授权系统，直接参考 [统一客户端 UI 模板](client/template/README.md)。四步即可：

1. 在管理后台「产品管理」创建产品，拿到 `product_id` 和 `api_key`
2. 复制 `client/template/` 三个文件到你的客户端工程
3. 改 `client-core.js` 顶部的 `CONFIG`（产品名、服务器、密钥、获取卡密方式、界面文案）
4. 引入 CSS 和 JS，完成

只想参考界面不要验证逻辑的话，保留 `index.html` 和 `client-theme.css`，把 `verifyLicense()` 换成你自己的请求即可。

本地预览：

```bash
cd client/template
python -m http.server 8080
```

---

## 演示数据

快速造一套测试数据（含普通卡密、顶号场景、短时卡密）：

```bash
python scripts/setup_client_demo.py
```

---

## 测试

```bash
python -m pytest -q
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 服务端 | FastAPI + SQLAlchemy 2.0 + Pydantic Settings |
| 数据库 | MySQL / PostgreSQL / SQLite |
| 缓存 | Redis（限流，可降级） |
| 签名 | Ed25519（授权数据防篡改） |
| 鉴权 | API Key（客户端）+ JWT（管理后台） |
| 前端 | 原生 HTML/CSS/JS，无构建步骤 |

---

## 安全说明

- `.env`、数据库文件、`client/config.json` 均已在 `.gitignore` 中排除，切勿提交
- 客户端内的 API Key 只能请求授权接口，无法访问管理后台
- 若需更强保护，让客户端请求自己的后端，由后端代理转发授权请求

---

## 文档

- [统一客户端 UI 模板](client/template/README.md) — 客户端接入必读
- [接口文档](docs/api.md)
- [客户端接入说明](docs/client-integration.md)
- [开发文档](开发文档.md)
- [宝塔面板部署](宝塔面板安装.txt)