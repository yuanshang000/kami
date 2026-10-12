# 卡密授权系统

一套完整的软件授权（License）解决方案。核心能力是**卡密管理与授权校验**，配套提供统一客户端 UI 模板，让接入方不必为每个产品重复设计授权界面。

---

## 这是什么

| 部分 | 定位 | 说明 |
|---|---|---|
| **卡密系统** | 主体 | 生成卡密、校验授权、维护会话、记录日志。管理后台可视化操作 |
| **客户端 UI 模板** | 配套工具 | 一套开箱即用的授权界面。接入方复制即用，改配置即可换成自己的品牌 |

两者是「系统 + 配件」的关系：卡密系统独立运行，不依赖客户端模板；客户端模板是给接入方用的现成界面，用不用随你。

---

## 核心能力

### 卡密管理

- 批量生成卡密，支持分钟/小时/天三种有效期单位
- 单机绑定可选：开启后一张卡密只能在一台机器上使用，新机器验证会触发顶号确认
- 卡密可续期、禁用、启用、删除
- 按产品、状态、关键词、时间范围筛选查询

### 授权校验

- **verify** — 校验卡密并建立会话，接入方的主要入口
- **activate** — 激活流程
- **heartbeat** — 会话保活，防止授权被滥用
- **deactivate** — 用户主动退出，解绑当前机器
- **info** — 查询授权状态

### 安全机制

- **Ed25519 签名** — 授权数据签名下发，客户端可校验防篡改
- **API Key 鉴权** — 客户端凭密钥请求，无法越权
- **JWT 会话** — 管理后台登录态，过期自动跳转重新登录
- **设备绑定** — 机器码识别，顶号机制防止一卡多机
- **请求限流** — 按 IP 和 API Key 双维度（依赖 Redis，不可用时自动降级）
- **完整审计** — 每次验证、激活、心跳、注销都留日志，含 IP、机器码、错误码

### 会话管理

会话有独立生命周期（默认 24 小时），支持查看活跃会话、强制撤销。支持心跳续期。

---

## 项目结构

