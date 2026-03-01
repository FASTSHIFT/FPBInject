---
inclusion: fileMatch
fileMatchPattern: "{App/**,Source/**,Project/**}"
---

# 固件开发指南

当修改 `App/`、`Source/`、`Project/` 下的代码时，遵循以下约定。

## 架构

- 目标平台：ARM Cortex-M3（STM32F103），Thumb/Thumb-2 指令集
- 支持两种运行环境：NuttX RTOS 和裸机（Bare-metal）
- 构建系统：CMake，入口 `CMakeLists.txt`，通过 `NUTTX_APPS_DIR` 区分环境

## 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| func_loader | `App/func_loader/` | 串口协议解析、内存分配、FPB 操作、文件加载 |
| inject | `App/inject/` | 注入相关 C++ 代码、WString patch |
| blink | `App/blink/` | LED 闪烁示例 |
| test | `App/test/` | 板上测试 |

## 编码规范

- C 代码遵循 `.clang-format` 配置
- 函数命名：`模块前缀_动作`，如 `fl_stream_read()`、`fpb_set_patch()`
- 头文件使用 `#pragma once` 或 include guard
- 嵌入式约束：注意栈大小、避免动态分配、注意中断上下文限制

## FPB 相关寄存器

- `FP_CTRL`（0xE0002000）：控制寄存器
- `FP_REMAP`（0xE0002004）：重映射表基址
- `FP_COMP0-7`（0xE0002008-24）：代码/字面量比较器
- 代码区域范围：0x00000000 - 0x1FFFFFFF

## 测试（重要）

### 测试框架

- 自定义 C 测试框架：`App/tests/test_framework.h`
- 在宿主机（x86）上编译运行，使用 mock 替代真实硬件
- Mock 文件：`mock_hardware.c`、`mock_fatfs.c`、`fpb_mock_regs.c`
- 编译定义：`FPB_HOST_TESTING=1` 启用 mock 寄存器
- 覆盖率要求：≥ 80%（CI 强制检查，lcov）

### 三个测试可执行文件

| 目标 | 入口文件 | 说明 |
|------|----------|------|
| `test_runner` | `test_main.c` | 主测试：allocator、loader、stream、file、fpb_inject、debugmon、trampoline |
| `test_runner_nuttx` | `test_fpb_debugmon_nuttx.c` | NuttX 特定的 debugmon 测试 |
| `test_runner_fatfs` | `test_main_fatfs.c` | FatFS 文件后端测试 |

### 运行测试命令

```bash
# 构建并运行所有测试
cd App/tests && bash run_tests.sh

# 运行测试 + 覆盖率报告
cd App/tests && bash run_tests.sh coverage --threshold 80

# 仅构建
cd App/tests && bash run_tests.sh build

# 清理
cd App/tests && bash run_tests.sh clean
```

### 添加新测试的步骤

1. 创建测试文件 `App/tests/test_<module>.c`
2. 包含 `test_framework.h` 和需要的 mock 头文件
3. 编写测试函数（普通 void 函数），使用 `TEST_ASSERT_*` 宏
4. 创建 `run_<module>_tests()` 函数，用 `TEST_SUITE_BEGIN` / `RUN_TEST` 组织
5. 在对应的 `test_main.c`（或 `test_main_fatfs.c`）中声明 `extern void run_<module>_tests(void)` 并调用
6. 在 `App/tests/CMakeLists.txt` 的 `TEST_SOURCES_MAIN`（或 `_NUTTX`/`_FATFS`）中添加源文件
7. 如果测试新的生产代码文件，也要在 `SUT_SOURCES_*` 中添加

### 测试断言宏

```c
TEST_ASSERT(condition)                    // 布尔断言
TEST_ASSERT_EQUAL(expected, actual)       // 整数相等
TEST_ASSERT_EQUAL_HEX(expected, actual)   // 十六进制相等
TEST_ASSERT_STR_EQUAL(expected, actual)   // 字符串相等
TEST_ASSERT_EQUAL_MEMORY(exp, act, len)   // 内存比较
TEST_ASSERT_NOT_NULL(ptr)                 // 非空指针
TEST_ASSERT_NULL(ptr)                     // 空指针
TEST_ASSERT_TRUE(condition)               // 同 TEST_ASSERT
TEST_ASSERT_FALSE(condition)              // 取反断言
TEST_ASSERT_MSG(condition, msg)           // 带消息的断言
```

### 测试代码模板

```c
#include "test_framework.h"
#include "mock_hardware.h"

void test_example_basic(void) {
    TEST_ASSERT_EQUAL(42, some_function());
}

void test_example_null_input(void) {
    TEST_ASSERT_NULL(some_function(NULL));
}

void run_example_tests(void) {
    TEST_SUITE_BEGIN("Example Tests");
    RUN_TEST(test_example_basic);
    RUN_TEST(test_example_null_input);
    TEST_SUITE_END();
}
```

## 构建命令

```bash
# 裸机构建
mkdir -p build && cd build && cmake .. && make

# 烧录
cd Tools && bash flash.sh

# 代码格式化检查
Tools/code_format.sh --check
```
