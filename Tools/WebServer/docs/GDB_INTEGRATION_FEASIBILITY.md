# GDB 集成可行性分析

## 背景

当前 Symbol Variable Viewer 功能在处理大型 ELF 文件（如 > 100 MB 的 app.elf）时存在严重性能瓶颈：

| 操作 | 耗时 | 瓶颈原因 |
|------|------|----------|
| 符号全量加载 | ~9s | pyelftools 遍历 211522 个 symtab 条目 |
| `read_symbol_value` | ~3s | 重新打开 ELF，遍历 symtab 定位符号 |
| `get_struct_layout` | ~9s | 遍历全部 DWARF CU/DIE 查找变量类型 |
| 变量展开 tab 总耗时 | ~12s | `read_symbol_value` + `get_struct_layout` 串行执行 |

核心问题：Python 侧用 pyelftools 做了大量 ELF/DWARF 解析工作，而这些正是 GDB 的强项。

## 方案概述

在 Python 侧实现一个轻量级 GDB RSP (Remote Serial Protocol) Server，将设备的 `fl read/write` 命令桥接为 GDB 可识别的内存访问接口。前端通过 `arm-none-eabi-gdb` 子进程获取符号信息、类型解析、内存格式化等能力。

```
┌─────────────┐     HTTP/JSON      ┌──────────────────┐
│   Frontend   │ ◄────────────────► │   Flask Server    │
│  (Browser)   │                    │                   │
└─────────────┘                    │  GDB Subprocess   │
                                   │  (arm-none-eabi-  │
                                   │   gdb -ex ...)    │
                                   │       │           │
                                   │       │ GDB RSP   │
                                   │       ▼           │
                                   │  GDB RSP Bridge   │
                                   │  (TCP :3333)      │
                                   │       │           │
                                   │       │ fl cmds   │
                                   │       ▼           │
                                   │  Serial Protocol  │
                                   └───────┬──────────┘
                                           │ UART
                                           ▼
                                   ┌──────────────────┐
                                   │  Device (NuttX)   │
                                   │  fl read/write    │
                                   └──────────────────┘
```

## GDB RSP 协议适配分析

### GDB RSP 最小实现集

GDB RSP 是一个简单的文本协议，包格式为 `$<data>#<checksum>`。实现一个只支持内存读写的 stub 只需处理少量包类型：

| GDB 包 | 含义 | fl 命令映射 | 必要性 |
|---------|------|-------------|--------|
| `m addr,length` | 读内存 | `fl -c read --addr <addr> --len <len>` | ✅ 必须 |
| `M addr,length:XX..` | 写内存 | `fl -c write --addr <addr> --data <b64> --crc <crc>` | ✅ 必须 |
| `g` | 读所有寄存器 | 返回全零伪数据 | ✅ 必须（GDB 连接握手需要） |
| `G XX..` | 写所有寄存器 | 返回 OK（忽略） | ⚠️ 可选 |
| `?` | 查询停止原因 | 返回 `S05`（SIGTRAP） | ✅ 必须（连接握手） |
| `qSupported` | 能力协商 | 返回 `PacketSize=4096` | ✅ 必须 |
| `qAttached` | 查询附加状态 | 返回 `1` | ✅ 必须 |
| `Hg0` / `Hc0` | 设置线程 | 返回 OK | ✅ 必须 |
| `c` / `s` | 继续/单步 | 不支持，返回 `S05` | ⚠️ 伪实现 |
| `k` | 断开 | 关闭连接 | ✅ 必须 |

核心实现量约 200-300 行 Python 代码。

### 已具备的能力

| 能力 | 现状 | GDB RSP 对应 |
|------|------|-------------|
| 任意地址内存读 | `fl -c read` | `m` 包 ✅ |
| 任意地址内存写 | `fl -c write` | `M` 包 ✅ |
| 串口双向通信 | serial_protocol.py | 传输层 ✅ |
| Base64 + CRC 校验 | 已实现 | 数据完整性 ✅ |
| ELF 符号解析 | pyelftools | GDB 原生支持 ✅ |
| Toolchain 路径 | 已配置 | `arm-none-eabi-gdb` 可用 ✅ |

