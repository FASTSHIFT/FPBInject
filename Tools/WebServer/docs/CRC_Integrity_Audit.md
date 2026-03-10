# FL 串口协议 CRC 完整性审计报告

> 日期: 2026-03-10
> 范围: `fl.c` (固件) + `serial_protocol.py` (上位机)

## 1. 现状分析

### 1.1 CRC 算法

两端使用相同的 **CRC-16-CCITT**（初始值 `0xFFFF`，查表法），表一致，算法正确。

固件端 `calc_crc16_base(crc, data, len)` 支持增量计算（链式调用），可以避免拼接 buffer 的二次拷贝。

### 1.2 各命令 CRC 覆盖范围

| 命令 | `addr`/`offset` | `len` | `data` payload | CRC 方向 | 风险 |
|------|:---:|:---:|:---:|:---:|:---:|
| `write` | ❌ | 隐含 | ✅ | 上→下 | **高** — 地址错误静默写坏内存 |
| `upload` | ❌ | 隐含 | ✅ | 上→下 | **高** — 偏移错误写坏 alloc buffer |
| `read` (响应) | ❌ | ❌ | ✅ | 下→上 | **中** — 无法确认数据来自请求地址 |
| `fwrite` | N/A | 隐含 | ✅ | 上→下 | 低 — 顺序写入，无地址参数 |
| `fread` (响应) | N/A | ❌ | ✅ | 下→上 | 低 — 顺序读取 |

**核心漏洞**: `--addr` / `-a` (offset) / `--len` 等数值参数未参与 CRC 校验。串口传输中任何一个字符翻转（如 `0x20000000` 变成 `0x20000800`）都不会被检测到。

### 1.3 未使用的 argparse 参数

| 参数 | 声明 | 状态 |
|------|------|------|
| `entry` (`-e`) | `OPT_INTEGER('e', "entry", &entry, "Entry offset")` | **完全未使用** — 无任何命令读取 |
| `args` | `OPT_STRING(0, "args", &args, "Arguments")` | **完全未使用** — 无任何命令读取 |

这两个参数是历史遗留，应当清理以减少攻击面和代码噪音。

### 1.4 命令风格不一致

Python 端 `upload` 使用短选项 (`-a`, `-d`, `-r`)，而 `read_memory`/`write_memory` 使用长选项 (`--addr`, `--data`, `--crc`)。功能等价但风格混用，不影响正确性。

## 2. 整改方案

### 2.1 CRC 增强策略

利用 `calc_crc16_base` 的链式调用能力，将 `addr`/`offset`/`len` 的字节表示依次喂入 CRC 计算，**无需拼接 buffer，无二次循环**：

```c
// 固件端示例 (write 命令)
uint16_t crc = 0xFFFF;
uint32_t addr32 = (uint32_t)addr;
uint32_t len32  = (uint32_t)n;
crc = calc_crc16_base(crc, &addr32, sizeof(addr32));  // 4 bytes
crc = calc_crc16_base(crc, &len32,  sizeof(len32));   // 4 bytes
crc = calc_crc16_base(crc, buf, n);                    // payload
```

```python
# 上位机示例 (write 命令)
import struct
crc = 0xFFFF
crc = crc16_update(crc, struct.pack('<II', addr, len(chunk)))
crc = crc16_update(crc, chunk)
```

### 2.2 各命令改动清单

| 命令 | 改动 | CRC 输入 (按顺序) |
|------|------|------|
| `write` | 固件 + 上位机 | `addr(4B)` + `len(4B)` + `data` |
| `upload` | 固件 + 上位机 | `offset(4B)` + `len(4B)` + `data` |
| `read` (响应) | 固件 + 上位机 | `addr(4B)` + `len(4B)` + `data` |
| `fwrite` | 不改 | 无地址参数，当前方案足够 |
| `fread` (响应) | 不改 | 无地址参数，当前方案足够 |

### 2.3 字节序约定

CRC 中的 `addr` 和 `len` 统一使用 **小端序 (little-endian)** 编码，与 ARM Cortex-M 原生字节序一致。固件端直接取内存地址即可，无需额外转换。

### 2.4 向后兼容

- `crc` 参数仍然可选（`-1` = 不校验），旧版上位机不传 CRC 时固件跳过校验
- 新版上位机传入的 CRC 已包含 addr/len，新版固件用增强算法验证
- **不兼容场景**: 新上位机 + 旧固件 → CRC 不匹配 → 写入失败（安全侧失败，可接受）

## 3. 清理项

| 项目 | 操作 |
|------|------|
| `entry` 参数 | 从 `argparse_option` 和局部变量中删除 |
| `args` 参数 | 从 `argparse_option` 和局部变量中删除 |

## 4. 测试计划

### 4.1 上位机测试 (`test_serial_protocol.py`)

- `TestWriteMemoryCRC`: 验证 write 命令的 CRC 包含 addr + len + data
- `TestUploadCRC`: 验证 upload 命令的 CRC 包含 offset + len + data
- `TestReadResponseCRC`: 验证 read 响应解析时 CRC 包含 addr + len + data

### 4.2 固件测试

- 由 CI `lower-machine` job 中的固件单元测试覆盖

## 5. 影响评估

| 维度 | 影响 |
|------|------|
| 安全性 | 显著提升 — 地址/长度错误可被检测 |
| 性能 | 无影响 — CRC 链式调用仅多算 8 字节，可忽略 |
| 兼容性 | 新上位机 + 旧固件会 CRC 失败（安全侧），需同步升级 |
| 代码量 | 固件 ~20 行，上位机 ~30 行，测试 ~60 行 |
