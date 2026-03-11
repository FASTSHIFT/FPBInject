# C++ 注入支持现状分析

## 背景

对 C++ 源文件执行自动注入时，编译阶段出现大量来自 C++ 标准库头文件（`<cmath>`、`<functional>`、`<tuple>` 等）的错误。根本原因是当前编译流水线主要面向 C 文件设计，缺乏对 C++ 的完整支持。

## 错误表现

典型的编译失败信息：

```
error: 'abs' has not been declared in 'std'
error: 'FP_NAN' was not declared in this scope
error: 'float_t' has not been declared in '::'
error: 'acosf' has not been declared in '::'
```

原因链：

1. C++ 标准库头文件（libc++）依赖 C 数学库（`<math.h>`）提供特定符号
2. 头文件搜索路径顺序错误 — 工具链自带的 `math.h` 包装器试图从 `std::` 命名空间拉取符号，但此时这些符号尚未定义
3. 编译器以 `gcc` 而非 `g++` 调用，导致头文件解析行为不同

## 现有架构问题

### 问题 1：编译器未根据文件类型切换

编译流水线始终使用从 `compile_commands.json` 中提取的编译器。当匹配到的条目是 C 文件（回退匹配的常见情况）时，编译器为 `gcc` 而非 `g++`。

C++ 文件需要 `g++` 的原因：
- 默认启用 C++ 语言模式
- 自动添加 C++ 标准库的 include 路径
- 自动链接 `libstdc++` / `libc++`

**当前行为**：即使源文件是 `.cpp`，编译器仍然使用匹配条目中的 `gcc`。

### 问题 2：回退匹配跳过 C++ 文件

编译命令匹配采用 4 级回退策略：

| 级别 | 策略 | C++ 支持 |
|------|------|----------|
| 1 | 精确路径匹配 | ✅ 如果存在 `.cpp` 条目则可用 |
| 2 | 路径后缀匹配（≥3 级目录） | ❌ 仅搜索 `.c` 文件 |
| 3 | 目录树匹配 | ❌ 仅搜索 `.c` 文件 |
| 4 | 任意 `.c` 文件兜底 | ❌ 明确限定 `.c` |

如果 `compile_commands.json` 中没有精确匹配的 `.cpp` 条目，所有回退路径都会返回 C 文件的编译参数 — 缺少 C++ 标准版本、C++ include 路径，且使用 `gcc` 而非 `g++`。

### 问题 3：缺少 C++ 标准库路径处理

include 路径解析未考虑 C++ 标准库头文件：

- 没有自动发现 `libc++` 或 `libstdc++` 的 include 目录
- 没有为 C++ 头文件添加 `-isystem` 路径
- 没有注入 `-std=c++17`（或类似）标志
- 没有处理 `-fno-exceptions`、`-fno-rtti` 等嵌入式 C++ 常用选项

所有 C++ 相关的编译参数完全依赖 `compile_commands.json` 中匹配到的条目。

### 问题 4：头文件搜索路径顺序冲突

错误日志揭示了头文件包含顺序问题：

```
libcxx/math.h → libcxx/cmath → __compare/strong_order.h → ...
→ 工具链 math.h → 尝试 "using std::abs" → 失败
```

工具链自带的 `math.h` 包装器期望 `std::abs` 等符号已由 `<cmath>` 定义，但 `<cmath>` 自身仍在处理中。这种循环依赖通常由编译器内置的 include 路径排序解决，而这只有在使用 `g++` 时才能正确工作。

## 影响评估

| 场景 | 状态 | 说明 |
|------|------|------|
| C 文件注入 | ✅ 正常 | 主要使用场景，已充分测试 |
| C++ 文件且精确匹配 compile_commands | ⚠️ 部分可用 | 需要条目使用 `g++` 且包含完整参数 |
| C++ 文件回退匹配 | ❌ 不可用 | 回退到 C 参数，编译失败 |
| C++ 文件包含复杂头文件（`<functional>`、`<vector>`） | ❌ 不可用 | 标准库头文件无法解析 |
| C++ 文件仅包含 C 头文件 | ⚠️ 可能可用 | 如果不依赖 C++ 标准库，`gcc` 或许够用 |

## 改进方案

### 短期：编译器自动切换

当源文件扩展名为 `.cpp` / `.cc` / `.cxx` 时，自动将编译器从 `gcc` 替换为 `g++`：

```
arm-none-eabi-gcc → arm-none-eabi-g++
```

这一项改动即可解决大部分 C++ 编译失败，因为 `g++` 会自动添加正确的 C++ 标准库 include 路径。

### 中期：C++ 回退匹配

扩展回退匹配策略，使其同时搜索 `.cpp` / `.cc` 文件：

- 第 2-3 级：同时搜索 `.c` 和 `.cpp` 文件
- 第 4 级：当源文件为 C++ 时，优先选择 `.cpp` 兜底条目
- 从匹配到的 C++ 条目中提取 `-std=c++*` 等参数