### 不支持的能力（无需实现）

| 能力 | 原因 | 影响 |
|------|------|------|
| CPU 寄存器读写 | fl 协议无此命令，需固件改动 | GDB 连接时返回伪数据即可 |
| 断点/单步 | 需要 halt/resume 机制 | 不影响变量查看场景 |
| 程序暂停/继续 | 设备持续运行，不可中断 | 伪实现即可 |

## 性能收益分析

### 当前瓶颈 vs GDB 方案

| 操作 | 当前方案 | GDB 方案 | 预期提升 |
|------|----------|----------|----------|
| 符号查找 | pyelftools 遍历 symtab (~3s) | GDB 内置索引 (~0.01s) | **~300x** |
| 类型/结构体解析 | pyelftools 遍历 DWARF CU (~9s) | GDB `ptype` 命令 (~0.05s) | **~180x** |
| 变量值读取 | Python base64 解码 + 手动格式化 | GDB `x` / `print` 命令直接格式化 | 减少 Python 代码量 |
| 内存读写 | fl read/write (不变) | fl read/write (不变) | 无变化 |
| 首次连接 | 无额外开销 | GDB 加载 ELF + 建立索引 (~2-5s) | 一次性开销 |

关键收益：GDB 在加载 ELF 时会建立符号索引和 DWARF 加速结构，后续查询几乎是 O(1)。而 pyelftools 每次都是线性遍历。

### 可消除的 Python 代码

| 模块 | 行数 | 可替代程度 |
|------|------|-----------|
| `get_symbols()` | ~80 行 | 部分替代（GDB `info variables` / `info functions`） |
| `search_symbols()` | ~80 行 | 完全替代（GDB `info functions <regex>`） |
| `lookup_symbol()` | ~40 行 | 完全替代（GDB `info symbol <addr>`） |
| `read_symbol_value()` | ~30 行 | 完全替代（GDB `x/<n>bx <addr>`） |
| `get_struct_layout()` | ~100 行 | 完全替代（GDB `ptype <sym>`） |
| `_resolve_type_die()` | ~40 行 | 完全替代 |
| `_parse_struct_members()` | ~40 行 | 完全替代 |
| `_get_type_name()` | ~50 行 | 完全替代 |
| **合计** | **~460 行** | DWARF 解析全部可移除 |

## 实现方案

### Phase 1: GDB RSP Bridge（核心）

新增 `core/gdb_bridge.py`，实现最小 GDB RSP server：

```python
class GDBRSPBridge:
    """Bridges GDB RSP protocol to fl serial commands."""

    def __init__(self, serial_protocol, listen_port=3333):
        self.protocol = serial_protocol
        self.port = listen_port
        self.server = None

    def start(self):
        """Start TCP server for GDB connection."""
        # 监听 localhost:3333

    def handle_packet(self, packet):
        """Route GDB RSP packet to appropriate handler."""
        if packet.startswith('m'):      # 读内存
            return self._handle_read_memory(packet)
        elif packet.startswith('M'):    # 写内存
            return self._handle_write_memory(packet)
        elif packet == 'g':             # 读寄存器（伪实现）
            return '0' * (16 * 8)       # 16 个 ARM 寄存器，全零
        elif packet == '?':             # 停止原因
            return 'S05'
        # ...

    def _handle_read_memory(self, packet):
        """m addr,length -> hex bytes"""
        addr, length = parse_m_packet(packet)
        data, msg = self.protocol.read_memory(addr, length)
        return data.hex() if data else 'E01'
```

### Phase 2: GDB 子进程管理

新增 `core/gdb_session.py`，管理 GDB 子进程生命周期：

