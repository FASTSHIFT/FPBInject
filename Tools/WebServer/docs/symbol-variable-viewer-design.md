# Symbol Variable Viewer 方案评估报告

> 日期: 2026-03-06
> 状态: Draft
> 关联: `symbols.js`, `elf_utils.py`, `fl.c`, `serial_protocol.py`

## 1. 需求概述

当前符号搜索功能只返回 `name + addr`，不区分函数和变量。需要改造为：

| 符号类型 | 交互行为 |
|---------|---------|
| 函数 (Function) | 保持现状：单击→反汇编，双击→创建补丁 |
| 不可变变量 (Const) | 新标签页展示从 ELF 文件读出的值（编译时常量） |
| 可变变量 (Variable) | 新标签页展示从设备内存读出的实时值，支持刷新读取和写入 |

## 2. 现状分析

### 2.1 符号类型信息被丢弃

`elf_utils.py` 调用 `arm-none-eabi-nm` 解析符号，`nm` 输出格式为 `addr type name`，其中 type 列含义：

| nm 类型 | 含义 | 分类 |
|---------|------|------|
| `T` / `t` | .text（代码段） | 函数 |
| `D` / `d` | .data（已初始化数据） | 可变变量 |
| `B` / `b` | .bss（未初始化数据） | 可变变量 |
| `R` / `r` | .rodata（只读数据） | 不可变变量 |
| `W` / `w` | Weak symbol | 按所在段判断 |
| `A` | Absolute | 忽略 |
| `U` | Undefined | 忽略 |

当前代码 `parts[1]`（类型列）被完全忽略，`get_symbols()` 返回 `Dict[str, int]`（name→addr）。

### 2.2 无 ELF Section 读取能力

- 不使用 `pyelftools`，完全依赖命令行工具（`nm`、`objdump`、`readelf`、`strings`）
- 无法从 ELF 的 `.rodata` / `.data` section 读取常量初始值
- 无法获取变量大小（需要 DWARF 或 `nm --print-size`）
- DWARF 解析仅在 `get_signature()` 中用 `readelf --debug-dump=info` 做文本匹配，无法获取结构体布局
- 引入 `pyelftools` 可一次性解决上述所有问题，且降低对 toolchain 命令行工具的依赖

### 2.3 固件无内存读写命令

现有固件命令中：
- **写内存**：只能通过 `alloc` + `upload` 写入动态分配的缓冲区，不支持写任意地址
- **读内存**：完全不支持，没有 `read` / `peek` / `dump` 命令

现有分块传输机制可复用：
- `chunk_size` 配置项（默认 128，范围 16-1024）已用于 `upload` 和文件传输
- 吞吐量测试 `test_serial_throughput` 会推荐最佳 chunk_size
- 新增的 read/write 命令应复用此分块机制，无需单独设计传输协议

### 2.4 前端符号列表无类型区分

- 所有符号统一使用 `codicon-symbol-method` 图标
- 单击/双击行为不区分符号类型

## 3. 改造方案

### 3.1 后端：引入 pyelftools 统一 ELF 解析

**改动文件**: `core/elf_utils.py`

**新增依赖**: `pip install pyelftools`

**核心思路**: 用 `pyelftools` 替代 `nm` 解析符号表，一次加载 ELF 即可获取符号名、地址、大小、类型、所在 section，同时为后续 DWARF 结构体解析打下基础。

```python
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

def get_symbols(elf_path, toolchain_path=None) -> Dict[str, dict]:
    with open(elf_path, 'rb') as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name('.symtab')
        result = {}
        for sym in symtab.iter_symbols():
            if sym['st_shndx'] == 'SHN_UNDEF' or sym['st_size'] == 0:
                continue
            section = elf.get_section(sym['st_shndx'])
            result[sym.name] = {
                'addr': sym['st_value'],
                'size': sym['st_size'],
                'sym_type': sym['st_info']['type'],  # STT_FUNC / STT_OBJECT
                'section': section.name if section else '',
            }
    return result
```

**类型映射**（基于 ELF symbol type + section name）：

