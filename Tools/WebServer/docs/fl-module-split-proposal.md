# fl.c 模块拆分方案

> 日期: 2026-04-01
> 现状: fl.c 1349 行，25 个 cmd_* 函数，30 个预处理条件编译指令

## 1. 现状分析

### 1.1 fl.c 内容构成

| 区域 | 行数 | 占比 | 说明 |
|------|:----:|:----:|------|
| CRC / Base64 工具函数 | ~130 | 10% | `calc_crc16_base`, `base64_to_bytes`, `bytes_to_base64` |
| 初始化 + 辅助函数 | ~50 | 4% | `fl_init`, `fl_flush_dcache`, `fl_check_addr_range`, `verify_args_crc` |
| 核心命令 (ping/echo/info/alloc/upload/read/write) | ~280 | 21% | 不依赖 FPB 的通用命令 |
| FPB 命令 (patch/tpatch/dpatch/unpatch/enable/hello) | ~270 | 20% | 依赖 FPB 硬件，受 `FL_NO_FPB` 控制 |
| 文件命令 (fopen/fwrite/fread/fclose/fcrc/fseek/fstat/flist/fremove/fmkdir/frename) | ~360 | 27% | 受 `FL_USE_FILE` 控制 |
| 命令分发 (dispatch table + argparse + fl_exec_cmd) | ~60 | 4% | |
| 类型定义 (cmd_args_t / cmd_handler_t) | ~20 | 1% | |

### 1.2 预处理条件分布

| 宏 | 出现次数 | 控制范围 |
|----|:--------:|---------|
| `FL_NO_FPB` | 8 | FPB 命令 + includes + init |
| `FL_USE_FILE` | 4 | 文件命令整块 + dispatch table |
| `FPB_NO_TRAMPOLINE` | 3 | tpatch/unpatch 内部 |
| `FPB_NO_DEBUGMON` | 3 | dpatch/unpatch 内部 |
| `FL_USE_EXTERNAL_ARGPARSE` | 3 | argparse include |

### 1.3 核心问题

1. **单文件过大**: 1349 行，职责混杂
2. **条件编译嵌套**: FPB 命令内部还有 trampoline/debugmon 的 `#ifdef`，三层嵌套
3. **工具函数与业务混合**: CRC、Base64 是通用工具，不应和命令处理混在一起
4. **难以独立测试**: 所有命令共享 `static` 作用域，无法单独编译测试

## 2. 拆分方案

### 2.1 目标文件结构

```
App/func_loader/
├── fl.c                  # 初始化 + 命令分发 (~120 行)
├── fl.h                  # 公开 API (不变)
├── fl_error.h            # 错误码 (不变)
├── fl_cmd_core.c         # 核心命令: ping/echo/echoback/info/hello (~150 行)
├── fl_cmd_mem.c          # 内存命令: alloc/upload/read/write (~250 行)
├── fl_cmd_patch.c        # FPB 命令: patch/tpatch/dpatch/unpatch/enable (~270 行)
├── fl_cmd_file.c         # 文件命令: fopen/fwrite/fread/... (~360 行)
├── fl_cmd.h              # 内部头文件: cmd_args_t, cmd_handler_t, 辅助函数声明
├── fl_codec.c            # CRC + Base64 (~130 行)
├── fl_codec.h            # CRC + Base64 声明
├── fl_allocator.c        # (不变)
├── fl_file.c             # (不变)
├── fl_stream.c           # (不变)
├── fl_log.c              # (不变)
└── fl_port_nuttx.c       # (不变)
```

### 2.2 各文件职责

#### fl.c (瘦身后 ~120 行)

- `fl_init_default()`, `fl_init()`, `fl_is_inited()`
- `fl_exec_cmd()` — argparse + dispatch table
- dispatch table `s_cmd_table[]`

#### fl_cmd.h (新增，内部头文件)

