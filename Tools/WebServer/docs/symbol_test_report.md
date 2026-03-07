# ELF Symbol Pipeline 测试报告

生成时间: 2026-03-07  
ELF: `X-TRACK-EVO-AT32.elf` (12.4 MB)  
测试脚本: `test_elf_symbols.py`

## 1. 总览

| 指标 | 数值 |
|------|------|
| nm 符号总数 | 12,826 |
| nm 耗时 | 0.05s |
| function | 11,026 (86.0%) |
| variable | 938 (7.3%) |
| const | 860 (6.7%) |
| other | 2 (0.0%) |

nm 提取速度极快，类型分布合理。

## 2. 已修复的问题

### 2.1 ✅ section 信息缺失 (P0)

**问题**: `_get_symbol_section()` 只解析 `info address` 输出，但 GDB 对非函数符号不返回 section：

```
Symbol "PIN_MAP" is static storage at address 0x80eb1cc.          → 无 section
Symbol "vtable for AppFactory" is at 0x80f1e9c in a file compiled without debugging.  → 无 section
```

**修复**: 在 `_lookup_symbol_impl` 中，当 section 为空时，用 `info symbol 0x<addr>` 做 fallback：

```
PIN_MAP in section .rodata          → 成功获取 .rodata
_lv_theme_default_styles in section .bss  → 成功获取 .bss
```

**效果**:
- `PIN_MAP`: section 从空变为 `.rodata`，类型正确识别为 `const`
- `_lv_theme_default_styles`: section 从空变为 `.bss`，`read_symbol_value` 正确跳过 BSS
- `lv_font_montserrat_14`: section 从空变为 `.rodata`

### 2.2 ✅ `.N` 后缀局部 static 变量 sizeof 失败 (P2)

**问题**: nm 输出的局部 static 变量带 `.N` 后缀（如 `sm_pdu_size.1`），GDB 无法识别。

**修复**: `_get_sizeof` 增加 fallback，去掉 `.N` 后缀重试。

### 2.3 ✅ nm type code `A` 未映射 (P3)

**问题**: `_sidata` 和 `_Min_Stack_Size` 的 nm type code `A`（absolute）未在 `_NM_TYPE_MAP` 中。

**修复**: 添加 `"A": "other"` 和 `"a": "other"` 映射。

### 2.4 ✅ const struct 无法获取 struct layout (P1)

**问题**: `_get_struct_layout_impl` 检查 `"type = struct"` 是否在输出中，但 `const struct` 的 GDB 输出为 `"type = const struct Point"`，不包含 `"type = struct"` 子串。

**修复**: 改用正则 `r"type\s*=\s*(?:const\s+|volatile\s+)*struct\b"` 匹配，支持 `const`/`volatile` 修饰符。

## 3. 剩余问题

### 3.1 🟡 nm/GDB 类型不一致

随机采样 38 个符号中 5 个类型不匹配：

| 符号 | nm 类型 | GDB 类型 | 原因 |
|------|---------|----------|------|
| `BusFault_Handler` | function | variable | weak alias 到默认 handler，GDB 无调试信息 |
| `__ieee754_atan2` | function | variable | libm 内部函数，无调试信息 |
| `HAL::Manager` | variable | function | nm 看到 BSS 中的对象，GDB 看到构造函数 |
| lambda `_FUN` 符号 | function | variable | GDB 对 lambda 语法报错，fallback 为 variable |

**影响**: 前端搜索用 nm 类型，详情页用 GDB 类型，可能不一致。  
**建议**: 对无调试信息的符号（GDB 返回 "unknown type"），优先使用 nm 的 `sym_type`。

### 3.2 🟡 size=0 的变量（无法 auto-read）

随机采样中 7/38 个符号 size=0，主要类别：

| 类别 | 数量 | 示例 | 原因 |
|------|------|------|------|
| guard variable (`_ZGV*`) | ~166 | `_ZGVZ11DP_Env_InitP8DataNodeE3ctx` | "unknown type" |
| vtable (`_ZTV*`) | ~194 | `_ZTV10AppFactory` | "unknown type" |
| 无调试信息的局部 static | 若干 | `grey_filter.0`, `CSWTCH.56` | GDB 找不到符号 |
| linker script 符号 | 2 | `_sidata`, `_Min_Stack_Size` | 无类型信息 |

**影响**: 这些符号在 UI 中显示为可选但无法读取值。  
**建议**:
- guard variable 固定 size=8（ARM ABI）
- vtable 可通过 `info symbol` 推算大小
- 无调试信息的符号在 UI 标记 "⚠ 无调试信息"

### 3.3 🟡 demangled 名称中的特殊语法导致 GDB 报错

两类问题：

1. **lambda 符号**: `{lambda(void*, long)#3}::_FUN` 中的 `{` `}` `#` 导致 GDB 语法错误
2. **demangled guard variable**: `guard variable for XXX` 中 GDB 将 `guard` 解释为关键字

