# fpb_cli 远程控制（走外部端口）可行性分析

## 背景与诉求

用户希望 `fpb_cli` 能够通过**外部端口远程控制**：即 CLI 运行在 A 机器，目标设备（串口）连接在 B 机器，B 机器上跑着 WebServer，A 机器的 CLI 通过网络把命令发到 B 机器执行。

本文分析当前 `fpb_cli` 的架构对远程控制的支持现状、缺口，以及补齐方案。

---

## 一、当前架构：CLI 已是「代理优先」设计

`fpb_cli` 的运行模式由 `cli/fpb_cli.py` + `cli/server_proxy.py` 共同决定，已经天然具备走 HTTP API 的能力。

### 1.1 三种运行模式

| 模式 | 触发条件 | 行为 |
|------|----------|------|
| 代理模式（默认） | 指定 `--port` 且未加 `--direct` | 通过 HTTP API 把操作转发给 WebServer |
| 自动拉起 | 代理模式下本地 WebServer 未运行 | 自动 `subprocess` 启动本地 WebServer 再走代理 |
| 直连模式 | 加 `--direct` | CLI 自己打开串口（绕过 WebServer） |

关键代码（`FPBCLI.__init__`）：

```python
if port:
    proxy = ServerProxy(base_url=server_url)
    if proxy.is_server_running():        # 1) 已有 server → 直接用
        self._proxy = proxy
        ...
    if proxy.launch_server():            # 2) 没有 → 本地自动拉起
        self._proxy = proxy
        ...
    self._direct_connect(port, baudrate) # 3) 拉起失败 → 直连串口
```

### 1.2 已经存在 `--server-url` 参数

CLI 已经暴露了 `--server-url`：

```python
parser.add_argument(
    "--server-url",
    type=str,
    default=DEFAULT_SERVER_URL,   # http://127.0.0.1:5500
    help=f"WebServer URL for proxy mode (default: {DEFAULT_SERVER_URL}).",
)
```

这意味着**理论上**已经可以：

```bash
fpb_cli.py --server-url http://192.168.1.20:5500 --port /dev/ttyACM0 info
```

`ServerProxy` 内部所有请求都基于 `self.base_url`，URL 本身就支持远程主机。所以「走外部端口远程控制」在传输层已经具备基础。

---

## 二、远程控制的真实缺口

虽然传输层支持远程 URL，但要真正可用，存在以下几个**必须解决**的缺口。

### 2.1 认证 Token 未透传（最关键缺口）

WebServer 的认证中间件（`app/middleware.py`）逻辑：

- **localhost（127.0.0.1 / ::1）请求免认证**。
- **非 localhost 请求必须携带 token**（query `?token=`、`X-Auth-Token` 头或 cookie），否则返回 403。

而 `ServerProxy` 虽然构造函数支持 `token` 参数：

```python
def __init__(self, base_url=DEFAULT_SERVER_URL, token=None):
    self.token = token
def _build_url(self, path):
    url = f"{self.base_url}{path}"
    if self.token:
        url += f"...token={self.token}"
```

**但 CLI 侧从未传入 token**：`FPBCLI.__init__` 创建 `ServerProxy(base_url=server_url)` 时没有 `token` 参数，CLI 也没有 `--token` 命令行选项。

结论：
- 本地（localhost）代理能用，是因为免认证。
- **一旦 `--server-url` 指向远程 IP，所有请求都会被 403 拒绝**，因为没带 token。

这是远程控制目前**不可用的首要原因**。

### 2.2 自动拉起逻辑在远程场景无意义

`is_server_running()` 探测失败时，CLI 会尝试 `launch_server()` 在**本地**拉起 WebServer。但远程场景下：

- 目标 server 在远端，本地探测失败不代表远端没起。
- 即便探测到远端不可达，本地拉起的 server 也连不到远端的串口设备。

所以远程模式下应当**禁用自动拉起**，探测失败直接报错，而不是 fallback 到本地拉起或直连串口。

### 2.3 路径语义是「服务端本地路径」

这是一个**容易踩坑的语义问题**。注入相关操作中：

- `elf_path`、`compile_commands_path`、`original_source_file` 这些路径，最终是在 **WebServer 所在机器**上被解析、读取、编译的。
- CLI 的 `inject` 代理实现（`server_proxy.inject`）会把**源码内容读出来**（`source_content`）随请求发送，这部分是内容透传，没问题。
- 但 `elf_path` / `compile_commands_path` 仍是路径字符串，指向的是**服务端文件系统**。

含义：远程注入时，ELF 和 compile_commands.json 必须存在于**服务端**机器上，路径也要写成服务端的路径。CLI 端本地的同名文件不会被上传。这对用户而言是需要明确告知的心智模型。

> 反观本地 ELF 分析类命令（`analyze` / `disasm` / `search` / `get-symbols` / `signature` / `compile`）——它们**不走代理**，而是用 CLI 本地的 `self._fpb` 直接操作本地 ELF（见 `FPBCLI.analyze` 等）。因此这些命令在「远程」语义下其实操作的是**本地文件**，与设备无关。需要在文档中区分清楚：哪些命令作用于本地、哪些转发到远端设备。

