# Watch Expression 设计方案

## 1. 目标

实现类似 VSCode Debug Watch 窗口的能力：用户输入任意表达式，系统从设备内存读取数据并按指定类型解析显示。

### 典型用例

```
*(struct uart_config *)0x20001000        → 展开结构体所有字段
*(uint32_t *)0x40021000                  → 读外设寄存器
((float *)0x20002000)[0:10]              → 读 float 数组前 10 个元素
*g_list_head                             → 解引用指针变量
(enum state_t)g_current_state            → 按枚举类型显示
*(const char *)g_version_str             → 读字符串指针
```

## 2. 现状

### 已有能力

| 组件 | 能力 | 限制 |
|------|------|------|
| GDB Session | `execute(cmd)` 可执行任意 GDB CLI | 只连接了 ELF，未连接真实设备 |
| GDB Session | `ptype /o` 解析结构体布局 | 需要符号名或类型名 |
| GDB Session | `whatis` 获取表达式类型 | — |
| GDB Session | `print sizeof(expr)` 获取大小 | — |
| Serial Protocol | `read_memory(addr, size)` 从设备读取 | 需要明确的地址和长度 |
| 前端 | `_decodeFieldValue()` 解码 int/float/char/double | 需要 hex_data + type_name |
| 前端 | struct table 渲染 | 需要 struct_layout 数组 |

### 关键洞察

GDB 加载了 ELF 的完整 DWARF 调试信息，可以解析任意 C/C++ 类型表达式。但 GDB 连接的是 RSP Bridge（用于符号查询），不是真实设备。真实设备数据通过串口协议读取。

因此方案是：**GDB 负责类型解析（地址、大小、布局），串口负责数据读取，前端负责渲染。**

## 3. 架构

```
用户输入表达式: *(struct uart_config *)0x20001000
                          │
                          ▼
              ┌─────────────────────┐
              │  POST /api/watch    │
              │  { expr: "..." }    │
              └────────┬────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ 1. GDB   │ │ 2. GDB   │ │ 3. GDB   │
    │ whatis   │ │ sizeof   │ │ ptype /o  │
    │ → 类型   │ │ → 大小   │ │ → 布局   │
    └──────────┘ └──────────┘ └──────────┘
          │            │            │
          ▼            ▼            ▼
    type_name      size         struct_layout
          │            │
          ▼            ▼
    ┌──────────────────────┐
    │ 4. 计算目标地址       │
    │    GDB: print &(expr)│
    │    或用户直接给地址   │
    └──────────┬───────────┘
               │
               ▼  addr + size
    ┌──────────────────────┐
    │ 5. Serial read_memory│
    │    从设备读取 raw hex │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ 6. 返回前端          │
    │ { addr, size, type,  │
    │   hex_data, layout } │
    └──────────────────────┘
```

## 4. 表达式分类与解析策略

### 4.1 分类

| 类别 | 示例 | 地址来源 | 类型来源 |
|------|------|----------|----------|
| A. 符号名 | `g_config` | GDB `info address` | GDB `whatis` |
| B. 解引用 | `*g_ptr` | 从设备读指针值 | GDB `whatis *g_ptr` |
| C. 强转地址 | `*(type *)0xADDR` | 表达式中的地址字面量 | 表达式中的类型 |
| D. 数组切片 | `((int *)0xADDR)[0:N]` | 地址字面量 | 元素类型 + 数量 |
| E. 成员访问 | `g_config.baud` | 基地址 + 成员偏移 | GDB `whatis` |
| F. 枚举强转 | `(enum state_t)val` | 同 val 的地址 | 枚举类型 |

### 4.2 后端解析流程

