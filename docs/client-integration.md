# 客户端对接指南

本文档面向需要接入卡密授权系统的客户端开发者，说明需要调用的 API、请求/响应格式、签名验证方法以及安全注意事项。

---

## 1. 概述

客户端接入流程：

```
用户输入卡密 → 调用 verify/activate → 获取 session → 定期 heartbeat → 退出时 deactivate
```

所有客户端 API 的 Base URL 为：

```
{服务器地址}/api/v1/license
```

例如：`http://localhost:8000/api/v1/license/verify`

---

## 2. 鉴权方式

每个请求必须携带产品的 **API Key**，通过 HTTP Header 传递：

```http
Authorization: Bearer {API_KEY}
```

> API Key 在管理后台「产品管理」页面创建产品时自动生成，格式为 `app_xxxxxxxx`。
> API Key 是产品级密钥，**不是**卡密。一个产品对应一个 API Key，该产品下所有卡密共用。

可选 Header：

| Header | 说明 | 是否必须 |
|--------|------|----------|
| `X-Product-ID` | 产品 ID，用于交叉校验 | 否（不传则由 API Key 自动识别） |
| `X-Client-Version` | 客户端版本号 | 否 |
| `X-Request-ID` | 请求唯一标识，用于日志追踪 | 否（不传服务端自动生成） |

---

## 3. 统一响应结构

### 成功

```json
{
  "success": true,
  "code": 0,
  "message": "成功",
  "request_id": "uuid",
  "data": { ... }
}
```

### 失败

```json
{
  "success": false,
  "code": 4004,
  "message": "卡密已禁用",
  "request_id": "uuid",
  "data": null,
  "error": {
    "type": "license_error",
    "retryable": false
  }
}
```

### 错误码表

| 错误码 | 含义 | 客户端处理建议 |
|--------|------|----------------|
| 4001 | 卡密无效 | 提示用户检查卡密 |
| 4002 | 卡密不存在 | 提示用户卡密错误 |
| 4003 | 卡密已过期 | 提示用户续期或购买新卡密 |
| 4004 | 卡密已禁用 | 提示用户联系管理员 |
| 4005 | 产品不匹配 | 检查 API Key 和 Product ID 是否对应 |
| 4006 | API Key 无效 | 检查 API Key 配置 |
| 4007 | 请求参数无效 | 检查请求体格式 |
| 4008 | 签名验证失败 | 签名被篡改，可能遭遇中间人攻击 |
| 4009 | 会话无效 | 需要重新验证/激活卡密 |
| 4010 | 会话已过期 | 需要重新验证/激活卡密 |
| 4011 | 请求已过期 | 客户端时间偏差过大，检查本地时钟 |
| 4012 | 请求已被重放 | 防重放保护触发 |
| 4013 | 请求频率超限 | 退避后重试，读取 `Retry-After` Header |
| 4014 | 客户端版本不支持 | 提示用户升级客户端 |
| 4015 | 产品已禁用 | 联系管理员 |
| 5001 | 服务器内部错误 | 可重试 |
| 5002 | 数据库错误 | 可重试 |
| 5003 | 签名服务错误 | 联系管理员 |

---

## 4. API 详情

### 4.1 验证卡密 - POST /verify

验证卡密有效性。如果卡密状态为 `UNUSED`，会自动激活并创建会话。如果已是 `ACTIVE`，直接创建新会话。

**请求体：**

```json
{
  "license_key": "用户输入的卡密",
  "machine_id": "机器唯一标识（可选）",
  "client_version": "1.0.0（可选）"
}
```

**响应 data：**

```json
{
  "authorization": "base64url编码的签名数据",
  "session_id": "会话ID",
  "session_token": "会话令牌（仅此一次返回，需保存）",
  "expire_at": "2026-09-24T12:00:00Z",
  "server_time": "2026-09-23T12:00:00Z"
}
```

> **重要：** `session_token` 只在 verify/activate 响应中返回一次，后续 heartbeat 请求需要携带它。客户端必须安全存储（如加密存入本地配置），不要明文写入日志。

