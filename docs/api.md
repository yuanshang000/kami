# License Server API 文档 V1

**Base URL:** `https://license.example.com/api/v1`

**协议:** HTTPS + JSON (UTF-8)

**字段命名:** snake_case

---

## 1. 请求 Header 规范

所有客户端授权 API 请求需携带：

```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer {API_KEY}
X-Request-ID: {UUID v4}
X-Client-Version: {客户端版本}
X-Product-ID: {产品 ID}
```

管理后台 API 使用：

```http
Authorization: Bearer {ADMIN_JWT_TOKEN}
```

---

## 2. 统一响应结构

### 成功

```json
{
  "success": true,
  "code": 0,
  "message": "success",
  "request_id": "uuid",
  "data": { ... }
}
```

### 失败

```json
{
  "success": false,
  "code": 4003,
  "message": "license expired",
  "request_id": "uuid",
  "data": null,
  "error": {
    "type": "license_error",
    "field": null,
    "details": null,
    "retryable": false,
    "retry_after": null,
    "docs_url": null
  }
}
```

---

## 3. 错误码表

| Code | 名称 | HTTP | 说明 |
|---:|---|---:|---|
| 0 | SUCCESS | 200 | 成功 |
| 4001 | INVALID_LICENSE | 400 | 卡密格式错误 |
| 4002 | LICENSE_NOT_FOUND | 404 | 卡密不存在 |
| 4003 | LICENSE_EXPIRED | 200 | 卡密已过期 |
| 4004 | LICENSE_DISABLED | 200 | 卡密已禁用 |
| 4005 | INVALID_PRODUCT | 400 | 产品不存在或不匹配 |
| 4006 | INVALID_API_KEY | 401 | API Key 无效 |
| 4007 | INVALID_REQUEST | 422 | 请求参数错误 |
| 4008 | INVALID_SIGNATURE | 401 | 签名验证失败 |
| 4009 | INVALID_SESSION | 401 | Session 无效 |
| 4010 | SESSION_EXPIRED | 401 | Session 已过期 |
| 4011 | REQUEST_EXPIRED | 400 | 请求已过期 |
| 4012 | NONCE_REPLAYED | 409 | Nonce 重复 |
| 4013 | RATE_LIMITED | 429 | 请求过于频繁 |
| 4014 | CLIENT_VERSION_UNSUPPORTED | 400 | 客户端版本不支持 |
| 4015 | PRODUCT_DISABLED | 403 | 产品已禁用 |
| 5001 | INTERNAL_ERROR | 500 | 服务器内部错误 |
| 5002 | DATABASE_ERROR | 500 | 数据库错误 |
| 5003 | SIGNING_ERROR | 500 | 签名生成失败 |
| 5004 | GEOIP_ERROR | 500 | 地理位置查询失败 |

---

## 4. 授权签名机制

服务器使用 **Ed25519** 对授权 Payload 签名。

### Authorization 字段格式

`data.authorization` 是 Base64URL 编码的字符串，解码后为：

```
version.payload.signature
```

- `version`: 协议版本号（Base64URL 编码的 ASCII 数字）
- `payload`: 授权数据 JSON（Base64URL 编码）
- `signature`: Ed25519 签名（Base64URL 编码）

### Payload 字段

```json
{
  "version": 1,
  "status": "authorized",
  "license_id": "L-xxxxxx",
  "product_id": "mytool",
  "issued_at": 1790134215,
  "expire_at": 1790136015,
  "server_time": 1790134215,
  "session_id": "sess_xxxxxx",
  "nonce": "xxxxxx"
}
```

客户端必须使用内置的 **Ed25519 Public Key** 验证签名，验证失败则拒绝授权。

---

## 5. 客户端 API

### 5.1 POST /license/verify

卡密验证。首次验证时自动激活。

**Request Body:**
```json
{
  "license_key": "Qm7xK9pL2vN8sD4fR1tY6wA3",
  "machine_id": "7f8c2a...",
  "client_version": "1.0.0"
}
```