```python
def evaluate_watch_expr(expr: str) -> dict:
    """
    统一入口：解析表达式，返回 {addr, size, type_name, struct_layout}。
    不读取设备数据（读取由调用方决定）。
    """

    # Step 1: 用 GDB 获取表达式的类型
    type_name = gdb.execute(f"whatis {expr}")
    # 解析 "type = struct uart_config *" → "struct uart_config *"

    # Step 2: 获取大小
    size = gdb.execute(f"print sizeof({expr})")

    # Step 3: 计算目标地址
    addr = _resolve_expr_addr(expr, type_name)

    # Step 4: 如果是指针解引用，调整 addr/size/type
    if type_name 是指针类型:
        # 需要从设备读取指针值
        ptr_val = serial.read_memory(addr, 4)  # ARM 32-bit
        addr = int.from_bytes(ptr_val, 'little')
        type_name = 去掉一层 '*'
        size = gdb.execute(f"print sizeof({deref_type})")

    # Step 5: 如果是 struct/class/union，获取布局
    struct_layout = None
    if is_aggregate_type(type_name):
        struct_layout = gdb.execute(f"ptype /o {type_name}")

    return {addr, size, type_name, struct_layout}
```

### 4.3 地址解析 `_resolve_expr_addr`

```python
def _resolve_expr_addr(expr, type_name):
    """从表达式中提取或计算目标地址。"""

    # Case 1: 表达式包含地址字面量
    #   *(type *)0x20001000  →  0x20001000
    m = re.search(r'0x[0-9a-fA-F]+', expr)
    if m and ('*)' in expr or expr.strip().startswith('*')):
        return int(m.group(), 16)

    # Case 2: 纯符号名 → GDB info address
    #   g_config  →  info address g_config → 0x20001234
    addr_output = gdb.execute(f"info address {expr}")
    addr = parse_address(addr_output)
    if addr is not None:
        return addr

    # Case 3: 复杂表达式 → GDB print &(expr)
    #   g_config.baud  →  print &(g_config.baud) → 0x20001234
    addr_output = gdb.execute(f"print &({expr})")
    # 解析 "$1 = (uint32_t *) 0x20001238"
    addr = parse_print_addr(addr_output)
    return addr
```

## 5. API 设计

### 5.1 Watch 表达式求值

```
POST /api/watch/evaluate
```

请求：
```json
{
  "expr": "*(struct uart_config *)0x20001000",
  "read_device": true
}
```

响应：
```json
{
  "success": true,
  "expr": "*(struct uart_config *)0x20001000",
  "addr": "0x20001000",
  "size": 24,
  "type_name": "struct uart_config",
  "is_pointer": false,
  "is_aggregate": true,
  "struct_layout": [
    {"name": "baud", "type_name": "uint32_t", "offset": 0, "size": 4},
    {"name": "parity", "type_name": "uint8_t", "offset": 4, "size": 1},
    {"name": "buf_ptr", "type_name": "uint8_t *", "offset": 8, "size": 4}
  ],
  "hex_data": "00c20100000100000030002000000000...",
  "source": "device"
}
```

参数说明：
- `expr`: C/C++ 表达式字符串
- `read_device`: 是否从设备读取实际数据（false 时只返回类型信息，不读 hex_data）

### 5.2 Watch 指针展开

```
POST /api/watch/deref
```

请求：
```json
{
  "addr": "0x20003000",
  "type_name": "uint8_t *",
  "depth": 1,
  "max_size": 256
}
```

响应：
```json
{
  "success": true,
  "target_addr": "0x20004000",
  "target_type": "uint8_t",
  "target_size": 1,
  "is_aggregate": false,
  "hex_data": "48",
  "display_hint": "char"
}
```

对于 `char *` 类型，后端自动读取到 `\0` 或 `max_size`，返回字符串。

### 5.3 Watch 列表管理

```
GET    /api/watch/list              → 获取所有 watch 表达式
POST   /api/watch/add               → 添加 watch 表达式
DELETE /api/watch/remove             → 删除 watch 表达式
POST   /api/watch/refresh            → 刷新所有 watch 的值
POST   /api/watch/refresh-one        → 刷新单个 watch 的值
```

Watch 列表持久化在 `state` 中（随配置保存/恢复），格式：
```json
[
  {"id": 1, "expr": "*(struct uart_config *)0x20001000", "collapsed": false},
  {"id": 2, "expr": "g_counter", "collapsed": true},
  {"id": 3, "expr": "((float *)0x20002000)[0:5]", "collapsed": false}
]
```