- `cmd_args_t` 结构体定义
- `cmd_handler_t` typedef
- `verify_args_crc()` 声明
- `fl_flush_dcache()` 声明
- `fl_check_addr_range()` 声明
- 各 `cmd_*` 函数声明（供 dispatch table 引用）

#### fl_codec.c / fl_codec.h (新增)

- `calc_crc16_base()`, `calc_crc16()`, `calc_crc16_str()`, `calc_crc16_base_str()`
- `base64_to_bytes()`, `bytes_to_base64()`
- 从 `static` 改为模块内部可见（通过 `fl_codec.h` 暴露给其他 `fl_cmd_*.c`）

#### fl_cmd_core.c (新增)

- `cmd_ping`, `cmd_echo`, `cmd_echoback`, `cmd_info`, `cmd_hello`
- `cmd_info` 内部的 `#ifndef FL_NO_FPB` 保留

#### fl_cmd_mem.c (新增)

- `cmd_alloc`, `cmd_upload`, `cmd_read`, `cmd_write`
- `fl_flush_dcache()`, `fl_check_addr_range()` 移入此文件

#### fl_cmd_patch.c (新增)

- 整个文件被 `#ifndef FL_NO_FPB` 包裹
- `verify_patch_crc()`, `cmd_patch`, `cmd_tpatch`, `cmd_dpatch`, `cmd_unpatch`, `cmd_enable`
- `FPB_NO_TRAMPOLINE` / `FPB_NO_DEBUGMON` 的条件编译集中在此文件
- `FL_NO_FPB` 时提供 stub 实现（`FL_NO_FPB_CMD` 宏）

#### fl_cmd_file.c (新增)

- 整个文件被 `#if FL_USE_FILE` 包裹（或直接通过 CMake 控制编译）
- `cmd_fopen` ~ `cmd_frename` 全部 11 个文件命令

### 2.3 条件编译简化

| 当前 | 拆分后 |
|------|--------|
| fl.c 内 `#ifndef FL_NO_FPB` 包裹 FPB 命令 | `fl_cmd_patch.c` 整文件 `#ifndef FL_NO_FPB ... #endif` 包裹 |
| fl.c 内 `#if FL_USE_FILE` 包裹文件命令 | `fl_cmd_file.c` 整文件 `#if FL_USE_FILE ... #endif` 包裹 |
| fl.c 内 `FPB_NO_TRAMPOLINE` / `FPB_NO_DEBUGMON` | 仅在 `fl_cmd_patch.c` 内部，不扩散 |
| dispatch table 内 `#if FL_USE_FILE` | 保留（无法避免） |

条件编译保留在源码中（`#if` / `#ifndef`），不依赖 CMake 条件编译，确保兼容 NuttX Make、Keil、IAR 等不同构建系统。拆分后每个文件只关心自己的条件宏，不再出现多层嵌套。

## 3. 风险评估

| 风险 | 等级 | 缓解措施 |
|------|:----:|---------|
| `static` 函数改为模块可见，增加符号暴露 | 低 | 使用 `fl_cmd.h` 内部头文件，不对外暴露 |
| 拆分后编译依赖变复杂 | 低 | CMake glob 已覆盖 `func_loader/*.c` |
| 测试用例需要适配 | 中 | 测试通过 `fl_exec_cmd` 黑盒调用，不直接调用 `cmd_*`，无需改动 |
| dispatch table 仍需条件编译 | 低 | 不可避免，但只剩 1 处 `#if FL_USE_FILE` |

## 4. 实施建议

分 3 步渐进式拆分，每步独立可验证：

1. **Step 1**: 提取 `fl_codec.c/h`（CRC + Base64），风险最低
2. **Step 2**: 提取 `fl_cmd_file.c`（文件命令），已有天然的 `#if FL_USE_FILE` 边界
3. **Step 3**: 提取 `fl_cmd_patch.c`（FPB 命令）+ `fl_cmd_mem.c`（内存命令）+ `fl_cmd_core.c`（核心命令）

每步完成后跑 `build_test.sh` + `run_tests.sh` 验证。
