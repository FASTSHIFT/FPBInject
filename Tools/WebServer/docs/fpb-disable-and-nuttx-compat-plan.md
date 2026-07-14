# FPB 功能开关与 NuttX `running_regs` 兼容性改进方案

> 日期: 2026-07-13
> 版本: v1.0
> 状态: 已实现 `running_regs` 兼容层；FPB 全关 config 为待实现提案

---

## 一、背景

### 1.1 问题描述

FPBInject 项目存在两个需要改进的兼容性问题：

1. **`running_regs()` 函数兼容性**：`fpb_debugmon_nuttx.c` 中的 `debugmon_callback` 直接调用了 `running_regs()`，但该函数并非在所有 NuttX 版本中都存在。低版本 NuttX 编译时会报错。

2. **FPB 功能全关**：当前虽然有 `FL_NO_FPB` 宏可以禁用 FPB 相关命令，但缺少一个统一的 Kconfig 开关来在编译配置层面控制 FPB 功能的启用/禁用。

### 1.2 `running_regs()` 的历史演变

通过 `git log -S "running_regs"` 追踪，NuttX 中获取当前中断寄存器上下文的 API 经历了三代演变：

| 时间段 | API | 定义位置 | 说明 |
|--------|-----|----------|------|
| 2024-04 之前 | `CURRENT_REGS` 宏 | `arch/<arch>/include/irq.h` | `#define CURRENT_REGS (g_current_regs[up_cpu_index()])` |
| 2024-04 ~ 2024-09 | `up_current_regs()` 内联函数 | `arch/<arch>/include/irq.h` | `static inline uint32_t *up_current_regs(void)` |
| 2024-09+ | `running_regs()` 宏 | `include/nuttx/sched.h` | `#define running_regs() ((FAR void **)(g_running_task->xcp.regs))` |

关键 commit：
- `a31a82c2283` (2024-04-08): `arch: change get_current_regs to up_current_regs`
- `19b4911d7fd` (2024-09-24): `arch: remove up_current_regs in common code` — 引入 `running_regs()`
- `0ad222e2b40` (2024-11-20): `arm: remove up_set_current_regs/up_current_regs` — ARM 架构清理

---

## 二、`running_regs` 兼容方案（已实现）

### 2.1 设计思路

新增 `Source/fpb_nuttx_compat.h` 兼容头文件，通过预处理宏检测自动选择可用的 API：

```
优先级 1: running_regs (NuttX >= 2024-09) → 原生支持，无需处理
优先级 2: CURRENT_REGS  (NuttX < 2024-04) → #define running_regs() ((void *)CURRENT_REGS)
优先级 3: NULL fallback (2024-04 ~ 2024-09 中间版本) → #define running_regs() (NULL)
```

### 2.2 为什么中间版本（up_current_regs）用 NULL 而非自动检测

`up_current_regs()` 是 `static inline` 函数，**无法用 `#ifdef` 检测**。如果强行 `#define running_regs() up_current_regs()`，在不存在该函数的版本上会导致编译错误。

因此选择 NULL fallback 策略：
- 不报编译错误（满足"实在兼容不了不报错也行"的要求）
- `debugmon_callback` 已有 NULL 检查，会打印明确的错误日志
- 用户可手动通过编译参数 `-Drunning_regs()=up_current_regs()` 启用

### 2.3 实现文件

#### `Source/fpb_nuttx_compat.h`（新增）

核心逻辑：

```c
#if defined(__NuttX__) && !defined(FPB_HOST_TESTING_NUTTX)

#ifndef running_regs
  #ifdef CURRENT_REGS
    /* 最旧 API: CURRENT_REGS 宏 */
    #define running_regs() ((void *)CURRENT_REGS)
  #else
    /* 中间版本或未知: NULL fallback */
    #define running_regs() (NULL)
    #define FPB_RUNNING_REGS_FALLBACK_NULL 1
  #endif
#endif

#endif
```

#### `Source/fpb_debugmon_nuttx.c`（修改）

1. 在 NuttX 系统头文件**之后**引入 `fpb_nuttx_compat.h`（确保 `running_regs` 已被定义时不会被覆盖）
2. 改进 `debugmon_callback` 的 NULL 处理日志，在 `FPB_RUNNING_REGS_FALLBACK_NULL` 时给出更明确的版本提示

### 2.4 兼容性矩阵

