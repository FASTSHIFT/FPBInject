# FL 串口协议 CRC 完整性审计报告

> 日期: 2026-03-10
> 范围: `fl.c` (固件) + `serial_protocol.py` (上位机)

## 1. 整改前现状

### 1.1 CRC 算法

两端使用相同的 **CRC-16-CCITT**（初始值 `0xFFFF`，查表法），表一致，算法正确。

固件端 `calc_crc16_base(crc, data, len)` 支持增量计算（链式调用），可以避免拼接 buffer 的二次拷贝。

上位机端新增 `crc16_update(crc, data)` 对应固件端的链式调用。

### 1.2 整改前各命令 CRC 覆盖范围

| 命令 | `addr`/`offset` | `len` | `comp` | `orig` | `target` | `data` | CRC 方向 | 风险 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `write` | ❌ | 隐含 | — | — | — | ✅ | 上→下 | **高** — 地址错误静默写坏内存 |
| `upload` | ❌ | 隐含 | — | — | — | ✅ | 上→下 | **高** — 偏移错误写坏 alloc buffer |
| `read` (请求) | ❌ | ❌ | — | — | — | — | 上→下 | **中** — 地址错误触发 HardFault |
| `read` (响应) | ❌ | ❌ | — | — | — | ✅ | 下→上 | **中** — 无法确认数据来自请求地址 |
| `patch` | — | — | ❌ | ❌ | ❌ | — | 上→下 | **极高** — 地址错误改变代码跳转 |
| `tpatch` | — | — | ❌ | ❌ | ❌ | — | 上→下 | **极高** — 同上 |
| `dpatch` | — | — | ❌ | ❌ | ❌ | — | 上→下 | **极高** — 同上 |
| `fwrite` | N/A | 隐含 | — | — | — | ✅ | 上→下 | 低 — 顺序写入，无地址参数 |
| `fread` (响应) | N/A | ❌ | — | — | — | ✅ | 下→上 | 低 — 顺序读取 |

### 1.3 已清理的未使用 argparse 参数

| 参数 | 原声明 | 状态 |
|------|------|------|
| `entry` (`-e`) | `OPT_INTEGER('e', "entry", &entry, "Entry offset")` | 已删除 — 无任何命令使用 |
| `args` | `OPT_STRING(0, "args", &args, "Arguments")` | 已删除 — 无任何命令使用 |

## 2. 整改方案

### 2.1 CRC 增强策略

利用 `calc_crc16_base` 的链式调用能力，将数值参数的字节表示依次喂入 CRC 计算，**无需拼接 buffer，无二次循环**：

```c
// 固件端示例 (write 命令)
uint32_t addr32 = (uint32_t)addr;
uint32_t len32  = (uint32_t)n;
uint16_t crc = 0xFFFF;
crc = calc_crc16_base(crc, &addr32, sizeof(addr32));  // 4 bytes
crc = calc_crc16_base(crc, &len32,  sizeof(len32));   // 4 bytes
crc = calc_crc16_base(crc, buf, n);                    // payload
```

```python
# 上位机示例 (write 命令)
crc = crc16_update(0xFFFF, struct.pack('<II', addr, len(chunk)))
crc = crc16_update(crc, chunk)
```

### 2.2 字节序约定

CRC 中的数值参数统一使用 **小端序 (little-endian)** 编码，与 ARM Cortex-M 原生字节序一致。固件端直接取内存地址即可，无需额外转换。

### 2.3 向后兼容

- （后来改为强制）上位机会发 CRC 的命令，固件现在要求带 `crc`，缺少时回复 `CRC required`；`unpatch --all`、`enable --all` 以及没有请求 CRC 的命令不受影响
- 新版上位机传入的 CRC 已包含所有数值参数，新版固件用增强算法验证
- **不兼容场景**: 新上位机 + 旧固件 → CRC 不匹配 → 操作失败（安全侧失败，可接受）

## 3. 整改结果

### 3.1 各命令 CRC 覆盖范围（整改后）

| 命令 | CRC 输入 (按顺序) | CRC 方向 | 状态 |
|------|------|:---:|:---:|
| `write` | `addr(4B)` + `len(4B)` + `data` | 上→下 | ✅ 已修复 |
| `upload` | `offset(4B)` + `len(4B)` + `data` | 上→下 | ✅ 已修复 |
| `read` (请求) | `addr(4B)` + `len(4B)` | 上→下 | ✅ 已修复 |
| `read` (响应) | `addr(4B)` + `len(4B)` + `data` | 下→上 | ✅ 已修复 |
| `patch` | `comp(4B)` + `orig(4B)` + `target(4B)` | 上→下 | ✅ 已修复 |
| `tpatch` | `comp(4B)` + `orig(4B)` + `target(4B)` | 上→下 | ✅ 已修复 |
| `dpatch` | `comp(4B)` + `orig(4B)` + `target(4B)` | 上→下 | ✅ 已修复 |
| `fwrite` | `data` | 上→下 | 无需改动 |
| `fread` (响应) | `data` | 下→上 | 无需改动 |

### 3.2 涉及文件

| 文件 | 改动 |
|------|------|
| `App/func_loader/fl.c` | `cmd_read` 增加请求 CRC 校验；新增 `verify_patch_crc()` 供 patch/tpatch/dpatch 使用；清理 `entry`/`args` 参数 |
| `Tools/WebServer/core/serial_protocol.py` | `read_memory` 发送 `--crc`；新增 `_patch_crc()` 供 patch/tpatch/dpatch 使用；`_parse_read_response` 验证 addr+len+data |
| `Tools/WebServer/utils/crc.py` | 新增 `crc16_update(crc, data)` 支持链式计算 |
| `Tools/WebServer/tests/test_serial_protocol.py` | 新增 `TestEnhancedCRC` 测试类，覆盖 write/upload/read/patch/tpatch/dpatch 的 CRC 验证 |

### 3.3 测试覆盖

| 测试 | 验证内容 |
|------|------|
| `test_write_crc_includes_addr_and_len` | write 命令 CRC 包含 addr + len + data |
| `test_upload_crc_includes_offset_and_len` | upload 命令 CRC 包含 offset + len + data |
| `test_read_response_crc_includes_addr_and_len` | read 响应 CRC 包含 addr + len + data；旧格式 CRC 被拒绝 |
| `test_read_cmd_includes_crc` | read 请求发送 --crc 覆盖 addr + len |
| `test_patch_cmd_includes_crc` | patch 命令 CRC 包含 comp + orig + target |
| `test_tpatch_cmd_includes_crc` | tpatch 命令 CRC 包含 comp + orig + target |
| `test_dpatch_cmd_includes_crc` | dpatch 命令 CRC 包含 comp + orig + target |
| `test_crc16_update_chaining` | crc16_update 链式调用等价于 crc16 拼接调用 |

## 5. 影响评估

| 维度 | 影响 |
|------|------|
| 安全性 | 显著提升 — 地址/长度错误可被检测 |
| 性能 | 无影响 — CRC 链式调用仅多算 8 字节，可忽略 |
| 兼容性 | 新上位机 + 旧固件会 CRC 失败（安全侧），需同步升级 |
| 代码量 | 固件 ~20 行，上位机 ~30 行，测试 ~60 行 |