### 4.2 激活卡密 - POST /activate

显式激活卡密。与 verify 的区别：activate 对已激活的卡密不会自动续期，仅返回当前状态。

**请求体：** 同 verify

**响应 data：** 同 verify

### 4.3 心跳保活 - POST /heartbeat

定期调用以保持会话活跃。服务端会更新会话的最后心跳时间，并重新校验卡密状态（如是否已过期/禁用）。

**请求体：**

```json
{
  "session_id": "从 verify/activate 获取的会话ID",
  "session_token": "从 verify/activate 获取的会话令牌",
  "machine_id": "机器唯一标识（可选）",
  "client_version": "1.0.0（可选）"
}
```

**响应 data：**

```json
{
  "authorization": "新的签名数据",
  "session_id": "会话ID",
  "expire_at": "2026-09-24T12:00:00Z",
  "server_time": "2026-09-23T12:00:00Z"
}
```

> **建议心跳间隔：** 30~60 秒。间隔过长可能导致会话过期被服务端清理，过短则增加服务器负载。

### 4.4 注销会话 - POST /deactivate

主动注销当前会话（如用户退出登录）。注销后 session_token 立即失效。

**请求体：**

```json
{
  "session_id": "会话ID",
  "session_token": "会话令牌"
}
```

**响应 data：**

```json
{
  "deactivated": true
}
```

### 4.5 查询卡密信息 - GET /info

查询当前会话关联的卡密状态和到期时间。

**Query 参数：**

| 参数 | 说明 |
|------|------|
| `session_id` | 会话 ID（必须） |
| `session_token` | 会话令牌（可选，但建议携带） |

**响应 data：**

```json
{
  "product_id": "my_product",
  "license_id": "LIC_xxxxxxxx",
  "status": "ACTIVE",
  "activated_at": "2026-09-23T12:00:00Z",
  "expire_at": "2026-09-24T12:00:00Z",
  "server_time": "2026-09-23T12:30:00Z"
}
```

---

## 5. 签名验证（防篡改）

每次 verify/activate/heartbeat 响应中的 `authorization` 字段是服务端用 **Ed25519 私钥** 签名的授权数据。客户端应使用预置的 **Ed25519 公钥** 验证签名，确保授权数据未被篡改。

### authorization 格式

```
base64url( version_b64 . payload_b64 . signature_b64 )
```

解码后得到三段用 `.` 分隔的 base64url 字符串：

1. `version` - 签名版本号（当前为 `1`）
2. `payload` - JSON 授权数据
3. `signature` - Ed25519 签名

### payload 内容

```json
{
  "version": 1,
  "status": "authorized",
  "license_id": "LIC_xxxxxxxx",
  "product_id": "my_product",
  "issued_at": 1695465600,
  "expire_at": 1695552000,
  "server_time": 1695465600,
  "session_id": "SES_xxxxxxxx",
  "nonce": "随机字符串"
}
```

### 客户端验证步骤（Python 示例）

```python
import base64, json
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

PUBLIC_KEY_B64 = "从管理后台获取的 Ed25519 公钥"

def verify_authorization(authorization: str) -> dict:
    # 1. 外层 base64url 解码
    raw = base64.urlsafe_b64decode(authorization + "=" * (-len(authorization) % 4))
    version_b64, payload_b64, sig_b64 = raw.decode("ascii").split(".")

    # 2. 解码各段
    def b64url_decode(s):
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    payload_bytes = b64url_decode(payload_b64)
    signature = b64url_decode(sig_b64)

    # 3. 验证签名
    verify_key = VerifyKey(b64url_decode(PUBLIC_KEY_B64))
    verify_key.verify(payload_bytes, signature)  # 失败会抛出 BadSignatureError

    # 4. 解析 payload
    return json.loads(payload_bytes)
```

### 为什么要验证签名？