### 2.4 命令分类：哪些可远程、哪些不行

| 命令 | 是否走代理 | 远程语义 |
|------|-----------|----------|
| `analyze` / `disasm` / `search` / `get-symbols` / `signature` | 否（本地 `self._fpb`） | 操作 **CLI 本地** ELF，与远端设备无关 |
| `decompile` | 否（本地 Ghidra） | 操作本地 ELF + 本地 Ghidra |
| `compile` | 否（本地编译） | 用本地工具链编译，仅校验 |
| `info` / `inject` / `unpatch` | 是 | 转发到远端设备 ✅ |
| `mem-read` / `mem-write` / `mem-dump` | 是 | 转发到远端设备 ✅ |
| `test-serial` | 是 | 转发到远端设备 ✅ |
| `serial-send` / `serial-read` | 是 | 转发到远端设备 ✅ |
| `file-*`（list/stat/download/upload/remove/mkdir/rename） | 是 | 转发到远端设备 ✅ |
| `connect` / `disconnect` | 是 | 控制远端 server 的串口连接 ✅ |

设备类操作（info/inject/mem/serial/file）都已经有代理实现，**功能上是齐全的**，缺的只是认证与少量健壮性处理。

### 2.5 服务端绑定与安全现状

- WebServer 默认 `--host 0.0.0.0`（`main.py` parse_args），**默认就监听所有网卡**，具备被远程访问的条件。
- 默认启用 token 认证（`secrets.token_hex(4)`，启动 banner 打印 `Network` URL 含 token）。
- 有 auto-ban 引擎（`app/auto_ban.py`）做扫描器节流，白名单是 localhost。

也就是说，远程访问的**网络与安全骨架已经具备**，问题集中在 CLI 客户端没有把 token 用起来。

---

## 三、可行性结论

**结论：可行，且改动量小。** 当前架构（代理优先 + `--server-url` + `ServerProxy.token` 支持 + 服务端 0.0.0.0 监听 + token 认证）已经为远程控制铺好了 90% 的路。主要缺口是 CLI 没有把认证 token 透传到 `ServerProxy`，以及远程模式下的自动拉起/直连 fallback 不应触发。

设备类操作（注入、内存读写、串口、文件传输）的代理实现都已存在，远程可直接复用。

---

## 四、实施方案

### 4.1 必做项（让远程真正可用）

**1) CLI 增加 `--token` 选项并透传给 ServerProxy**

```python
# main() argparse
parser.add_argument(
    "--token",
    type=str,
    default=os.environ.get("FPB_TOKEN"),  # 支持环境变量，避免命令行泄露
    help="Auth token for remote WebServer (non-localhost requires it).",
)

# FPBCLI.__init__ 创建代理时
proxy = ServerProxy(base_url=server_url, token=token)
```

建议同时支持 `FPB_TOKEN` 环境变量，避免 token 出现在 shell history / ps 输出中。

**2) 远程模式禁用「自动拉起」与「直连 fallback」**

判定「远程」：`server_url` 的 host 不是 127.0.0.1 / localhost / ::1。远程时：

```python
if is_remote(server_url):
    proxy = ServerProxy(base_url=server_url, token=token)
    if not proxy.is_server_running():
        raise FPBCLIError(f"Remote server not reachable: {server_url}")
    self._proxy = proxy
    # 不 launch_server()，不 fallback 直连串口
    return
```

否则远端不可达时会错误地在本地拉起 server 或尝试打开本地不存在的串口。

**3) 401/403 错误要给出清晰提示**

`ServerProxy._get/_post` 目前直接 `urlopen`，403 会抛 `HTTPError`。应捕获并提示「token 缺失或错误」，而不是输出一个含糊的异常。

### 4.2 健壮性增强（建议）

- **超时与重试**：远程网络延迟比本地高，`_API_TIMEOUT=30` 对大文件上传/注入可能偏短，建议针对 upload/inject 单独放宽（upload 已用 120s）。
- **HTTPS 支持**：当前仅 `http://`。跨不可信网络时 token 明文传输有风险，建议支持 `https://` + 自签证书或反向代理。
- **路径语义文档化**：明确 `elf_path` / `compile_commands_path` 指服务端路径；本地分析命令（analyze/disasm 等）作用于本地。
- **连接探测命令**：可加一个 `fpb_cli.py --server-url ... status` 子命令，仅探测远端 server 与设备连接状态，便于排错。

### 4.3 使用示例（补齐后）

```bash
# B 机器（连设备）：启动 server，记下 banner 里的 token
./main.py --host 0.0.0.0 --port 5500
#   🔑 Token: a1b2c3d4

# A 机器（远程控制）：
export FPB_TOKEN=a1b2c3d4

# 远程模式下 --port 可选：若 B 机器的 server 已连接设备，无需再传 --port
fpb_cli.py --server-url http://192.168.1.20:5500 info
fpb_cli.py --server-url http://192.168.1.20:5500 mem-read 0x20000000 64

# 仅当远端 server 尚未连接设备时，才用 --port 让 server 去打开对应串口
fpb_cli.py --server-url http://192.168.1.20:5500 --port /dev/ttyACM0 info

# 注入：--elf / --compile-commands 是 B 机器 上的路径
fpb_cli.py --server-url http://192.168.1.20:5500 \
    inject myFunc /srv/patches/patch.c \
    --elf /srv/fw/firmware.elf \
    --compile-commands /srv/fw/build/compile_commands.json
```