## 6. 后端实现

### 6.1 新增 `core/watch_evaluator.py`

```python
class WatchEvaluator:
    """解析 watch 表达式，利用 GDB 做类型推导，串口做数据读取。"""

    def __init__(self, gdb_session, serial_read_fn):
        self._gdb = gdb_session
        self._read_memory = serial_read_fn

    def evaluate(self, expr: str, read_device: bool = True) -> dict:
        """求值一个 watch 表达式。"""
        # 1. GDB whatis → type_name
        # 2. GDB sizeof → size
        # 3. 解析地址
        # 4. 如果是聚合类型 → ptype /o → struct_layout
        # 5. 如果 read_device → serial read_memory → hex_data
        ...

    def deref_pointer(self, addr: int, type_name: str,
                      depth: int = 1, max_size: int = 256) -> dict:
        """解引用指针，读取目标数据。"""
        # 1. 从设备读 4 字节指针值
        # 2. GDB 解析目标类型
        # 3. 递归 evaluate 目标
        ...
```

### 6.2 新增 `app/routes/watch.py`（或扩展 symbols.py）

路由注册到 Blueprint，挂载在 `/api/watch/`。

### 6.3 GDB 命令映射

| 用户表达式 | GDB 命令 | 解析目标 |
|-----------|----------|----------|
| `*(T *)0xADDR` | `whatis *(T *)0xADDR` | 类型名 |
| `*(T *)0xADDR` | `print sizeof(T)` | 大小 |
| `*(T *)0xADDR` | `ptype /o T` | 结构体布局 |
| `g_var` | `info address g_var` | 地址 |
| `g_var` | `whatis g_var` | 类型名 |
| `g_var.field` | `print &(g_var.field)` | 字段地址 |
| `*g_ptr` | `whatis *g_ptr` | 目标类型 |
| `*g_ptr` | `print sizeof(*g_ptr)` | 目标大小 |
| `(enum E)val` | `whatis val` | 原始类型 |
| `(enum E)val` | `ptype enum E` | 枚举定义 |

### 6.4 数组切片语法

自定义语法 `((T *)ADDR)[start:count]`，后端解析：

```python
# 匹配 [start:count] 或 [count]（start 默认 0）
m = re.search(r'\[(\d+)?:(\d+)\]\s*$', expr)
if m:
    start = int(m.group(1) or 0)
    count = int(m.group(2))
    # 去掉切片后缀，用 GDB 解析基础表达式的元素类型和地址
    base_expr = expr[:m.start()]
    elem_type = gdb_whatis(base_expr)  # e.g. "float *"
    elem_size = gdb_sizeof(去掉指针的类型)
    addr = resolve_addr(base_expr) + start * elem_size
    total_size = count * elem_size
    # 构造 struct_layout 为数组元素列表
    layout = [
        {"name": f"[{start+i}]", "type_name": elem_type去指针,
         "offset": i * elem_size, "size": elem_size}
        for i in range(count)
    ]
```

### 6.5 枚举显示

```python
def _resolve_enum_display(type_name, raw_value):
    """用 GDB ptype 获取枚举定义，匹配值到名称。"""
    output = gdb.execute(f"ptype {type_name}")
    # 解析 "type = enum state_t {IDLE = 0, RUNNING = 1, ERROR = 2}"
    # 返回 "RUNNING" if raw_value == 1
```

## 7. 前端 UI

### 7.1 Watch 面板

在符号搜索区域下方新增 Watch 面板：

```
┌─ WATCH ──────────────────────────────────────┐
│ [+] 添加表达式...                             │
│                                               │
│ ▼ *(struct uart_config *)0x20001000    [⟳][×]│
│   baud      uint32_t   115200                │
│   parity    uint8_t    0                     │
│   buf_ptr   uint8_t *  0x20004000  [→]       │
│                                               │
│ ▶ g_counter                        [⟳][×]    │
│   uint32_t  42                               │
│                                               │
│ ▼ ((float *)0x20002000)[0:5]       [⟳][×]    │
│   [0]  float  3.14                           │
│   [1]  float  2.71                           │
│   [2]  float  0.00                           │
│   [3]  float  -1.00                          │
│   [4]  float  100.5                          │
│                                               │
│ ▶ (enum state_t)g_state            [⟳][×]    │
│   enum state_t  RUNNING (1)                  │
│                                               │
│ [Refresh All]                                │
└───────────────────────────────────────────────┘
```

