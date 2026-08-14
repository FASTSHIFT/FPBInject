# Server / CLI 连接参数统一与最大化复用重构方案

## 0. 目标

一句话：**让 `fpbinject-server` 也能像 `fpbinject`（CLI）一样，把串口/连接参数直接暴露成命令行 flag，而不是只能塞进 `config.json`；且 CLI 与 server 两侧的参数定义"同源"，改一处即可。**

两个子目标：

1. **回收 `--port` 语义**：趁使用者还少，把 server 的 HTTP 端口 flag 改名，让 `--port` 在 server 和 CLI 两侧统一表示"串口设备"。
2. **最大化复用**：连接类参数（串口、波特率、数据位、校验、流控、DTR/RTS、传输 chunk 等）由 `config_schema.py` **单一数据源**驱动，自动生成 argparse flag，CLI 与 server 共用同一套生成器与回填逻辑。

---

## 1. 现状

### 1.1 两侧 `--port` 语义冲突

| 入口 | `--port` 含义 | 默认值 | 来源 |
|------|--------------|--------|------|
| `fpbinject-server`（`main.py`） | **HTTP 监听端口** | 5500 | `parse_args()` 手写 |
| `fpbinject`（`cli/fpb_cli.py`） | **串口设备** (`/dev/ttyACM0`) | 无 | `main()` 手写 |

### 1.2 server 启动参数（`main.py:parse_args`）

只有运维类参数，**没有任何串口/连接参数**：

```
--host  --port(HTTP)  --debug  --skip-port-check
--no-browser  --no-auth  --no-mdns  --config  --version
```

串口相关全部只能走 `config.json`（由 `AppState.load_config()` 从 schema 加载）。想指定串口启动，只能先写配置文件——就是当前"用 json 不够优雅"的痛点。

### 1.3 CLI 连接参数（`cli/fpb_cli.py`）

手写暴露：`--port/-p`(串口)、`--baudrate/-b`、`--elf`、`--compile-commands`、`--tx-chunk-size`、`--tx-chunk-delay`、`--max-retries`、`--direct`、`-s/--server`、`--server-url`(隐藏旧名)、`--no-discovery`、`--token`。

CLI 是**无 config 的瘦客户端**，参数全部来自命令行，最终写入 `DeviceState` 字段。

### 1.4 参数的真正单一数据源：`config_schema.py`

`CONFIG_SCHEMA` 已经为每个连接项定义了 key / 类型 / 默认值 / 范围 / tooltip：

- **CONNECTION 组**：`port`(串口)、`baudrate`、`auto_connect`、`data_bits`、`parity`、`stop_bits`、`flow_control`、`dtr_on_connect`、`rts_on_connect`、`vserial_enable`、`vserial_symlink`。
- **TRANSFER 组**：`upload_chunk_size`、`download_chunk_size`、`serial_tx_fragment_size`、`serial_tx_fragment_delay`、`transfer_max_retries`、`wakeup_shell_cnt`。

`DeviceState` 在 `__init__` 里正是 `for key, value in get_config_defaults(): setattr(self, key, value)` —— 已经是 schema 驱动。**argparse 是唯一还在手写、没有复用 schema 的一层。**

### 1.5 命名不一致（历史遗留）

`serial-params-refactor-proposal.md` 已把 schema 里的 chunk 参数重命名（`tx_chunk_size` → `serial_tx_fragment_size` 等），但 CLI flag 仍叫 `--tx-chunk-size`/`--tx-chunk-delay`，两侧没对齐。本次统一顺带修正。

---

## 2. 设计

### 2.1 回收 `--port`：HTTP 端口改名

| flag | 改动 | 说明 |
|------|------|------|
| `--port`（HTTP，server） | **改名 → `--http-port`**（无短选项） | server 监听端口 |
| `--port`（串口） | server **新增**、CLI **保持** | 两侧统一表示串口设备 |

- **直接改名，不设过渡期**：趁使用者还少，`--port` 在 server 上直接不再表示 HTTP 端口，不保留隐藏别名。`server_proxy.launch_server` 同步改用 `--http-port`。
- `--http-port` 不设短选项，避免与 CLI 的 `-p`（串口）混淆。
- 默认值/常量（`DEFAULT_PORT=5500`、`DEFAULT_SERVER_URL`）不变，只是"设置 HTTP 端口"的 flag 名变了。