- **防中间人篡改：** 即使 HTTPS 被劫持（如企业代理），攻击者也无法伪造合法授权数据
- **防本地伪造：** 客户端缓存的授权数据如果被篡改，签名验证会失败
- **防重放：** payload 中的 `nonce` 和时间戳可用于防重放检查

---

## 6. 安全注意事项

### 6.1 防止本地绕过验证

这是客户端接入最常见的安全问题。攻击者可以通过以下方式绕过验证：

- **修改本地配置文件：** 将"已验证"标志改为 true
- **Hook 网络请求：** 拦截 verify 请求并返回伪造的成功响应
- **替换公钥：** 用攻击者自己的密钥对伪造签名
- **修改二进制：** 直接 patch 客户端跳过验证逻辑

**防护建议：**

1. **验证签名而非仅检查 HTTP 状态码：** 不要只判断 `success == true`，必须用公钥验证 `authorization` 签名。即使攻击者伪造了 HTTP 响应，没有私钥也无法生成合法签名。

2. **公钥硬编码在客户端中：** Ed25519 公钥不要从配置文件读取，应编译进二进制或混淆存储。攻击者替换公钥后签名验证会失败。

3. **检查 payload 字段：** 验证签名后还需检查：
   - `status == "authorized"`
   - `expire_at` 未过期（与 `server_time` 对比，而非本地时间）
   - `license_id` 和 `product_id` 与预期一致
   - `nonce` 未被使用过（防重放）

4. **核心功能与服务端绑定：** 不要在本地做"一次验证永久使用"的逻辑。关键功能执行前应检查会话有效性（heartbeat 或本地缓存的授权未过期）。

5. **代码混淆与反调试：** 对验证逻辑进行代码混淆，增加逆向难度。检测调试器附加、内存修改等。

6. **不要信任本地时间：** 攻击者可以修改系统时间延长到期。应使用 payload 中的 `server_time` 和 `expire_at` 判断，而非 `local_time`。

### 6.2 机器码绑定

`machine_id` 用于将卡密绑定到特定设备。建议：

- 使用硬件序列号、MAC 地址、磁盘 ID 等组合生成，而非随机 UUID
- 对 `machine_id` 做哈希处理，不传输明文硬件信息
- 服务端会记录首次激活的 machine_id，后续验证时可校验一致性

### 6.3 session_token 安全

- `session_token` 只在 verify/activate 时返回一次，必须安全存储
- 不要写入日志、URL 参数或明文文件
- 建议使用操作系统的安全存储机制（如 Windows DPAPI、macOS Keychain）
- 怀疑泄露时调用 deactivate 注销会话，重新验证

### 6.4 离线场景

系统支持配置离线宽限期（`OFFLINE_GRACE_PERIOD`）。在宽限期内，客户端可以使用缓存的授权数据离线运行。但：

- 宽限期到期后必须重新在线验证
- 离线期间无法检测卡密是否被服务端禁用/撤销
- 对高价值软件建议设置较短的宽限期或禁用离线模式

### 6.5 网络安全

- 生产环境必须使用 HTTPS，防止授权数据被窃听
- 客户端应做证书校验（pinning 更佳），防止中间人攻击
- 设置合理的请求超时（建议 10 秒），避免网络问题导致客户端卡死
- 对 4013（频率超限）错误实现退避重试，读取响应 Header `Retry-After`

---

## 7. 完整接入流程示例（伪代码）