| `st_info.type` | section | 分类 |
|----------------|---------|------|
| `STT_FUNC` | `.text` | `function` |
| `STT_OBJECT` | `.data` / `.bss` | `variable`（可变） |
| `STT_OBJECT` | `.rodata` | `const`（不可变） |

**对比 nm 方案的优势**：
- 不依赖 toolchain 路径和 `arm-none-eabi-nm` 可执行文件
- 直接获取 `st_size`，无需 `--print-size` 选项
- 直接获取 section 名，无需从 type letter 推断
- 为 3.2 节的 section 数据读取和 DWARF 解析复用同一个 ELF 文件句柄

**保留 CLI 工具的场景**：`disassemble_function` 和 `decompile_function` 仍使用 `objdump` 和 Ghidra，因为 pyelftools 不提供反汇编能力。

**影响范围**: `get_symbols()` 返回值从 `Dict[str, int]` 变为 `Dict[str, dict]`，需同步修改：
- `routes/symbols.py` — 搜索/列表 API 返回新字段（地址从 `symbols[name]` 改为 `symbols[name]['addr']`）
- `core/elf_utils.py` — 反汇编/签名查找等引用 symbols 的地方
- 前端 `symbols.js` — 渲染和交互逻辑
- 所有相关测试

### 3.2 后端：从 ELF 读取数据 + DWARF 结构体解析

**改动文件**: `core/elf_utils.py`（新增函数）

#### 3.2.1 读取 section 数据

复用 3.1 已有的 `pyelftools`，直接从 section 中按偏移读取二进制数据：

```python
def read_symbol_value(elf_path: str, sym_name: str) -> Optional[bytes]:
    """从 ELF 的 section 中读取符号对应的原始字节。"""
    with open(elf_path, 'rb') as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name('.symtab')
        for sym in symtab.iter_symbols():
            if sym.name == sym_name and sym['st_size'] > 0:
                section = elf.get_section(sym['st_shndx'])
                offset = sym['st_value'] - section['sh_addr']
                return section.data()[offset:offset + sym['st_size']]
    return None
```

注意：`.bss` 段无初始值（全零），`read_symbol_value` 对 `.bss` 符号返回 `None`，前端需提示"需从设备读取"。

#### 3.2.2 DWARF 结构体布局解析

使用 `pyelftools` 的 DWARF 解析能力，从 `DW_TAG_variable` → `DW_AT_type` 链追踪到 `DW_TAG_structure_type`，提取成员布局：

```python
def get_struct_layout(elf_path: str, sym_name: str) -> Optional[List[dict]]:
    """解析符号的 DWARF 类型信息，返回结构体成员列表。"""
    with open(elf_path, 'rb') as f:
        elf = ELFFile(f)
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag == 'DW_TAG_variable':
                    name = die.attributes.get('DW_AT_name')
                    if name and name.value.decode() == sym_name:
                        type_die = _resolve_type(dwarf, die)
                        if type_die and type_die.tag == 'DW_TAG_structure_type':
                            return _parse_struct_members(type_die)
    return None  # 非结构体或无 DWARF 信息

def _parse_struct_members(struct_die) -> List[dict]:
    """递归解析结构体成员。"""
    members = []
    for child in struct_die.iter_children():
        if child.tag == 'DW_TAG_member':
            members.append({
                'name': child.attributes['DW_AT_name'].value.decode(),
                'offset': child.attributes['DW_AT_data_member_location'].value,
                'size': _get_type_size(child),
                'type_name': _get_type_name(child),
            })
    return members
```

返回示例：
```json
[
  {"name": "x",      "offset": 0,  "size": 4, "type_name": "int32_t"},
  {"name": "y",      "offset": 4,  "size": 4, "type_name": "int32_t"},
  {"name": "flags",  "offset": 8,  "size": 1, "type_name": "uint8_t"},
  {"name": "name",   "offset": 12, "size": 16, "type_name": "char[16]"}
]
```

**前提条件**: ELF 必须包含 DWARF 调试信息（编译时 `-g`）。若无 DWARF，`get_struct_layout` 返回 `None`，前端回退到纯 hex dump 显示。