```
kami/
├── app/                    授权服务端（FastAPI）
│   ├── api/
│   │   ├── license.py      客户端接口：verify / activate / heartbeat / deactivate / info
│   │   ├── auth.py         后台认证：login / logout / session / refresh
│   │   ├── admin.py        卡密管理接口
│   │   └── admin_extra.py  产品、会话、日志、仪表盘
│   ├── core/               配置、加密、错误码、限流、Redis
│   ├── database/           连接与建表
│   ├── models/             ORM 模型
│   ├── services/           业务逻辑（卡密、会话、日志、地理）
│   └── static/index.html   管理后台前端（单文件）
│
├── client/
│   ├── template/           ★ 客户端 UI 模板（接入应用时用这个）
│   ├── index.html          简易测试客户端（网页）
│   ├── main.py             命令行测试客户端
│   └── config.json         本地配置（含 API Key，不应提交）
│
├── scripts/
│   ├── generate_keys.py           生成 Ed25519 密钥对
│   ├── init_db.py                 初始化数据库
│   ├── create_demo_product.py     创建演示产品
│   └── setup_client_demo.py       生成客户端演示数据
│
├── tests/                  pytest 测试
├── docs/                   接口文档与接入说明
├── 开发文档.md              完整开发文档
└── 宝塔面板安装.txt          宝塔面板部署步骤
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

```bash
cp .env.example .env
```

生成签名密钥对，填入 `.env`：

```bash
python scripts/generate_keys.py
```

`.env` 关键配置项：

| 配置项 | 说明 |
|---|---|
| `DB_TYPE` / `DB_HOST` / `DB_NAME` 等 | 数据库连接（支持 MySQL / PostgreSQL / SQLite） |
| `JWT_SECRET` | 后台登录令牌密钥，**务必改成随机长字符串** |
| `ED25519_PRIVATE_KEY` / `ED25519_PUBLIC_KEY` | 签名密钥对，`generate_keys.py` 生成 |
| `ADMIN_DEFAULT_USERNAME` / `ADMIN_DEFAULT_PASSWORD` | 首次启动创建的后台账号 |
| `SESSION_EXPIRE_SECONDS` | 客户端会话有效期，默认 86400（24 小时） |
| `REDIS_HOST` / `REDIS_PORT` | 限流依赖，不可用时自动降级为不限流 |

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

### 4. 启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开管理后台：http://127.0.0.1:8000

用 `.env` 里配置的账号登录。

### 5. 创建产品

进入「产品管理」新建产品，记下：

- **product_id** — 产品标识，接入方要填
- **api_key** — 产品密钥，接入方要填

再进入「卡密管理」批量生成卡密，就可以分发出去了。

---

## 接入方怎么用

接入方（你的应用开发者）拿到 `product_id` 和 `api_key` 后，有两种用法：

### 方式一：用现成的客户端 UI 模板（推荐）

复制 `client/template/` 整个目录到你的应用工程，改配置就能用。

包含完整的验证页、授权状态页、日志面板、日夜主题，UI 不用自己画。

**详细文档：[client/template/README.md](client/template/README.md)**

### 方式二：只调接口，界面自己写

直接调 `POST /api/v1/license/verify` 等接口，返回 JSON，界面完全由接入方决定。

**接口文档：[docs/api.md](docs/api.md)**

最小示例：

```js
const resp = await fetch(SERVER + '/api/v1/license/verify', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + API_KEY,
    'X-Product-ID': PRODUCT_ID,
  },
  body: JSON.stringify({
    license_key: 用户输入的卡密,
    machine_id: 获取机器码(),
    client_version: '1.0.0',
  }),
});
const data = await resp.json();
if (data.success) {
  // 授权成功，data.session_id / data.session_token 用于后续心跳
} else {
  // 失败，data.code 是错误码，data.message 是可展示给用户的文案
}
```

---

## 客户端 UI 模板说明

位置：`client/template/`

它解决什么问题：每个产品接入授权时都要做验证界面，如果每次都重新设计，UI 就不统一、还容易漏掉顶号确认、退出授权、日志排查这些必要功能。这套模板把这些做成了标准件。

三个文件：

| 文件 | 作用 |
|---|---|
| `index.html` | 页面结构（验证页 + 授权页 + 两个弹窗） |
| `client-theme.css` | 设计系统，两套主题的设计令牌 |
| `client-core.js` | 全部逻辑：接口调用、会话、心跳、日志、交互 |

接入方只改 `client-core.js` 顶部的 `CONFIG`，不碰其他代码。里面能配的包括：产品名、Logo、服务器地址、API Key、获取卡密的联系方式、所有界面文案、心跳间隔、日志开关、主题锁定策略。

已实现的功能：卡密验证、成功失败提示、获取卡密（跳转链接或联系方式点击复制）、单机授权顶号提示与确认、授权到期倒计时与进度条、退出授权二次确认、关闭程序二次确认、运行日志与诊断导出、日夜主题切换、记住卡密自动验证。

本地预览：

```bash
cd client/template
python -m http.server 8080
```

生成演示数据（含普通卡密、顶号场景、短时卡密）：

```bash
python scripts/setup_client_demo.py
```

---

## 测试

```bash
python -m pytest -q
```

---

## 部署

Docker：

```bash
docker-compose up -d
```

宝塔面板部署步骤见 [宝塔面板安装.txt](宝塔面板安装.txt)。

生产环境务必修改 `.env` 中的 `JWT_SECRET` 和 `ADMIN_DEFAULT_PASSWORD`，并确保 Redis 可用（否则限流失效）。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 服务端 | FastAPI + SQLAlchemy 2.0 + Pydantic Settings |
| 数据库 | MySQL / PostgreSQL / SQLite |
| 缓存 | Redis（限流，可降级） |
| 签名 | Ed25519 |
| 鉴权 | API Key（客户端）+ JWT（管理后台） |
| 前端 | 原生 HTML/CSS/JS，无构建步骤 |

---

## 安全须知

- `.env`、数据库文件、`client/config.json` 均已在 `.gitignore` 中排除
- API Key 只能请求授权接口，**无法访问管理后台**。但客户端里的 Key 任何人都能看到，需更强保护时应由接入方后端代理转发
- `session_token` 只返回一次，服务端仅存哈希，丢失只能重新验证

---

## 文档

- [客户端 UI 模板文档](client/template/README.md) — 接入方看这份
- [接口文档](docs/api.md)
- [客户端接入说明](docs/client-integration.md)
- [开发文档](开发文档.md) — 系统设计、数据库结构、错误码等完整细节