| NuttX 版本 | `running_regs` | `CURRENT_REGS` | 兼容结果 | dpatch 功能 |
|------------|----------------|----------------|----------|-------------|
| >= 2024-09 | ✅ 已定义 | — | ✅ 原生工作 | ✅ 可用 |
| 2024-04 ~ 2024-09 | ❌ | ❌ | ⚠️ NULL fallback | ❌ 不可用（日志提示） |
| < 2024-04 | ❌ | ✅ 已定义 | ✅ 通过 CURRENT_REGS | ✅ 可用 |

### 2.5 用户手动启用中间版本支持

如果用户使用 2024-04 ~ 2024-09 的 NuttX 版本且需要 dpatch 功能，可在编译参数中手动指定：

```bash
# 在 Makefile/CMake 中添加
CFLAGS += -Drunning_regs\(\)=up_current_regs\(\)
```

或在 `nuttx.cmake` 中：

```cmake
target_compile_definitions(fl PRIVATE running_regs()=up_current_regs())
```

---

## 三、FPB 全关 Kconfig 开关方案（待实现提案）

### 3.1 现有宏开关体系

项目已有一套分层的宏开关：

| 宏 | 层级 | 作用 | 当前控制方式 |
|----|------|------|-------------|
| `FL_NO_FPB` | func_loader 层 | 禁用所有 FPB patch 命令（patch/tpatch/dpatch/unpatch/enable） | 编译参数 |
| `FPB_NO_TRAMPOLINE` | Source 层 | 禁用 trampoline 模式 | 编译参数 |
| `FPB_NO_DEBUGMON` | Source 层 | 禁用 DebugMonitor 模式 | 编译参数 |
| `FPB_HOST_TESTING` | Source 层 | 主机测试模式（使用 mock 寄存器） | CMake 选项 |

当 `FL_NO_FPB` 定义时，`fl_cmd_patch.c` 提供了 stub 实现，所有 patch 命令返回 `FL_ERR_DISABLED`。

### 3.2 提议的 Kconfig 增强

在 `Kconfig` 中新增配置项，将现有编译参数宏与 Kconfig 系统对接：

```kconfig
if FPBINJECT

# ... 现有配置项 ...

config FPBINJECT_NO_FPB
	bool "Disable FPB hardware (FL_NO_FPB)"
	default n
	---help---
		Disable all FPB hardware operations. Patch/tpatch/dpatch/unpatch/enable
		commands will return FL_ERR_DISABLED. Useful for platforms without FPB
		support or for memory-only injection scenarios.

config FPBINJECT_NO_TRAMPOLINE
	bool "Disable trampoline mode (FPB_NO_TRAMPOLINE)"
	default n
	depends on !FPBINJECT_NO_FPB
	---help---
		Disable trampoline-based injection. tpatch command will return error.
		Use when FPB can REMAP to RAM directly without trampoline intermediaries.

config FPBINJECT_NO_DEBUGMON
	bool "Disable DebugMonitor mode (FPB_NO_DEBUGMON)"
	default n
	depends on !FPBINJECT_NO_FPB
	---help---
		Disable DebugMonitor-based injection. dpatch command will return error.
		Use on platforms without DebugMonitor exception support.

endif # FPBINJECT
```

### 3.3 构建系统对接

#### `cmake/nuttx.cmake` 修改

```cmake
set(FPB_DEFINITIONS
    FL_NUTTX_BUF_SIZE=${CONFIG_FPBINJECT_BUF_SIZE}
    FL_NUTTX_LINE_SIZE=${CONFIG_FPBINJECT_LINE_SIZE}
    FL_USE_FILE=1
    FL_FILE_USE_POSIX=1
)

if(CONFIG_FPBINJECT_NO_FPB)
    list(APPEND FPB_DEFINITIONS FL_NO_FPB)
endif()

if(CONFIG_FPBINJECT_NO_TRAMPOLINE)
    list(APPEND FPB_DEFINITIONS FPB_NO_TRAMPOLINE)
endif()

if(CONFIG_FPBINJECT_NO_DEBUGMON)
    list(APPEND FPB_DEFINITIONS FPB_NO_DEBUGMON)
endif()

nuttx_add_application(
    NAME fl
    ...
    DEFINITIONS ${FPB_DEFINITIONS}
)
```

#### `Makefile` 修改