**成功响应:**
```json
{
  "success": true,
  "code": 0,
  "message": "success",
  "request_id": "uuid",
  "data": {
    "authorization": "eyJ2ZXJzaW9uIjox...",
    "session_id": "sess_xxxxxx",
    "session_token": "xxxxxx",
    "expire_at": "2026-09-23T04:02:15Z",
    "server_time": "2026-09-23T03:32:15Z"
  }
}
```

### 5.2 POST /license/activate

显式激活卡密（与 verify 类似，仅激活不创建 session 上下文重复）。

**Request Body:** 同 verify

### 5.3 POST /license/heartbeat

心跳重新验证。

**Request Body:**
```json
{
  "session_id": "sess_xxxxxx",
  "session_token": "xxxxxx",
  "machine_id": "7f8c2a...",
  "client_version": "1.0.0"
}
```

### 5.4 POST /license/deactivate

结束当前 session。

**Request Body:**
```json
{
  "session_id": "sess_xxxxxx",
  "session_token": "xxxxxx"
}
```

### 5.5 GET /license/info

获取当前授权信息。

**Query:** `?session_id=sess_xxxxxx&session_token=xxxxxx`

---

## 6. 管理后台 API

### 6.1 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /admin/auth/login | 管理员登录 |
| POST | /admin/auth/logout | 登出 |
| POST | /admin/auth/change-password | 修改密码 |

### 6.2 卡密管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /admin/licenses | 卡密列表（支持筛选分页） |
| POST | /admin/licenses/batch-generate | 批量生成 |
| POST | /admin/licenses/batch-enable | 批量启用 |
| POST | /admin/licenses/batch-disable | 批量禁用 |
| POST | /admin/licenses/batch-extend | 批量延期 |
| POST | /admin/licenses/export | 导出（txt/csv） |
| GET | /admin/licenses/{id} | 卡密详情 |
| PATCH | /admin/licenses/{id} | 修改卡密 |
| DELETE | /admin/licenses/{id} | 删除卡密 |
| POST | /admin/licenses/{id}/extend | 延期 |
| POST | /admin/licenses/{id}/disable | 禁用 |
| POST | /admin/licenses/{id}/enable | 启用 |
| GET | /admin/licenses/{id}/logs | 使用记录 |

### 6.3 产品管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /admin/products | 产品列表 |
| POST | /admin/products | 创建产品 |
| GET | /admin/products/{id} | 产品详情 |
| PATCH | /admin/products/{id} | 修改产品 |
| POST | /admin/products/{id}/regenerate-key | 重新生成 API Key |

### 6.4 其他

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /admin/sessions | Session 列表 |
| GET | /admin/logs | 使用日志 |
| GET | /admin/admin-logs | 管理员操作日志 |
| GET | /admin/dashboard | 仪表盘统计 |

---

## 7. 批量生成请求示例

```json
{
  "product_id": "mytool",
  "count": 100,
  "duration": 30,
  "duration_unit": "minute",
  "remark": "batch-2026-09"
}
```

---

## 8. Python 接入示例

```python
import base64
import json
import uuid
import requests
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

SERVER_URL = "https://license.example.com/api/v1"
API_KEY = "app_xxxxxxxxxxxxxxxx"
PRODUCT_ID = "mytool"
PUBLIC_KEY_B64 = "Ed25519_Public_Key_Base64URL"  # 从服务器管理员获取

def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def verify_authorization(authorization: str) -> dict:
    raw = b64url_decode(authorization).decode("ascii")
    version_b64, payload_b64, sig_b64 = raw.split(".")
    payload_bytes = b64url_decode(payload_b64)
    signature = b64url_decode(sig_b64)
    verify_key = VerifyKey(b64url_decode(PUBLIC_KEY_B64))
    verify_key.verify(payload_bytes, signature)  # raises BadSignatureError if invalid
    return json.loads(payload_bytes)

def verify_license(license_key: str, machine_id: str) -> dict:
    resp = requests.post(
        f"{SERVER_URL}/license/verify",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "X-Request-ID": str(uuid.uuid4()),
            "X-Client-Version": "1.0.0",
            "X-Product-ID": PRODUCT_ID,
        },
        json={
            "license_key": license_key,
            "machine_id": machine_id,
            "client_version": "1.0.0",
        },
        timeout=10,
    )
    data = resp.json()
    if not data["success"]:
        raise RuntimeError(f"License error {data['code']}: {data['message']}")
    payload = verify_authorization(data["data"]["authorization"])
    if payload["status"] != "authorized":
        raise RuntimeError("not authorized")
    if payload["product_id"] != PRODUCT_ID:
        raise RuntimeError("product mismatch")
    return payload

# 使用
payload = verify_license("Qm7xK9pL2vN8sD4fR1tY6wA3", "machine-abc")
print("Authorized until:", payload["expire_at"])
```