```
# 1. 启动时检查本地缓存的授权
cached_auth = load_from_secure_storage()
if cached_auth and verify_signature(cached_auth) and not is_expired(cached_auth):
    # 有有效缓存，进入心跳模式
    start_heartbeat_loop()
else:
    # 需要用户输入卡密
    license_key = prompt_user("请输入卡密")
    resp = POST("/verify", {license_key, machine_id})
    if resp.success:
        # 验证签名
        payload = verify_authorization(resp.data.authorization)
        if payload.status == "authorized":
            save_to_secure_storage(resp.data.session_id, resp.data.session_token)
            start_heartbeat_loop()
        else:
            show_error("授权验证失败")
    else:
        show_error(resp.message)

# 2. 心跳循环
function heartbeat_loop():
    while running:
        sleep(30)
        resp = POST("/heartbeat", {session_id, session_token, machine_id})
        if resp.success:
            payload = verify_authorization(resp.data.authorization)
            if payload.status != "authorized" or payload.expire_at < payload.server_time:
                show_error("授权已失效，请重新验证")
                break
        else:
            if resp.code in (4009, 4010):  # 会话无效/过期
                # 需要重新验证
                re_verify()
            elif resp.code == 4013:  # 频率超限
                sleep(resp.retry_after)
            else:
                show_error(resp.message)
                break

# 3. 退出时
function on_exit():
    POST("/deactivate", {session_id, session_token})
    clear_secure_storage()
```

---

## 8. 多语言接入示例

### Python

```python
import requests

API_URL = "http://localhost:8000/api/v1/license"
API_KEY = "app_xxxxxxxx"

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# 验证
resp = requests.post(f"{API_URL}/verify", headers=headers,
    json={"license_key": "YOUR_LICENSE_KEY", "machine_id": "MACHINE_ID"})
data = resp.json()
if data["success"]:
    session_id = data["data"]["session_id"]
    session_token = data["data"]["session_token"]
    # 保存 session_id 和 session_token

# 心跳
requests.post(f"{API_URL}/heartbeat", headers=headers,
    json={"session_id": session_id, "session_token": session_token})
```

### C++

```cpp
// 使用 libcurl + nlohmann/json
#include <curl/curl.h>
#include <nlohmann/json.hpp>

// 验证卡密
nlohmann::json body = {
    {"license_key", "YOUR_LICENSE_KEY"},
    {"machine_id", "MACHINE_ID"}
};
// POST to http://localhost:8000/api/v1/license/verify
// Header: Authorization: Bearer app_xxxxxxxx
// 解析响应中的 session_id 和 session_token
```

### JavaScript / Node.js

```javascript
const resp = await fetch("http://localhost:8000/api/v1/license/verify", {
    method: "POST",
    headers: {
        "Authorization": "Bearer app_xxxxxxxx",
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
        license_key: "YOUR_LICENSE_KEY",
        machine_id: "MACHINE_ID"
    })
});
const data = await resp.json();
if (data.success) {
    const { session_id, session_token } = data.data;
    // 保存 session_id 和 session_token
}
```

### Go

```go
body, _ := json.Marshal(map[string]string{
    "license_key": "YOUR_LICENSE_KEY",
    "machine_id":  "MACHINE_ID",
})
req, _ := http.NewRequest("POST", "http://localhost:8000/api/v1/license/verify",
    bytes.NewReader(body))
req.Header.Set("Authorization", "Bearer app_xxxxxxxx")
req.Header.Set("Content-Type", "application/json")
resp, _ := http.DefaultClient.Do(req)
// 解析 JSON 响应
```

---

## 9. 常见问题

**Q: verify 和 activate 有什么区别？**

A: verify 会自动激活未使用的卡密（UNUSED → ACTIVE），适合首次使用场景。activate 是显式激活，对已激活的卡密不会改变其到期时间。实际使用中，大多数客户端只需调用 verify 即可。

**Q: 一个卡密可以同时在多台机器上使用吗？**

A: 可以创建多个会话，但建议通过 machine_id 绑定限制。服务端不强制单设备限制，由客户端根据业务需求实现。

**Q: 心跳失败后怎么办？**

A: 如果错误码是 4009（会话无效）或 4010（会话已过期），需要重新调用 verify 获取新会话。其他错误可重试。

**Q: session_token 丢了怎么办？**

A: 无法恢复，需要重新调用 verify/activate 获取新会话和新 token。旧会话会在过期后自动失效。

**Q: 如何测试对接？**

A: 使用项目自带的测试客户端：`python client/main.py`，按菜单引导操作即可。