```python
class GDBSession:
    """Manages arm-none-eabi-gdb subprocess."""

    def __init__(self, elf_path, gdb_path, target_port=3333):
        self.proc = None

    def start(self):
        """Launch GDB, load ELF, connect to RSP bridge."""
        self.proc = subprocess.Popen(
            [self.gdb_path, '-batch-silent', '-ex', f'file {elf_path}',
             '-ex', f'target remote :{self.port}'],
            stdin=PIPE, stdout=PIPE, stderr=PIPE
        )

    def execute(self, cmd):
        """Execute a GDB command and return output."""
        # 通过 GDB/MI 或 -ex 执行命令

    def get_symbol_type(self, sym_name):
        """Get symbol type info via 'ptype'."""
        return self.execute(f'ptype {sym_name}')

    def read_variable(self, sym_name):
        """Read variable value via 'print'."""
        return self.execute(f'print /x {sym_name}')

    def search_symbols(self, pattern):
        """Search symbols via 'info functions/variables'."""
        return self.execute(f'info variables {pattern}')
```

### Phase 3: 路由层适配

修改 `app/routes/symbols.py`，优先使用 GDB session：

```python
@bp.route("/symbols/value", methods=["GET"])
def api_get_symbol_value():
    gdb = state.gdb_session
    if gdb and gdb.is_alive():
        # 快速路径：GDB 直接返回格式化数据
        result = gdb.read_variable(sym_name)
        struct_info = gdb.get_symbol_type(sym_name)
        return jsonify({"success": True, ...})
    else:
        # 回退路径：原有 pyelftools 逻辑
        ...
```

## 风险与挑战

### 技术风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| GDB 连接到"运行中"的目标 | 中 | RSP stub 始终返回 `S05`（已停止），GDB 不会尝试 resume |
| GDB 子进程管理复杂度 | 中 | 使用 GDB/MI 协议，有成熟的 Python 库（pygdbmi） |
| 串口通道竞争 | 高 | GDB RSP bridge 复用现有 `_run_serial_op()` worker 线程调度 |
| GDB 启动加载 ELF 耗时 | 低 | 一次性开销 2-5s，后续查询毫秒级；可后台预加载 |
| 跨平台 GDB 可用性 | 低 | toolchain 已包含 `arm-none-eabi-gdb` |

### 串口通道竞争（最大挑战）

当前串口被 fl 协议独占，GDB RSP bridge 的内存读写也需要走串口。解决方案：

**方案 A：复用现有 worker 线程（推荐）**
- GDB RSP bridge 收到 `m` 包时，通过 `_run_serial_op()` 调度到 fpb-worker 线程
- 与现有 read/write 路由共享同一调度机制
- 无需修改固件

**方案 B：双通道（需固件支持）**
- 设备开放第二个串口/USB CDC 端口专用于 GDB
- 完全隔离，无竞争
- 需要固件改动

## 替代方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A: GDB RSP Bridge（本方案）** | 利用 GDB 强大的符号/类型解析；消除 DWARF 解析代码；前端可展示 GDB 格式化数据 | 需要管理 GDB 子进程；串口竞争需要调度 |
| **B: 优化 pyelftools** | 无新依赖；改动小 | DWARF 遍历本质上慢；代码复杂度持续增长 |
| **C: 预构建符号索引** | 离线处理，运行时快 | 需要额外构建步骤；ELF 变化时需重建 |
| **D: 使用 llvm-dwarfdump** | 比 pyelftools 快 | 仍是外部进程；输出解析复杂 |

## 结论

GDB RSP Bridge 方案技术上可行，核心实现量约 300-500 行 Python 代码。最大收益是将 DWARF 类型解析从 ~9s 降到 ~0.05s，同时消除约 460 行 pyelftools DWARF 解析代码。

**建议分阶段推进**：
1. 先实现 Phase 1 (RSP Bridge) + Phase 2 (GDB Session)，验证端到端可行性
2. 确认性能收益后，逐步将 `/symbols/value`、`/symbols/search` 等路由迁移到 GDB 路径
3. 保留 pyelftools 作为 fallback（GDB 不可用时）

**预估工作量**：3-5 天（Phase 1-2），额外 2-3 天（Phase 3 路由迁移 + 测试）。