> 为什么不让两侧都用 `--port` 表示 HTTP：CLI 的 `--port=串口` 已是既定语义且文档/示例大量使用；HTTP 端口本就该是 server 独有的运维参数。让 `--port` 全局统一为"串口"、HTTP 用显式的 `--http-port`，冲突彻底消除。

### 2.2 复用点在 schema，不在 argparse

**不共用 CLI 的整个 parser**（CLI 有 analyze/inject/... 一堆子命令和 policy，server 用不到）。复用停在"**schema → flag 生成器 + flag → DeviceState 回填器**"这一层。

新增模块 `core/arg_schema.py`（放 core，CLI 与 server 都依赖 core）：

```python
def add_connection_args(parser, *, groups=(ConfigGroup.CONNECTION,
                                           ConfigGroup.TRANSFER)):
    """按 schema 为指定组生成 argparse flag。
    key 'foo_bar' -> '--foo-bar'；短选项/别名来自 ConfigItem 扩展字段。
    默认值一律设为 None（哨兵），以便区分'用户未传'与'传了默认值'。"""

def connection_overrides(args):
    """从 parsed args 抽取用户实际传入(非 None)的连接项，
    返回 {schema_key: value}，供回填。"""

def apply_overrides(device, overrides):
    """把 overrides 写入 DeviceState（setattr）。"""
```

`ConfigItem` 扩展三个可选字段（保持单一数据源）：

```python
cli_expose: bool = True      # 是否生成 CLI/server flag
cli_short: str = ""          # 短选项，如 '-p' / '-b'
cli_aliases: tuple = ()      # 兼容旧名，如 ('--tx-chunk-size',)
```

类型映射：`NUMBER`→`int`/`float`（按默认值类型或新增 `is_float`）、`BOOLEAN`→`store_true`（或 `--flag/--no-flag`）、`STRING/PATH*`→`str`、`SELECT`→`choices=[v for v,_ in options]`；`help` 取 `tooltip`，`min/max` 写进 help 文本。

### 2.3 优先级与落盘语义

```mermaid
flowchart LR
    CLIFLAG["命令行 flag"] -->|覆盖| CFG["config.json 加载值"]
    CFG -->|覆盖| DEF["schema 默认值"]
    CLIFLAG --> RUN["本次运行生效"]
    RUN -.->|默认不写回| CFG
```

- 优先级：**命令行 flag > config.json > schema 默认**。
- flag 只影响**本次运行**，**默认不写回 config.json**（避免 `--port /dev/ttyACM0` 试一次就污染持久配置）。
- server 流程：`state.configure(resolve_config_path(...))` 先加载 config → 再 `apply_overrides(state.device, connection_overrides(args))` 覆盖。哨兵 None 保证只覆盖用户显式传的项。
- 保留 `--save-config`（可选，后续）：显式要求时才把本次 override 持久化。

### 2.4 server 与 CLI 的接入

**server（`main.py`）**：
```python
parser = argparse.ArgumentParser(prog=..., description="FPBInject Web Server")
# 运维参数：--host --http-port(-P) --debug --skip-port-check
#           --no-browser --no-auth --no-mdns --config --version
add_connection_args(parser)      # 注入 --port(串口) --baudrate ... 全套
```
启动时 `--port` 有值即等价于"配置了串口"，配合 `auto_connect`（可默认：显式给了 `--port` 就自动连）触发 `restore_state()` 里的自动连接。

**CLI（`fpb_cli.py`）**：
把手写的 `--port/-p --baudrate/-b --tx-chunk-* --max-retries` 替换为 `add_connection_args(parser, groups=(CONNECTION, TRANSFER))`；`--elf`/`--compile-commands` 若也进 schema（PROJECT 组）可一并生成，否则保留手写。CLI 特有的 `--direct -s/--server --server-url --no-discovery --token` 保持手写（非连接 schema 项）。

`FPBCLI.__init__` 的入参改为接收 `overrides` dict 或直接在 `apply_overrides` 后读 `DeviceState`，消除 `tx_chunk_size=args.tx_chunk_size` 这类逐个搬运。