**影响**: 这些符号只能通过 mangled name (`_ZGV*`, `_ZN*`) 查询。  
**建议**: 对包含 `{lambda` 或以 `guard variable` 开头的 demangled 名称，自动切换到 mangled name 查询。

### 3.4 🔵 GDB 查询性能

| 操作 | 平均耗时 | P95 | 说明 |
|------|----------|-----|------|
| lookup_symbol | 1.13s | 2.13s | 含 section fallback |
| struct_layout | 0.3-1.5s | - | 取决于是否需要 fallback |
| read_symbol_value | 0.9-1.8s | - | 取决于数据大小 |
| API 全流程 | 1.8-5.1s | - | search + lookup + layout + read |

**现有缓解**: `_symbol_detail_cache` + `_struct_layout_cache` 确保第二次起直接命中。  
**建议**: 用户添加符号到监控列表时后台预热缓存。

### 3.5 🔵 长符号名

18 个符号名超过 200 字符（C++ lambda 嵌套），前端需确保 truncate + tooltip。

### 3.6 🔵 同地址 68 个别名

地址 `0x080D5118` 有 68 个符号（ARM 默认中断 handler weak alias），属正常现象。

## 4. C++ 符号测试补充 (2026-03-07)

### 4.1 测试 fixture

新增 `tests/fixtures/test_symbols_cpp.cpp`，覆盖以下 C++ 符号类型：

| 类别 | 示例 | nm type | 测试状态 |
|------|------|---------|----------|
| 命名空间函数 | `HAL::GPIO_Init` / `_ZN3HAL9GPIO_InitEmm` | T | ✅ |
| 嵌套命名空间 | `HAL::Detail::increment` | T | ✅ |
| 命名空间变量 | `HAL::gpio_state` / `_ZN3HAL10gpio_stateE` | B | ✅ |
| 类方法 (weak) | `SensorDevice::init` / `_ZN12SensorDevice4initEv` | W | ✅ |
| 析构函数 D0/D1/D2 | `_ZN12SensorDeviceD0Ev` 等 | W | ✅ |
| 静态类成员 | `Point3D::instance_count` / `_ZN7Point3D14instance_countE` | B | ✅ |
| vtable | `_ZTV12SensorDevice` | V | ✅ |
| guard variable | `_ZGVZ13get_singletonvE8instance` | b | ✅ |
| 函数内 static | `_ZZ13get_singletonvE8instance` | b | ✅ |
| 模板类实例 | `RingBuffer<uint32_t, 8>` / `RingBuffer<uint8_t, 16>` | B | ✅ |
| extern "C" 函数 | `cpp_test_main` | T | ✅ |
| POD const struct | `g_cpp_config` | R | ✅ |
| operator delete | `_ZdlPv` / `_ZdlPvj` | T | ✅ |

### 4.2 发现并修复的 bug

#### 4.2.1 ✅ C++ class 的 struct layout 无法解析 (P1)

**问题**: `_get_struct_layout_impl` 只检查 `type = struct` 和 `type = union`，但 C++ 类的 `ptype /o` 输出为 `type = class Point3D { ... }`。

**修复**: 正则改为 `r"type\s*=\s*(?:const\s+|volatile\s+)*(?:struct|class)\b"`，同时更新 fallback 链中的字符串检查。

#### 4.2.2 ✅ mangled C++ 函数名被误判为 variable (P1)

**问题**: `_lookup_symbol_impl` 通过 `"is a function"` 或 `"in .text"` 判断函数类型，但 mangled 名称（如 `_ZN3HAL9GPIO_InitEmm`）的 `info address` 输出为 `"is at 0x... in a file compiled without debugging"`，不含这两个关键词。

**修复**: 在 section fallback 解析完成后，增加二次检查：如果 `sym_type == "variable"` 且 `section == ".text"`，则修正为 `"function"`。

### 4.3 测试统计

| 指标 | 数值 |
|------|------|
| C fixture 测试 | 46 (5 classes) |
| C++ fixture 测试 | 36 (4 classes) |
| 总计 | 82 tests, 22 subtests |
| 全部通过 | ✅ |

## 5. 修复优先级总结

| 状态 | 优先级 | 问题 | 工作量 |
|------|--------|------|--------|
| ✅ 已修复 | P0 | section 信息缺失 | 小 |
| ✅ 已修复 | P1 | const struct layout 失败 | 极小 |
| ✅ 已修复 | P1 | C++ class layout 不识别 | 极小 |
| ✅ 已修复 | P1 | mangled 函数名误判为 variable | 小 |
| ✅ 已修复 | P2 | `.N` 后缀 sizeof 失败 | 小 |
| ✅ 已修复 | P3 | nm type `A` 未映射 | 极小 |
| 待修复 | P1 | nm/GDB 类型不一致 fallback | 中 |
| 待修复 | P1 | size=0 变量 UI 标记 | 中 |
| 待修复 | P2 | lambda/guard demangled 名称处理 | 小 |
| 待修复 | P2 | union struct layout 解析 | 中 |
| 待修复 | P2 | 嵌套 struct 成员展平 | 中 |
| 可选 | P3 | GDB 查询预热 | 中 |