```makefile
CFLAGS += -DFL_NUTTX_BUF_SIZE=$(CONFIG_FPBINJECT_BUF_SIZE) \
          -DFL_NUTTX_LINE_SIZE=$(CONFIG_FPBINJECT_LINE_SIZE) \
          -DFL_USE_FILE=1 \
          -DFL_FILE_USE_POSIX=1

ifdef CONFIG_FPBINJECT_NO_FPB
CFLAGS += -DFL_NO_FPB
endif

ifdef CONFIG_FPBINJECT_NO_TRAMPOLINE
CFLAGS += -DFPB_NO_TRAMPOLINE
endif

ifdef CONFIG_FPBINJECT_NO_DEBUGMON
CFLAGS += -DFPB_NO_DEBUGMON
endif
```

### 3.4 上位机兼容性

#### 设备端 `info` 命令输出变化

当 FPB 全关时，`fl_cmd_print_fpb_info` 已有 stub 输出：

```
FPB: disabled (FL_NO_FPB)
```

上位机 `serial_protocol.py` 的 `info()` 方法解析 FPB 信息时需要处理这种情况：

```python
# 当前解析逻辑（serial_protocol.py info() 方法）
elif line.startswith("FPB:"):
    info["fpb_detail"] = line.split(":", 1)[1].strip()
    if "v1" in line:
        info["fpb_version"] = 1
    elif "v2" in line:
        info["fpb_version"] = 2
    # 需要新增: 检测 disabled
    if "disabled" in line:
        info["fpb_disabled"] = True
        info["fpb_version"] = 0
```

#### 上位机 UI 适配建议

1. **`info` 响应解析**：当检测到 `fpb_disabled: True` 时，前端禁用 patch/tpatch/dpatch/enable 按钮
2. **inject 请求**：当 `fpb_version == 0` 时，`inject_single()` 应提前返回错误 `"FPB hardware disabled on device"`
3. **slot 显示**：FPB 禁用时 slot 列表为空，前端显示 "FPB disabled" 状态

#### 协议向后兼容

- 设备端 `info` 命令的输出格式不变（已有 `FPB: disabled (FL_NO_FPB)` stub）
- patch/tpatch/dpatch/enable 命令仍可发送，设备返回 `[FLERR] FPB disabled (FL_NO_FPB)`
- 上位机无需修改命令发送逻辑，只需在 UI 层根据 `fpb_disabled` 标志禁用操作

### 3.5 实现优先级

根据需求"全关这个优先级不高"，建议：

1. ✅ **已实现**：`running_regs` 兼容层（`fpb_nuttx_compat.h`）
2. ⬜ **待实现**：Kconfig 开关 + 构建系统对接
3. ⬜ **待实现**：上位机 `fpb_disabled` 检测与 UI 适配

---

## 四、变更清单

### 已实现变更

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `Source/fpb_nuttx_compat.h` | 新增 | `running_regs` 兼容头文件 |
| `Source/fpb_debugmon_nuttx.c` | 修改 | 引入兼容头文件 + 改进 NULL 处理日志 |

### 待实现变更（FPB 全关 config）

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `Kconfig` | 修改 | 新增 `FPBINJECT_NO_FPB` / `FPBINJECT_NO_TRAMPOLINE` / `FPBINJECT_NO_DEBUGMON` |
| `cmake/nuttx.cmake` | 修改 | Kconfig → 编译宏映射 |
| `Makefile` | 修改 | Kconfig → 编译宏映射 |
| `Tools/WebServer/core/serial_protocol.py` | 修改 | `info()` 解析 `fpb_disabled` |
| `Tools/WebServer/fpb_inject.py` | 修改 | `inject_single()` 检查 `fpb_disabled` |

---

## 五、测试建议

### 5.1 `running_regs` 兼容性测试

1. **新版 NuttX (>= 2024-09)**：正常编译，dpatch 功能正常工作
2. **旧版 NuttX (< 2024-04)**：定义了 `CURRENT_REGS`，`running_regs()` 被映射为 `CURRENT_REGS`，dpatch 应正常工作
3. **中间版本 (2024-04 ~ 2024-09)**：`running_regs()` 为 NULL，编译不报错，dpatch 命令触发时日志输出版本提示
4. **主机测试**：`FPB_HOST_TESTING_NUTTX` 模式下使用 mock 的 `running_regs()`，不受影响

### 5.2 FPB 全关测试（待实现后）

1. 启用 `CONFIG_FPBINJECT_NO_FPB`，编译固件
2. 上位机连接后 `info` 命令应显示 `FPB: disabled (FL_NO_FPB)`
3. 尝试发送 `patch` 命令，应返回 `[FLERR] FPB disabled (FL_NO_FPB)`
4. 上位机 UI 应禁用注入相关按钮