#### 3.2.3 新增 API

`GET /api/symbols/value?name=<sym>`

返回：
```json
{
  "success": true,
  "name": "my_config",
  "addr": "0x08010000",
  "size": 28,
  "type": "const",
  "section": ".rodata",
  "hex_data": "0100000002000000030000004865...",
  "struct_layout": [
    {"name": "x", "offset": 0, "size": 4, "type_name": "int32_t"},
    {"name": "y", "offset": 4, "size": 4, "type_name": "int32_t"}
  ]
}
```

`struct_layout` 为 `null` 时表示非结构体或无 DWARF 信息，前端回退到纯 hex dump。

### 3.3 固件：新增内存读写命令

**改动文件**: `App/func_loader/fl.c`

#### 3.3.1 `read` 命令 — 读取任意地址内存（单 chunk）

```
fl -c read --addr 0x20000000 --len 128
```

响应格式（复用 `upload` 的 base64 + CRC 模式）：

```
[FLOK] READ 128 bytes crc=0x1234 data=<base64>
```

实现要点：
- 参数：`--addr`（必需）、`--len`（可选，默认为 `chunk_size`，上限 1024）
- 单次只读一个 chunk，大变量由 Python 层循环分块读取
- 直接 `memcpy` 从目标地址读取到临时 buffer → base64 编码 → CRC-16 校验
- 地址保护：可选用 `setjmp`/`longjmp` 捕获 HardFault，或信任用户输入

#### 3.3.2 `write` 命令 — 写入任意地址内存（单 chunk）

```
fl -c write --addr 0x20000000 --data <base64> --crc 0x1234
```

响应格式：

```
[FLOK] WRITE 128 bytes to 0x20000000
```

实现要点：
- 参数：`--addr`（必需）、`--data`（必需，base64）、`--crc`（可选）
- 单次只写一个 chunk，大变量由 Python 层循环分块写入
- 复用 `upload` 的 base64 解码 + CRC 校验逻辑
- CRC 通过后 `memcpy` 到目标地址 → `flush_dcache_cb`
- **安全考虑**：Flash 地址不可写，固件侧检查地址范围，非 RAM 区域拒绝并返回错误

#### 3.3.3 与现有命令的关系

| 命令 | 用途 | 地址来源 | 分块 |
|------|------|---------|------|
| `upload` | 写入 `alloc` 分配的缓冲区 | `last_alloc + offset` | Python 层按 `chunk_size` 分块 |
| `write` (新) | 写入任意 RAM 地址 | 用户指定 `--addr` | Python 层按 `chunk_size` 分块 |
| `read` (新) | 读取任意地址内存 | 用户指定 `--addr` | Python 层按 `chunk_size` 分块 |

三个命令共享同一个 `chunk_size` 配置，由吞吐量测试自动推荐最佳值。

### 3.4 后端：Python 协议层

**改动文件**: `core/serial_protocol.py`

新增两个方法，复用 `self.device.chunk_size` 进行分块传输：

```python
def read_memory(self, addr: int, length: int) -> Tuple[Optional[bytes], str]:
    """分块读取设备内存，复用 chunk_size 配置。"""
    chunk = self.device.chunk_size or 128
    buf = bytearray()
    offset = 0
    while offset < length:
        n = min(chunk, length - offset)
        cmd = f"-c read --addr 0x{addr + offset:X} --len {n}"
        resp = self.send_cmd(cmd, timeout=2.0)
        # 解析 base64 + CRC 校验
        data = self._parse_read_response(resp)
        if data is None:
            return None, f"Read failed at offset {offset}"
        buf.extend(data)
        offset += n
    return bytes(buf), f"Read {length} bytes OK"

def write_memory(self, addr: int, data: bytes) -> Tuple[bool, str]:
    """分块写入设备内存，复用 chunk_size 配置。"""
    chunk = self.device.chunk_size or 128
    offset = 0
    while offset < len(data):
        piece = data[offset:offset + chunk]
        b64 = base64.b64encode(piece).decode("ascii")
        crc = crc16(piece)
        cmd = f"-c write --addr 0x{addr + offset:X} --data {b64} --crc 0x{crc:04X}"
        resp = self.send_cmd(cmd, timeout=2.0)
        if not self._check_ok(resp):
            return False, f"Write failed at offset {offset}"
        offset += len(piece)
    return True, f"Write {len(data)} bytes OK"
```