### 长期：完整 C++ 支持

- 从构建系统自动检测 C++ 标准版本
- 在 Web UI 中支持配置 C++ 编译参数
- 支持自定义 C++ 标准库 include 路径覆盖
- 处理 `-fno-exceptions`、`-fno-rtti` 等嵌入式 C++ 常见选项

## 临时解决方案

在正式支持 C++ 之前，用户可以通过以下方式绕过：

1. 确保目标 `.cpp` 文件在 `compile_commands.json` 中有精确匹配的条目
2. 将补丁函数写在单独的 `.c` 文件中，使用 `extern "C"` 链接，避免依赖 C++ 标准库
3. 通过配置手动添加所需的 include 路径和编译参数

## 结论

当前注入流水线在 C++ 支持方面存在根本性缺口。编译器选择和 include 路径解析在设计上以 C 为中心。短期修复（自动切换 `gcc` → `g++`）可以用最小的代码改动解决最常见的失败场景。中长期改进将使 C++ 注入在不同构建配置下都能稳定工作。

---

## 已实施的修复

以下修复已全部实现并通过 CI 验证。

### 修复 1：编译器自动切换 gcc → g++（`compiler.py`）

当源文件扩展名为 `.cpp` / `.cc` / `.cxx` 时，自动将编译器路径中的 `gcc` 替换为 `g++`。

### 修复 2：C++ 回退匹配（`compile_commands.py`）

- 第 2-3 级目录树匹配：当源文件为 C++ 时，同时搜索 `.cpp` / `.cc` / `.cxx` 条目
- 第 4 级兜底匹配：当源文件为 C++ 时，优先选择 C++ 条目

### 修复 3：C++ 编译参数白名单（`compile_commands.py`）

cflags 解析器原先只保留 `-mthumb`、`-mcpu` 等 ARM 架构参数和少量通用参数。C++ 关键参数被丢弃，导致头文件搜索路径冲突。

新增白名单项：

| 参数 | 作用 |
|------|------|
| `-nostdinc++` | 禁用编译器自带的 C++ 标准库头文件路径 |
| `-fno-exceptions` | 禁用 C++ 异常（嵌入式常用） |
| `-fno-rtti` | 禁用运行时类型信息（嵌入式常用） |
| `-std=*` | C/C++ 标准版本（如 `-std=c++17`、`-std=gnu++20`） |

其中 `-nostdinc++` 是最关键的修复 — 没有它，`g++` 会同时搜索工具链自带的 C++ 标准库和项目自定义的 libc++，两者冲突导致 `using std::abs` 等声明失败。

### 修复 4：C++ 名称修饰（name mangling）支持（`compiler.py`）

C++ 编译器会对函数名进行修饰（mangling），例如：

```
void Class::method(bool, bool) → _ZN5ns5Class6methodEbb
```

这导致三个环节失败：

1. **链接器 `-Wl,-u` 标志**：使用未修饰名 `Class::method`，链接器找不到符号，`--gc-sections` 删除了注入函数
2. **链接脚本 `KEEP` 规则**：`KEEP(*(.text.Class::method))` 无法匹配实际的 section 名 `.text._ZN5ns5Class6methodEbb`
3. **最终符号查找**：nm 输出的 demangled 名带完整命名空间（`ns::Class::method`），与标记提取的短名（`Class::method`）不匹配

解决方案：新增 `_resolve_mangled_names()` 函数：

- 编译 `.o` 后，分别运行 `nm`（mangled）和 `nm -C`（demangled）
- 逐行配对，构建 demangled → mangled 映射
- 同时生成后缀映射（`Class::method` → mangled name），解决命名空间前缀不匹配问题
- 链接器 `-Wl,-u` 和 `KEEP` 规则使用 mangled 名
- 最终符号匹配使用后缀比较，并将短名回写到返回的 symbols 字典

### 修复 5：FPB_INJECT 标记正则支持 C++ 类方法（`patch_generator.py`、`compiler.py`）

原正则 `(\w+)\s*\(` 无法匹配 `Class::method` 中的 `::`。

修改为 `([\w:]+)\s*\(`，支持：

- C 函数：`void func()` → 提取 `func`
- C++ 类方法：`void Class::method()` → 提取 `Class::method`

### 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `core/compile_commands.py` | C++ 回退匹配、cflags 白名单扩展 |
| `core/compiler.py` | `_resolve_mangled_names()`、mangled 名链接、后缀符号匹配 |
| `core/patch_generator.py` | FPB_INJECT 正则支持 `::` |
| `tests/test_compiler.py` | 更新 mock side_effect 适配新增的 nm 调用 |
| `tests/test_compiler_extended.py` | 同上 |
| `tests/test_compile_inplace.py` | 同上 + 修正 `call_args_list` 索引 |