---

## 9. C++ 接入示例

```cpp
#include <cpprest/http_client.h>
#include <nlohmann/json.hpp>
// 需链接 libsodium 用于 Ed25519 验签

using namespace web;
using namespace web::http;
using namespace web::http::client;
using json = nlohmann::json;

struct LicenseResult {
    bool authorized;
    std::string sessionId;
    long long expireAt;
};

LicenseResult verifyLicense(const std::string& licenseKey,
                            const std::string& machineId) {
    http_client client(U("https://license.example.com/api/v1"));
    http_request req(methods::POST);
    req.set_request_uri("/license/verify");
    req.headers().add("Authorization", "Bearer app_xxxxxxxxxxxxxxxx");
    req.headers().add("X-Product-ID", "mytool");
    req.headers().add("X-Client-Version", "1.0.0");
    json body = {
        {"license_key", licenseKey},
        {"machine_id", machineId},
        {"client_version", "1.0.0"}
    };
    req.set_body(body.dump(), "application/json");

    auto resp = client.request(req).get();
    auto dataBod = resp.extract_json().get();
    auto data = dataBod["data"];

    // 1. 解析 authorization: base64url -> "version.payload.signature"
    // 2. 用 libsodium crypto_sign_verify_detached 验证 Ed25519 签名
    // 3. 检查 payload.status == "authorized"
    // 4. 检查 payload.product_id == "mytool"
    // 5. 检查 payload.expire_at > current_time

    LicenseResult result;
    result.authorized = true;
    result.sessionId = data["session_id"].as_string();
    result.expireAt = /* payload["expire_at"] */;
    return result;
}
```

---

## 10. C# 接入示例

```csharp
using System.Net.Http;
using System.Text;
using System.Text.Json;
using NSec.Cryptography;  // Ed25519 验签

class LicenseClient {
    private static readonly string ServerUrl = "https://license.example.com/api/v1";
    private static readonly string ApiKey = "app_xxxxxxxxxxxxxxxx";
    private static readonly string ProductId = "mytool";
    // Ed25519 public key bytes
    private static readonly byte[] PublicKey = Convert.FromBase64String("...");

    public static async Task<JsonElement> VerifyAsync(string licenseKey, string machineId) {
        using var http = new HttpClient();
        http.DefaultRequestHeaders.Add("Authorization", $"Bearer {ApiKey}");
        http.DefaultRequestHeaders.Add("X-Product-ID", ProductId);
        http.DefaultRequestHeaders.Add("X-Client-Version", "1.0.0");
        http.DefaultRequestHeaders.Add("X-Request-ID", Guid.NewGuid().ToString());

        var body = JsonSerializer.Serialize(new {
            license_key = licenseKey,
            machine_id = machineId,
            client_version = "1.0.0"
        });
        var resp = await http.PostAsync($"{ServerUrl}/license/verify",
            new StringContent(body, Encoding.UTF8, "application/json"));
        var json = JsonDocument.Parse(await resp.Content.ReadAsStringAsync()).RootElement;

        if (!json.GetProperty("success").GetBoolean())
            throw new Exception($"Error {json.GetProperty("code")}");

        var authorization = json.GetProperty("data").GetProperty("authorization").GetString();
        // 1. Base64URL decode authorization -> "version.payload.signature"
        // 2. Verify Ed25519 signature using NSec: PublicKey.Verify(payload, signature)
        // 3. Parse payload JSON, check status/product_id/expire_at
        return json.GetProperty("data");
    }
}
```

---

## 11. Go 接入示例

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "github.com/go-fed/httpsig"  // 或 golang.org/x/crypto/ed25519
    "golang.org/x/crypto/ed25519"
)