> 关于 `--port`：串口属于 **server 所在机器**，不是 CLI。代理模式下 `--port` 不是必选项——只有在 server 还没连接设备时，才用它告诉 server 去打开哪个串口。本地分析类命令（analyze/disasm/search/compile）完全不需要 `--port`。

---

## 五、风险与注意事项

| 风险点 | 说明 |
|--------|------|
| Token 泄露 | 命令行参数会进 history / ps，优先用 `FPB_TOKEN` 环境变量或 cookie 文件 |
| 明文传输 | 默认 HTTP，token 与数据明文，跨公网需 HTTPS / SSH 隧道 |
| 路径语义混淆 | inject/elf 路径是服务端路径，用户易误以为是本地路径 |
| 0.0.0.0 默认暴露 | server 默认监听全网卡，配合弱 token（4 字节）在公网有风险，建议内网使用或加强 token |
| 自动拉起误触发 | 远程不可达时不应在本地拉起 server，需按 4.1-2 处理 |
| 本地命令伪「远程」 | analyze/disasm 等不转发，远程用户可能误以为在分析远端 ELF |

---

## 六、建议

1. **可行，推荐补齐。** 最小可用集就是 4.1 的三件事：`--token` 透传、远程禁用自动拉起、认证错误友好提示。完成后即可通过外部端口远程控制设备类操作。
2. **优先内网 + 环境变量 token**，公网场景再叠加 HTTPS / SSH 隧道。
3. **文档需明确**本地命令与远程命令的边界，以及注入路径的服务端语义。
4. 现有代理实现（`ServerProxy`）已覆盖全部设备操作，**无需为远程新增业务逻辑**，改动集中在客户端认证与模式判定，工作量小、风险低。


---

## 七、实施记录（已落地）

本方案的「必做项」已实现，主要改动：

### 7.1 `cli/server_proxy.py`

- 新增 `ProxyAuthError` 异常，区分「服务端不可达」与「可达但未授权（401/403）」。
- `_get` / `_post` / `file_upload` 三处请求统一携带 `X-Auth-Token` 头（保留 query token 作为兼容），并在收到 401/403 时抛出 `ProxyAuthError`，错误信息提示需要 `--token` / `FPB_TOKEN`。

### 7.2 `cli/fpb_cli.py`

- 新增 `--token` 选项，默认取环境变量 `FPB_TOKEN`，并透传给 `ServerProxy`。
- 新增 `_is_remote_url()`：判断 `--server-url` 是否指向非 localhost 主机。
- 新增 `_attach_proxy()`：附着到可达的 server；`--port` 可选，仅当 server 无设备时才请求其打开端口。
- 新增 `_init_remote_proxy()`：远程模式纯代理，**不自动拉起、不回退本地串口**；用 `get_status` 探测以区分不可达与未授权；远程不可达时——给了 port 则报错，没给 port 则保持离线（不影响本地 ELF 分析）。
- 模式判定整理为：direct / remote / local-with-port / offline 四类。`--direct` 与远程 URL 组合会被拒绝。
- 精简 `--help` 的 Examples，并在 `--port` 帮助里写明「仅设备相关命令需要」，避免被误读为全局必选项。

### 7.3 `--port` 是否必选？

不是。结论分三种情况：

| 场景 | 是否需要 `--port` |
|------|------------------|
| 本地分析（analyze/disasm/search/compile 等） | 不需要 |
| 远程代理，且远端 server 已连接设备 | 不需要 |
| 远程代理，但远端 server 尚未连接设备 | 需要（告诉 server 打开哪个串口） |
| 本地无运行中的 server，需自动拉起 | 需要（拉起的 server 要知道开哪个口） |

### 7.4 测试覆盖

- `tests/test_server_proxy.py`：新增 `TestServerProxyTokenTransmission`（token 头/查询透传、无 token 时不带头）与 `TestServerProxyAuthError`（401/403 → `ProxyAuthError`、`is_server_running` 吞掉鉴权错误返回 False、`file_upload` 同样抛错）。
- `tests/test_cli_coexistence.py`：新增 `TestFPBCLIIsRemoteUrl`（host 分类）、`TestFPBCLIRemoteMode`（远程纯代理、无 port 也能附着、token 透传、不可达/未授权报错、--direct 拒绝）、`TestFPBCLILocalNoPortNoServer`（本地无 port 保持离线）、`TestMainTokenArg`（`--token` 与 `FPB_TOKEN` 透传）。

全部新增用例与既有用例通过（仅一个与本改动无关的预存在用例 `test_fpb_cli_main_is_cli_main` 在基线上即失败）。