与 `upload` 方法的分块模式完全一致，共享同一个 `chunk_size` 配置。

**新增 API 路由**:

| 路由 | 方法 | 功能 |
|------|------|------|
| `POST /api/memory/read` | POST | 从设备读取内存 |
| `POST /api/memory/write` | POST | 向设备写入内存 |

### 3.5 前端：符号列表改造

**改动文件**: `static/js/features/symbols.js`

#### 图标区分

| 类型 | 图标 | 颜色 |
|------|------|------|
| function | `codicon-symbol-method` | 默认 |
| variable | `codicon-symbol-variable` | `var(--vscode-symbolIcon-variableForeground)` |
| const | `codicon-symbol-constant` | `var(--vscode-symbolIcon-constantForeground)` |

#### 交互行为

| 类型 | 单击 | 双击 |
|------|------|------|
| function | 反汇编（现状） | 创建补丁（现状） |
| const | 打开 ELF 值查看 tab | 同单击 |
| variable | 打开设备内存查看 tab | 同单击 |

### 3.6 前端：变量查看器 Tab

**改动文件**: `static/js/features/editor.js`（新增 tab 类型）

#### 3.6.1 Const 查看器（只读）

新 tab 类型 `const-viewer`，内容布局：

**有结构体信息时（DWARF 可用）**：

```
┌─────────────────────────────────────────────────────────┐
│ 📌 my_config                                            │
│ Address: 0x08010000  Size: 28 bytes                     │
│ Section: .rodata (Read-Only)                            │
├──────────┬──────────┬──────────┬────────────────────────┤
│ Field    │ Type     │ Offset   │ Value                  │
├──────────┼──────────┼──────────┼────────────────────────┤
│ x        │ int32_t  │ +0       │ 1        (0x00000001)  │
│ y        │ int32_t  │ +4       │ 2        (0x00000002)  │
│ flags    │ uint8_t  │ +8       │ 3        (0x03)        │
│ name     │ char[16] │ +12      │ "Hello"  (48 65 6C..)  │
├──────────┴──────────┴──────────┴────────────────────────┤
│ Raw (copyable):                                         │
│ 01000000 02000000 03000000 48656C6C 6F000000...         │
└─────────────────────────────────────────────────────────┘
```

**无结构体信息时（回退 hex dump）**：

```
┌─────────────────────────────────────────┐
│ 📌 my_const_value                       │
│ Address: 0x08010100  Size: 64 bytes     │
│ Section: .rodata (Read-Only)            │
├─────────────────────────────────────────┤
│ Hex View:                               │
│ 0x00: 01 00 00 00 48 65 6C 6C  ....Hell │
│ 0x08: 6F 20 57 6F 72 6C 64 00  o World. │
│ ...                                     │
├─────────────────────────────────────────┤
│ Raw (copyable):                         │
│ 01000000 48656C6C 6F20576F 726C6400     │
└─────────────────────────────────────────┘
```

- 数据来源：`GET /api/symbols/value?name=<sym>`（从 ELF 文件读取）
- 若 `struct_layout` 非空 → 渲染结构体表格，每个字段按 `type_name` 解析值
- 若 `struct_layout` 为空 → 回退到 hex dump + ASCII 预览
- 只读，无刷新/写入按钮

#### 3.6.2 Variable 查看器（可读写）

新 tab 类型 `var-viewer`，内容布局：

**有结构体信息时**：