const (
    serverURL   = "https://license.example.com/api/v1"
    apiKey      = "app_xxxxxxxxxxxxxxxx"
    productID   = "mytool"
)

var publicKey ed25519.PublicKey // = ed25519.PublicKey(base64decoded)

func VerifyLicense(licenseKey, machineID string) error {
    payload, _ := json.Marshal(map[string]string{
        "license_key":    licenseKey,
        "machine_id":     machineID,
        "client_version": "1.0.0",
    })
    req, _ := http.NewRequest("POST", serverURL+"/license/verify", bytes.NewReader(payload))
    req.Header.Set("Authorization", "Bearer "+apiKey)
    req.Header.Set("X-Product-ID", productID)
    req.Header.Set("Content-Type", "application/json")

    resp, err := http.DefaultClient.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)

    var result struct {
        Success bool `json:"success"`
        Code    int  `json:"code"`
        Data    struct {
            Authorization string `json:"authorization"`
        } `json:"data"`
    }
    json.Unmarshal(body, &result)
    if !result.Success {
        return fmt.Errorf("error %d", result.Code)
    }

    // 1. Base64URL decode authorization -> "version.payload.signature"
    // 2. ed25519.Verify(publicKey, payloadBytes, signature) -> bool
    // 3. check payload fields
    return nil
}
```

---

## 12. JavaScript 接入示例

```javascript
// Node.js, 使用 tweetnacl 做 Ed25519 验签
const nacl = require('tweetnacl');
const axios = require('axios');

const SERVER_URL = 'https://license.example.com/api/v1';
const API_KEY = 'app_xxxxxxxxxxxxxxxx';
const PRODUCT_ID = 'mytool';
const PUBLIC_KEY = Buffer.from('...', 'base64'); // Ed25519 public key

function b64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  return Buffer.from(str, 'base64');
}

function verifyAuthorization(auth) {
  const raw = b64urlDecode(auth).toString('ascii');
  const [verB64, payloadB64, sigB64] = raw.split('.');
  const payloadBytes = b64urlDecode(payloadB64);
  const signature = b64urlDecode(sigB64);
  const ok = nacl.sign.detached.verify(payloadBytes, signature, PUBLIC_KEY);
  if (!ok) throw new Error('signature invalid');
  return JSON.parse(payloadBytes.toString('utf8'));
}

async function verifyLicense(licenseKey, machineId) {
  const resp = await axios.post(`${SERVER_URL}/license/verify`, {
    license_key: licenseKey,
    machine_id: machineId,
    client_version: '1.0.0',
  }, {
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'X-Product-ID': PRODUCT_ID,
      'X-Client-Version': '1.0.0',
      'X-Request-ID': crypto.randomUUID(),
    },
    timeout: 10000,
  });
  const data = resp.data;
  if (!data.success) throw new Error(`Error ${data.code}: ${data.message}`);
  const payload = verifyAuthorization(data.data.authorization);
  if (payload.status !== 'authorized') throw new Error('not authorized');
  if (payload.product_id !== PRODUCT_ID) throw new Error('product mismatch');
  return payload;
}
```

---

## 13. 客户端授权验证流程

```
收到服务器响应
    ↓
验证 Ed25519 签名（使用 Public Key）
    ↓
检查 payload.status == "authorized"
    ↓
检查 payload.product_id == 预期产品
    ↓
检查 payload.expire_at > 当前时间
    ↓
授权成功 → 运行程序
    ↓
定时 Heartbeat（5~10 分钟）
```

---

## 14. 重试规则

- 网络错误 / HTTP 5xx / 429：指数退避重试，最多 3 次
- 业务错误（4001~4015）：不重试，直接进入失败流程

---

## 15. 部署

```bash
# 1. 生成密钥
python scripts/generate_keys.py --write

# 2. 配置 .env
cp .env.example .env
# 编辑数据库、Redis、密钥等配置

# 3. 初始化数据库
python scripts/init_db.py

# 4. 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 或 Docker
docker-compose up -d
```

---

## 16. OpenAPI / Swagger

启动服务后访问：

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`
- OpenAPI JSON: `/openapi.json`
