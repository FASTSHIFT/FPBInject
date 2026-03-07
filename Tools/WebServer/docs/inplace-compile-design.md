# In-Place Compile Design

## 背景

当前自动注入流程中，`PatchGenerator` 需要：
1. 拷贝整个源文件内容
2. 在 `/* FPB_INJECT */` 标记的函数前插入 `__attribute__((section(".fpb.text"), used))`
3. 将相对 `#include` 路径转换为绝对路径（因为编译在临时目录进行）
4. 将修改后的内容写入临时目录的 `inject.c` 进行编译

这种方式存在以下问题：
- 源码拷贝和修改增加了复杂度和出错概率
- include 路径转换可能遗漏或误转换
- 生成的 patch 源码与原始文件不一致，调试困难

## 方案

### 核心思路

利用 GCC 的 `-ffunction-sections` 编译选项（当前已在使用），每个函数会生成独立的 `.text.函数名` section。在链接阶段通过 linker script 的 `KEEP()` 精确选择需要注入的函数，而不是依赖自定义的 `.fpb.text` section。

### 改动点

#### 1. `compiler.py` - `compile_inject()`

新增 `source_file` 参数，支持直接编译原始文件：

- 当提供 `source_file` 时，直接编译该文件（不写临时文件）
- 编译输出（.o/.elf/.bin）仍然放在临时目录
- linker script 改为使用 `KEEP(*(.text.func1)) KEEP(*(.text.func2))` 选择目标函数
- 保留 `source_content` 参数的兼容性（旧模式仍可用）

新增 `inject_functions` 参数：
- 指定需要注入的函数名列表
- 用于生成精确的 linker script KEEP 规则
- 用于 `-Wl,-u,func_name` 强制保留符号

#### 2. `patch_generator.py` - `PatchGenerator`

新增 `generate_patch_inplace()` 方法：
- 只做标记检测，返回 `(source_file_path, [函数名列表])`
- 不再生成修改后的源码副本
- 保留 `generate_patch()` 方法的兼容性

#### 3. `file_watcher_manager.py` - `_trigger_auto_inject()`

修改自动注入流程：
- 使用 `find_marked_functions()` 检测标记
- 直接将原始文件路径和函数列表传给编译器
- 不再经过 `generate_patch()` 生成中间源码

### 编译流程对比

#### 旧流程
```
源文件 → PatchGenerator.generate_patch() → 修改后的源码字符串
  → compile_inject(source_content=修改后源码) → 写入临时文件 → 编译 → 链接(.fpb.text) → binary
```

#### 新流程
```
源文件 → PatchGenerator.find_marked_functions() → 函数名列表
  → compile_inject(source_file=原始文件, inject_functions=[函数名]) → 原地编译 → 链接(KEEP .text.func) → binary
```

### Linker Script 变化

旧版：
```ld
.text : {
    KEEP(*(.fpb.text))
    *(.text .text.*)
}
```

新版（原地编译模式）：
```ld
.text : {
    KEEP(*(.text.func1))
    KEEP(*(.text.func2))
    *(.text .text.*)
}
```

### 兼容性

- `source_content` 参数仍然有效（Web 编辑器手动输入场景）
- `generate_patch()` 方法保留不变
- 新增的 `source_file` + `inject_functions` 是可选参数
- 当 `source_file` 存在时优先使用原地编译模式

## 测试计划

- `test_compile_inplace.py`：测试原地编译路径
  - 测试 source_file 参数传递
  - 测试 inject_functions linker script 生成
  - 测试编译/链接/objcopy 各阶段错误处理
  - 测试与旧模式的兼容性
  - 测试 file_watcher_manager 新流程