```
┌─────────────────────────────────────────────────────────┐
│ 📊 g_device_state                                       │
│ Address: 0x20000100  Size: 32 bytes                     │
│ Section: .data (Read-Write)                             │
├─────────────────────────────────────────────────────────┤
│ [🔄 Read from Device]  [💾 Write to Device]            │
├──────────┬──────────┬──────────┬────────────────────────┤
│ Field    │ Type     │ Offset   │ Value (editable)       │
├──────────┼──────────┼──────────┼────────────────────────┤
│ x        │ int32_t  │ +0       │ [1          ]          │
│ y        │ int32_t  │ +4       │ [255        ]          │
│ flags    │ uint8_t  │ +8       │ [0          ]          │
│ name     │ char[16] │ +12      │ [Hello      ]          │
├──────────┴──────────┴──────────┴────────────────────────┤
│ Raw Hex (editable):                                     │
│ [01000000] [FF000000] [00000000] [48656C6C 6F00...]     │
├─────────────────────────────────────────────────────────┤
│ Status: Last read at 14:32:05                           │
└─────────────────────────────────────────────────────────┘
```

**无结构体信息时**：

```
┌─────────────────────────────────────────┐
│ 📊 g_counter                            │
│ Address: 0x20000200  Size: 4 bytes      │
│ Section: .bss (Read-Write, no init)     │
├─────────────────────────────────────────┤
│ [🔄 Read from Device]  [💾 Write]      │
├─────────────────────────────────────────┤
│ Hex Editor:                             │
│ 0x00: [01] [00] [00] [00]  ....        │
├─────────────────────────────────────────┤
│ Status: Last read at 14:32:05           │
└─────────────────────────────────────────┘
```

- **Read 按钮**：`POST /api/memory/read` → 分块读取 → 刷新显示
- **Write 按钮**：收集编辑后的值 → `POST /api/memory/write` → 分块写入设备
- 结构体模式下：字段值输入框按 `type_name` 提供合适的输入控件（整数用 number input，字符串用 text input，hex 用 monospace input）
- 编辑字段值时自动同步更新底部 Raw Hex；编辑 Raw Hex 时自动同步更新字段值
- `.bss` 变量首次打开时无 ELF 初始值，自动触发一次 Read from Device
- 按钮样式复用 `editorToolbar` 中 Inject 按钮的 `.vscode-button` 样式

## 4. 工作量评估

### Phase 1：pyelftools 引入 + 符号类型识别（基础）

| 任务 | 文件 | 预估 |
|------|------|------|
| 引入 `pyelftools` 依赖 | `requirements.txt` | 0.1h |
| 用 pyelftools 重写 `get_symbols()` | `elf_utils.py` | 1h |
| 新增 `read_symbol_value()` | `elf_utils.py` | 0.5h |
| 新增 `get_struct_layout()` + DWARF 解析 | `elf_utils.py` | 2h |
| 搜索 API 返回 type/size/section 字段 | `routes/symbols.py` | 0.5h |
| 新增 `/api/symbols/value` 路由 | `routes/symbols.py` | 0.5h |
| 前端符号列表显示类型图标 + 分发交互 | `symbols.js` | 1h |
| 适配所有 `symbols[name]` → `symbols[name]['addr']` | 多文件 | 0.5h |
| 更新测试 | 各测试文件 | 1.5h |

**小计: ~7.5h**

### Phase 2：Const 查看器 + 结构体渲染

| 任务 | 文件 | 预估 |
|------|------|------|
| Const 查看器 tab 渲染（结构体表格 + hex dump 双模式） | `editor.js` | 2h |
| 结构体字段值解析（按 type_name 解码 bytes → 显示值） | `editor.js` | 1.5h |
| CSS 样式（表格、hex dump） | `style.css` | 0.5h |
| i18n 翻译键 | 3 个 locale 文件 | 0.3h |
| 测试 | 各测试文件 | 1h |

**小计: ~5.3h**

### Phase 3：固件 read/write 命令 + 分块传输

| 任务 | 文件 | 预估 |
|------|------|------|
| 固件 `cmd_read` 实现（单 chunk） | `fl.c` | 1h |
| 固件 `cmd_write` 实现（单 chunk） | `fl.c` | 1h |
| Python `read_memory` / `write_memory`（分块循环，复用 chunk_size） | `serial_protocol.py` | 1h |
| 新增 `/api/memory/read` 和 `/api/memory/write` 路由 | `routes/` (新文件) | 0.5h |
| 固件单元测试 | `test_fl.c` | 1h |
| Python 路由测试 | `test_*_routes.py` | 1h |