### 7.2 交互设计

- 输入框支持自动补全（基于 nm 符号表）
- 按 Enter 添加表达式，立即求值并显示
- `[⟳]` 刷新单个表达式（从设备重新读取）
- `[×]` 删除表达式
- `[→]` 展开指针（调用 `/api/watch/deref`）
- 聚合类型默认展开，标量类型折叠显示值
- 值可以 inline 编辑（复用 Phase 2 的字段编辑能力）
- `[Refresh All]` 批量刷新所有表达式
- 支持 auto-refresh（复用 `_autoReadTimers` Map 机制）

### 7.3 值显示规则

| 类型 | 显示格式 | 示例 |
|------|----------|------|
| 整数 | 十进制 (hex) | `115200 (0x0001C200)` |
| float | 小数 | `3.140000` |
| double | 小数 | `3.14159265358979` |
| char | 字符 + ASCII | `'A' (0x41)` |
| char * | 字符串 | `"Hello World"` |
| 指针 | 地址 + [→] | `0x20004000 [→]` |
| 枚举 | 名称 (值) | `RUNNING (1)` |
| 数组 | 展开元素 | `[0] = 1, [1] = 2, ...` |
| struct | 展开字段 | 字段表格 |
| 未知 | raw hex | `DE AD BE EF` |

## 8. 安全与限制

### 8.1 安全措施

- 表达式长度限制：最大 256 字符
- 读取大小限制：单次最大 64KB（与现有 memory/read 一致）
- 指针解引用深度限制：最大 5 层
- 数组切片数量限制：最大 1024 个元素
- GDB 命令超时：10 秒
- 表达式黑名单：禁止 `set`、`call`、`run`、`continue` 等修改状态的命令

### 8.2 已知限制

- GDB 只有 ELF 的类型信息，不能执行函数调用（设备未通过 GDB 连接）
- 局部变量无法查看（需要运行时栈帧，而我们只有静态 ELF 信息）
- 优化后的变量可能被 GDB 报告为 "optimized out"
- C++ 模板类型的 `ptype` 输出可能非常长，需要截断处理

## 9. 实现计划

| 阶段 | 内容 | 工作量 | 依赖 |
|------|------|--------|------|
| W1 | `WatchEvaluator` 核心类 + 单元测试 | 中 | GDB Session |
| W2 | `/api/watch/evaluate` + `/api/watch/deref` API | 小 | W1 |
| W3 | 前端 Watch 面板 UI（添加/删除/显示） | 中 | W2 |
| W4 | 指针展开 + 数组切片 | 中 | W2 |
| W5 | 枚举显示 + char * 字符串 | 小 | W2 |
| W6 | inline 编辑 + auto-refresh | 小 | Phase 2 字段编辑 |
| W7 | Watch 列表持久化 | 极小 | W3 |

## 10. 与现有功能的关系

```
现有 Symbol Viewer (symbols.js)
  └── 以符号名为入口，查看全局变量
  └── 保留不变，作为快速入口

新增 Watch Panel (watch.js)
  └── 以表达式为入口，支持任意地址 + 类型强转
  └── 是 Symbol Viewer 的超集
  └── 复用：
      ├── _decodeFieldValue()  → 值解码
      ├── _renderStructTable() → 结构体渲染（提取为公共函数）
      ├── _formatHexDump()     → hex dump 渲染
      ├── _autoReadTimers      → auto-refresh 机制
      └── writeSymbolField()   → inline 编辑（通过 memory/write）
```

Symbol Viewer 中的 "Read from Device" 按钮可以增加一个 "Add to Watch" 选项，将当前符号添加到 Watch 面板。
