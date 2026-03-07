# Symbol Variable Viewer Improvement Plan

## 1. 现状分析

### 1.1 当前架构

```
前端 (symbols.js)
  ├── searchSymbols()        → GET /api/symbols/search  (nm 缓存过滤)
  ├── openSymbolValueTab()   → GET /api/symbols/value   (GDB 读 ELF 初始值)
  ├── readSymbolFromDevice() → POST /api/symbols/read   (串口读设备内存)
  ├── writeSymbolToDevice()  → POST /api/symbols/write  (串口写设备内存)
  └── toggleAutoRead()       → 定时调用 readSymbolFromDevice()

后端 (symbols.py)
  ├── _lookup_symbol()       → GDB lookup_symbol (addr/size/type/section)
  ├── _get_struct_layout_cached() → GDB ptype /o (结构体成员布局)
  ├── _run_serial_op()       → device_worker 线程执行串口操作
  └── fpb.read_memory()      → serial_protocol 分块读取 (chunk_size, 2s/chunk)

底层 (serial_protocol.py)
  ├── read_memory()          → 分块读, 每块 2s 超时, 支持 progress_callback
  └── write_memory()         → 分块写, 每块 2s 超时, 支持 progress_callback
```

### 1.2 痛点汇总

| # | 痛点 | 严重度 | 影响 |
|---|------|--------|------|
| P1 | 只能查看全局符号，不能查看任意地址 | 高 | 无法查看未导出的内存区域、外设寄存器、堆上数据 |
| P2 | 指针指向的数据无法查看 | 高 | 链表、动态缓冲区、字符串指针等常见场景无法调试 |
| P3 | 写入必须完整写入整个符号 | 高 | 大结构体只改一个字段也要写全部数据，效率低且易出错 |
| P4 | 大变量读取前端超时 | 高 | `_run_serial_op` 固定 10s 超时，大数组可能需要更久 |
| P5 | 无读写进度显示 | 中 | 用户不知道操作是否在进行、进度到哪里 |
| P6 | struct 字段不可单独编辑 | 中 | 只能编辑 raw hex dump，无法直接修改某个字段的值 |
| P7 | 不支持 float/double 解码显示 | 低 | 浮点变量只显示 hex，不显示实际浮点值 |
| P8 | auto-read 只支持一个符号 | 低 | 同时监控多个变量时需要反复切换 |

### 1.3 痛点根因

```
P1: API 设计以 "符号名" 为入口，无 "地址+长度" 的通用读写接口
P2: GDB 可以解析指针类型，但前端没有 "dereference" 操作
P3: write API 只接受完整 hex_data，无 offset+partial_data 参数
P4: _run_serial_op 超时固定 10s，不随数据量动态调整
    serial_protocol.read_memory 已支持 progress_callback，但 symbols.py 未使用
P5: read/write 是同步 HTTP 请求，无法推送中间进度
P6: 前端 struct table 是只读渲染，无 inline edit 能力
```

## 2. 整改方案

### Phase 1: 核心能力补齐（解决 P1/P3/P4/P5）

#### 2.1 新增通用内存读写 API

```
GET  /api/memory/read?addr=0x20000000&size=128
POST /api/memory/write  { addr: "0x20000000", offset: 0, hex_data: "..." }
```

- `read`: 支持任意地址 + 长度，不依赖符号名
- `write`: 支持 `offset` 参数，只写入指定偏移处的部分数据
- 前端新增 "Memory Viewer" 入口：输入地址 + 长度即可查看

#### 2.2 读写进度 SSE 流

将大数据读写改为 SSE (Server-Sent Events) 流式接口：

```
POST /api/memory/read/stream
  Request:  { addr: "0x20000000", size: 4096 }
  Response: text/event-stream
    data: {"type":"progress","offset":128,"total":4096}
    data: {"type":"progress","offset":256,"total":4096}
    ...
    data: {"type":"result","success":true,"hex_data":"..."}
```

后端实现：
- `serial_protocol.read_memory` 已有 `progress_callback`，在 callback 中 yield SSE event
- 超时改为动态计算：`timeout = max(10, size / chunk_size * 3)` 秒
- 前端显示进度条 + 百分比 + 已读字节数

#### 2.3 符号写入支持 offset

扩展现有 `/api/symbols/write`：

```json
{
  "name": "g_config",
  "offset": 4,
  "hex_data": "EFBEADDE"
}
```

后端：`addr = symbol_addr + offset`，只写 `len(hex_data)` 字节。
向后兼容：`offset` 缺省为 0，行为不变。

</text>
</invoke>

### Phase 2: 指针解引用 + 字段编辑（解决 P2/P6）

#### 2.4 指针解引用

新增 API：

```
GET /api/symbols/deref?name=g_list_head&depth=1
```

后端逻辑：
1. `lookup_symbol("g_list_head")` → 获取 addr, size, type
2. GDB `ptype g_list_head` → 判断是否为指针类型（`type = xxx *`）
3. 如果是指针：读取指针值（4 字节 ARM），得到目标地址
4. GDB `ptype *g_list_head` → 获取目标类型
5. 读取目标地址处的数据
6. `depth` 控制递归层数（防止循环引用无限展开）

前端：
- struct table 中指针类型字段显示 `→` 按钮
- 点击后展开子表格，显示指针指向的数据
- 支持多级展开（depth 限制，默认 3 层）

#### 2.5 struct 字段 inline 编辑