### 2.5 命名统一（顺带修正）

| 旧 CLI flag | 新 flag（schema 驱动） | 兼容 |
|-------------|----------------------|------|
| `--tx-chunk-size` | `--serial-tx-fragment-size` | 旧名进 `cli_aliases`，`SUPPRESS`+WARN |
| `--tx-chunk-delay` | `--serial-tx-fragment-delay` | 同上 |
| `--max-retries` | `--transfer-max-retries` | 同上（`--max-retries` 作别名） |

---

## 3. 受影响文件

| 文件 | 改动 |
|------|------|
| `core/config_schema.py` | `ConfigItem` 增 `cli_expose/cli_short/cli_aliases`（必要时 `is_float`）；给 `port`/`baudrate` 等标短选项与别名 |
| `core/arg_schema.py`（新增） | `add_connection_args` / `connection_overrides` / `apply_overrides` |
| `main.py` | `--port`→`--http-port(-P)`（`--port` 隐藏 deprecated 别名）；`parse_args` 调 `add_connection_args`；`main()` 加载 config 后 `apply_overrides`；端口冲突提示文案改 `--http-port` |
| `cli/fpb_cli.py` | 连接类 flag 改用 `add_connection_args`；旧名做别名；`FPBCLI` 入参简化为 overrides |
| `cli/server_proxy.py` | `launch_server` 拼命令 `--port`→`--http-port` |
| `tests/test_main.py` | 新增：`--http-port`、`--port`(串口)、别名、override 优先级 |
| `tests/test_fpb_cli.py` | 更新被改的 flag 断言；旧名别名兼容测试 |
| `tests/test_server_proxy.py` | `launch_server` 命令行断言改 `--http-port` |
| `tests/test_config_schema.py` | 新字段与生成器覆盖 |

---

## 4. 实施计划

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 | `core/arg_schema.py` 生成器 + `ConfigItem` 扩展字段（`cli_expose/cli_short/cli_aliases`）；`iter_cli_items`/`connection_overrides`/`apply_overrides`/`fill_missing_defaults` | ✅ 已完成 |
| P1 | server：HTTP 端口直接改名 `--http-port`（无过渡别名）；`server_proxy.launch_server` 同步；端口冲突提示文案改 `--http-port` | ✅ 已完成 |
| P2 | server：接入 `add_connection_args` + override 回填；`--port`(串口)/`--baudrate` 等可用；显式 `--port` 隐含 auto-connect | ✅ 已完成 |
| P3 | CLI：改用生成器，旧 flag 名（`--tx-chunk-size` 等）做别名；`fill_missing_defaults` 补默认值 | ✅ 已完成 |
| P4 | 命名统一（tx-chunk → serial-tx-fragment 等）+ 单测 | ✅ 已完成 |

全程 `./format.sh --lint` + `tests/run_tests.py --coverage --target 85`。

---

## 5. 兼容性与迁移

- **破坏性**：server 的 `--port` 不再表示 HTTP 端口。隐藏别名给一个发布周期缓冲，命中时 WARN 提示改用 `--http-port`；下个大版本移除。
- **CLI 无破坏**：`--port`(串口) 语义不变；`--tx-chunk-size` 等旧名保留为别名。
- **config.json 无破坏**：schema key 不变，仅新增 argparse 覆盖层；不写回策略保证旧配置不被 flag 意外改写。
- **文档**：`CLI.md`、`WebServer.md`、`main.py` 端口冲突提示、CLI epilog 示例统一更新为 `--http-port` / 串口 `--port`。

---

## 6. 收益

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| server 指定串口启动 | 必须先写 `config.json` | `fpbinject-server --port /dev/ttyACM0 --baudrate 115200` |
| 参数定义处 | schema + CLI argparse + server argparse **三处** | schema **一处**，两侧自动生成 |
| `--port` 语义 | server=HTTP / CLI=串口，冲突 | 全局统一=串口；HTTP 用 `--http-port` |
| 新增连接参数成本 | 改 schema + 两处 argparse | 只改 schema |
| CLI/server 命名 | `--tx-chunk-size` vs `serial_tx_fragment_size` 不一致 | 完全对齐 |
