# WebServer 安全整改方案：一次性密钥认证

## 1. 现状分析

### 1.1 当前安全态势

| 项目 | 现状 | 风险 |
|------|------|------|
| 服务绑定 | `0.0.0.0`（所有接口） | 局域网任何设备可访问 |
| 认证机制 | **无** | 任何人可调用全部 API |
| CORS | `Access-Control-Allow-Origin: *` | 恶意网页可跨域调用 |
| 安全头 | 无 CSP / X-Frame-Options | 可被 iframe 嵌入 |
| Debug 模式 | 默认关闭，可 `--debug` 开启 | 开启后暴露 Werkzeug REPL |

### 1.2 高危 API 清单

以下 API 在无认证情况下暴露，攻击者可直接利用：

- `/api/fpb/inject` — 向设备注入任意代码
- `/api/file/write` — 写入主机文件系统（`$HOME` 下任意路径）
- `/api/serial/send` — 向设备发送任意 shell 命令
- `/api/memory/write` — 写入设备任意内存地址
- `/api/config` POST — 修改服务器全部配置
- `/api/browse` — 浏览主机文件系统
- `/api/transfer/*` — 上传/下载/删除设备文件

### 1.3 攻击场景

1. **局域网嗅探**：同一 WiFi 下的设备扫描到 5500 端口，直接访问所有功能
2. **跨域攻击**：用户浏览恶意网页，JS 通过 `fetch('http://<lan_ip>:5500/api/...')` 调用 API（CORS `*` 允许）
3. **Debug REPL**：若 `--debug` 开启，Werkzeug debugger PIN 可被暴力破解

## 2. 设计方案

### 2.1 核心思路

服务启动时生成一次性随机 token，打印在终端。非 localhost 访问时，必须在 URL query 或 HTTP header 中携带该 token，否则返回 403。

```
启动日志:
  🏠 Local:   http://127.0.0.1:5500
  🌐 Network: http://192.168.1.100:5500?token=a3f8b2c1
  🔑 Token:   a3f8b2c1
```

### 2.2 认证规则

```
请求来源是 127.0.0.1 / ::1 ?
  ├── 是 → 放行（localhost 免认证）
  └── 否 → 检查 token
              ├── URL query: ?token=xxx
              ├── HTTP header: X-Auth-Token: xxx
              └── Cookie: fpbinject_token=xxx（首次验证后自动设置）
                    ├── 匹配 → 放行
                    └── 不匹配 → 403 Forbidden
```

### 2.3 Token 生命周期

| 阶段 | 行为 |
|------|------|
| 生成 | 服务启动时 `secrets.token_hex(4)` 生成 8 字符 hex token |
| 分发 | 打印在启动 banner 中，仅服务器终端可见 |
| 验证 | Flask `before_request` 钩子统一检查 |
| Cookie | 首次 token 验证通过后，`Set-Cookie: fpbinject_token=xxx`，后续请求自动携带 |
| 过期 | 随服务进程结束失效，重启生成新 token |
| 禁用 | `--no-auth` 参数可关闭认证（向后兼容） |

### 2.4 CORS 收紧

将 `CORS(app)` 改为仅允许本机来源：

```python
CORS(app, origins=[
    "http://127.0.0.1:*",
    "http://localhost:*",
    f"http://{lan_ip}:{port}",
])
```

## 3. 实现方案

### 3.1 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `main.py` | 生成 token，传入 `create_app()`，打印到 banner |
| `app/middleware.py` | 新建，`before_request` 钩子实现 token 校验 |
| `create_app()` | 注册 middleware，收紧 CORS |
| `templates/index.html` | 页面加载时从 URL 提取 token 存入 cookie |

### 3.2 middleware.py 伪代码

```python
import secrets
from flask import request, abort, make_response

def init_auth(app, token):
    """Register authentication middleware."""

    LOCALHOST_ADDRS = {"127.0.0.1", "::1"}

    @app.before_request
    def check_token():
        # Localhost is always allowed
        if request.remote_addr in LOCALHOST_ADDRS:
            return None

        # Check token from query, header, or cookie
        req_token = (
            request.args.get("token")
            or request.headers.get("X-Auth-Token")
            or request.cookies.get("fpbinject_token")
        )

        if req_token != token:
            abort(403)

        # Set cookie on first successful token auth
        if not request.cookies.get("fpbinject_token"):
            @after_this_request
            def set_cookie(response):
                response.set_cookie(
                    "fpbinject_token", token,
                    httponly=True, samesite="Lax",
                )
                return response

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response
```

### 3.3 main.py 改动

```python
import secrets

def create_app(auth_token=None):
    app = Flask(...)
    CORS(app, origins=[...])  # 收紧
    if auth_token:
        from app.middleware import init_auth
        init_auth(app, auth_token)
    register_routes(app)
    return app

def main():
    ...
    token = secrets.token_hex(4)  # e.g. "a3f8b2c1"
    app = create_app(auth_token=None if args.no_auth else token)

    # Banner
    logger.info(f"  ║  🌐 Network: {lan_url}?token={token}")
    logger.info(f"  ║  🔑 Token:   {token}")
```

### 3.4 前端 token 传递

页面首次加载时，从 URL `?token=xxx` 提取 token 并存入 cookie，后续所有 `fetch` 请求自动携带：

```javascript
// 在页面加载时执行
const urlToken = new URLSearchParams(location.search).get('token');
if (urlToken) {
    document.cookie = `fpbinject_token=${urlToken}; path=/; SameSite=Lax`;
    // 清理 URL 中的 token 参数
    const url = new URL(location);
    url.searchParams.delete('token');
    history.replaceState(null, '', url);
}
```

## 4. 测试计划

| 测试用例 | 预期 |
|---------|------|
| localhost 无 token 访问 | 200 OK |
| 非 localhost 无 token 访问 | 403 Forbidden |
| 非 localhost 带正确 query token | 200 OK + Set-Cookie |
| 非 localhost 带正确 header token | 200 OK |
| 非 localhost 带正确 cookie token | 200 OK |
| 非 localhost 带错误 token | 403 Forbidden |
| `--no-auth` 模式 | 所有请求 200 OK |
| 重启后旧 token | 403 Forbidden |
| CORS 非白名单 Origin | 无 ACAO 头 |

## 5. 向后兼容

- `--no-auth` 参数：禁用 token 认证，行为与当前一致
- localhost 访问完全不受影响
- 自动打开浏览器的 URL 自动附带 `?token=xxx`