前端改造：
- struct table 的 Value 列改为可编辑
- 整数字段：显示 `<input type="number">` 或 hex 输入框
- 编辑后只发送该字段的 offset + size 的 partial write
- 调用 `POST /api/symbols/write { name, offset, hex_data }`

交互流程：
```
用户点击字段值 → 变为 input → 用户修改 → 按 Enter 或失焦
  → 前端计算新 hex → POST /api/symbols/write (offset=字段offset, hex_data=字段hex)
  → 成功后刷新该字段显示
```

### Phase 3: 体验优化（解决 P7/P8）

#### 2.6 float/double 解码

扩展 `_decodeFieldValue()`：

```javascript
// 检测 float/double 类型
if (typeName.includes('float') && size === 4) {
  const view = new DataView(new ArrayBuffer(4));
  bytes.forEach((b, i) => view.setUint8(i, b));
  return view.getFloat32(0, true).toPrecision(7);  // little-endian
}
if (typeName.includes('double') && size === 8) {
  const view = new DataView(new ArrayBuffer(8));
  bytes.forEach((b, i) => view.setUint8(i, b));
  return view.getFloat64(0, true).toPrecision(15);
}
```

#### 2.7 多符号并行 auto-read

当前限制：`_autoReadTimer` 和 `_autoReadSymName` 是单例，只能同时 auto-read 一个符号。

改造：
```javascript
// 改为 Map<symName, timerId>
const _autoReadTimers = new Map();

function toggleAutoRead(symName) {
  if (_autoReadTimers.has(symName)) {
    clearInterval(_autoReadTimers.get(symName));
    _autoReadTimers.delete(symName);
  } else {
    const interval = parseInt(intervalInput?.value) || 1000;
    const timerId = setInterval(() => readSymbolFromDevice(symName), interval);
    _autoReadTimers.set(symName, timerId);
  }
}
```

后端：auto-read 请求可能并发，`_run_serial_op` 已通过 device_worker 队列串行化，无需额外处理。但需注意队列堆积——如果多个符号的 auto-read 间隔太短，队列会积压。建议：
- 前端限制最小间隔 500ms
- 后端 worker 队列超过阈值时丢弃旧的 read 请求

## 3. 实现优先级

| 阶段 | 内容 | 工作量 | 价值 |
|------|------|--------|------|
| Phase 1.1 | 通用内存读写 API (2.1) | 小 | 高 — 解锁任意地址查看 |
| Phase 1.2 | 符号写入支持 offset (2.3) | 极小 | 高 — 解锁字段级写入 |
| Phase 1.3 | 读写进度 SSE 流 (2.2) | 中 | 高 — 解决超时和无反馈问题 |
| Phase 2.1 | struct 字段 inline 编辑 (2.5) | 中 | 高 — 大幅提升写入体验 |
| Phase 2.2 | 指针解引用 (2.4) | 中 | 中 — 解锁指针数据查看 |
| Phase 3.1 | float/double 解码 (2.6) | 极小 | 低 — 纯前端改动 |
| Phase 3.2 | 多符号并行 auto-read (2.7) | 小 | 低 — 纯前端改动 |

## 4. API 变更总览

### 新增

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memory/read?addr=&size=` | 任意地址读取 |
| POST | `/api/memory/read/stream` | 大数据流式读取 (SSE) |
| POST | `/api/memory/write` | 任意地址写入 (支持 offset) |
| GET | `/api/symbols/deref?name=&depth=` | 指针解引用 |

### 修改

| 方法 | 路径 | 变更 |
|------|------|------|
| POST | `/api/symbols/write` | 新增可选 `offset` 参数 |
| POST | `/api/symbols/read` | 动态超时 + 可选 SSE 模式 |

### 不变

| 方法 | 路径 |
|------|------|
| GET | `/api/symbols/search` |
| GET | `/api/symbols/value` |
| POST | `/api/symbols/reload` |

## 5. 前端 UI 变更

### Memory Viewer（新增）

- 侧边栏 Symbol 搜索区域下方新增 "Memory" 输入区
- 输入框：Address (hex) + Size (decimal)
- 点击 "Read" 打开 Memory Viewer tab
- 复用现有 hex dump 渲染 + struct table（如果能匹配到符号）

### Symbol Value Tab（改造）

```
┌─────────────────────────────────────────────────┐
│ g_config [var]                           [×]    │
├─────────────────────────────────────────────────┤
│ Address: 0x20001234  Size: 24 bytes  .data (RW) │
│ [Read] [Write] [Auto ▶] [1000ms]    Last: 12:34│
│ ┌──────────────────────────────────────────────┐│
│ │ ████████████████░░░░░░░░ 67%  16/24 bytes    ││  ← 进度条（读写时显示）
│ └──────────────────────────────────────────────┘│
│                                                 │
│ Field      Type        Offset  Size  Value      │
│ ─────────  ──────────  ──────  ────  ────────── │
│ baud       uint32_t    +0      4     [115200 ]  │  ← 可编辑 input
│ parity     uint8_t     +4      1     [0      ]  │
│ stop_bits  uint8_t     +5      1     [1      ]  │
│ *buf_ptr   uint8_t*    +8      4     0x20003000 │  ← 指针，显示 → 按钮
│   └→ [展开指针目标数据...]                       │
│ timeout    float       +12     4     3.14       │  ← float 解码
│                                                 │
│ Raw Hex:                                        │
│ 0x0000: 00 C2 01 00 00 01 ...          .Â....  │
└─────────────────────────────────────────────────┘
```