**小计: ~5.5h**

### Phase 4：Variable 查看器 + 结构体编辑

| 任务 | 文件 | 预估 |
|------|------|------|
| Variable 查看器 tab 渲染（结构体表格 + hex 双模式） | `editor.js` | 2h |
| 结构体字段可编辑控件（number/text/hex input） | `editor.js` | 2h |
| 字段值 ↔ Raw Hex 双向同步 | `editor.js` | 1h |
| Read/Write 按钮交互（分块传输进度） | `editor.js` | 1h |
| `.bss` 变量自动触发首次 Read | `editor.js` | 0.3h |
| i18n 翻译键 | 3 个 locale 文件 | 0.3h |
| 前端测试 | `test_editor.js` 等 | 1.5h |

**小计: ~8.1h**

### 总计: ~26.4h

## 5. 风险与约束

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| ELF 无 DWARF 信息 | 无法解析结构体布局，只能 hex dump | `get_struct_layout` 返回 `None` 时前端自动回退到 hex dump 模式，功能不受阻 |
| DWARF 类型链复杂 | `typedef` → `const` → `struct` 多层间接引用 | `_resolve_type` 递归追踪 `DW_AT_type` 直到终端类型，设置最大深度防止死循环 |
| 变量大小未知 | `st_size == 0` 的符号无法确定读取长度 | 过滤掉 `st_size == 0` 的符号；或提示用户手动输入长度 |
| 非法地址读取导致 HardFault | 设备崩溃 | 固件侧可用 `setjmp`/`longjmp` 保护；或限制地址范围为 RAM 区域 |
| Flash 地址不可写 | `write` 命令失败或 HardFault | 固件侧检查地址范围，非 RAM 区域拒绝写入并返回错误 |
| `get_symbols()` 返回值结构变化 | 大量调用方需要适配 | 可做兼容层：`symbols[name]` 仍可用，内部 fallback 到 `symbols[name]['addr']` |
| 大变量分块传输慢 | 串口带宽有限，大数组读取耗时 | 复用 `chunk_size` 分块 + 前端显示传输进度条 |
| pyelftools 新增依赖 | 部署环境需安装 | 纯 Python 包，无 C 扩展，`pip install` 即可，兼容性好 |
| 结构体字段值 ↔ hex 双向同步 | 编辑一侧需实时更新另一侧，逻辑复杂 | 以 hex bytes 为 single source of truth，字段值只是 view 层的解码/编码 |

## 6. 未来扩展（不在本期范围）

- **嵌套结构体展开**：递归解析 `DW_TAG_structure_type` 内嵌的子结构体，树形展示
- **联合体 (union) 支持**：解析 `DW_TAG_union_type`，多种解读并列显示
- **枚举值映射**：解析 `DW_TAG_enumeration_type`，将整数值映射为枚举名
- **变量监视列表 (Watch)**：类似 IDE 的 Watch 窗口，定时轮询多个变量
- **断点式内存快照**：结合 FPB 注入，在函数入口/出口自动 dump 指定变量
- **内存对比 (Diff)**：对比 ELF 初始值和设备当前值，高亮差异
- **用 pyelftools 替代更多 CLI 调用**：`get_signature` 中的 `readelf --debug-dump` 可改用 DWARF DIE 直接解析

## 7. 建议实施顺序

```
Phase 1 (pyelftools + 符号类型 + DWARF 解析) → Phase 2 (Const 查看器) + Phase 3 (固件命令) 并行 → Phase 4 (Variable 查看器)
```

理由：Phase 1 将 pyelftools 引入并完成符号类型识别 + DWARF 结构体解析，是所有后续阶段的基础。Phase 2（Const 查看器）只依赖 ELF 解析，Phase 3（固件 read/write）只涉及固件和协议层，两者无依赖关系可并行开发。Phase 4 同时依赖 Phase 1 的结构体渲染能力和 Phase 3 的设备读写能力，必须最后实施。
