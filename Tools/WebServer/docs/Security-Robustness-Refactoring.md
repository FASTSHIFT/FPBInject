# WebServer 编译系统安全与健壮性整改

## 概述

本次整改针对 FPBInject WebServer 编译系统中的手动字符串处理进行安全与健壮性改进，减少解析脆弱性、命令注入风险与跨平台兼容问题。

## 整改范围

| 文件 | 整改内容 |
|------|----------|
| `core/compile_commands.py` | 命令行解析与 token 遍历 |
| `core/compiler.py` | 编译/链接命令拼接、链接脚本模板、FPB_INJECT 正则提取 |
| `core/patch_generator.py` | #include 路径改写与正则匹配 |
| `core/safe_parser.py` | 新增安全解析工具模块 |
| `core/linker_script.py` | 新增链接脚本模板系统 |

## 新增模块

### `core/safe_parser.py`

安全解析工具模块，提供：

```python
# 安全命令行解析（带降级策略）
from core.safe_parser import safe_shlex_split
tokens = safe_shlex_split(command, fallback=True)

# 路径安全引用
from core.safe_parser import quote_path
safe_path = quote_path("/path/with spaces/file.c")

# FPB_INJECT 标记解析（两阶段）
from core.safe_parser import FPBMarkerParser
funcs = FPBMarkerParser.extract_function_names(source_content)

# 依赖文件解析（多格式支持）
from core.safe_parser import parse_dep_file_command
cmd = parse_dep_file_command(dep_content, source_file)

# LRU 缓存装饰器
from core.safe_parser import cached_parse
@cached_parse(maxsize=64)
def parse_file(path): ...
```

### `core/linker_script.py`

链接脚本模板系统：

```python
from core.linker_script import LinkerScriptConfig, LinkerScriptGenerator

# 自定义配置
config = LinkerScriptConfig(
    bss_alignment=8,
    fpb_text_section=".custom.fpb",
)

# 生成链接脚本
generator = LinkerScriptGenerator(config=config)
content = generator.generate(base_addr=0x20001000)

# 或使用工厂函数
from core.linker_script import create_linker_script
create_linker_script(0x20001000, "output.ld", config={"bss_alignment": 16})
```

## 主要改进

### 1. 命令行解析鲁棒性

**问题**: `shlex.split` 在遇到未配对引号时会抛出异常

**解决方案**:
```python
def safe_shlex_split(command, fallback=True):
    try:
        return shlex.split(command)
    except ValueError as e:
        logger.warning(f"shlex.split failed: {e}")
        if fallback:
            return _fallback_split(command)  # 简单空格分割
        return None
```

### 2. 路径安全化

**问题**: 含空格或特殊字符的路径导致命令拆分错误或注入

**解决方案**:
- 所有路径使用 `shlex.quote()` 包裹
- 统一使用 `pathlib.Path` 处理路径拼接

```python
from pathlib import Path
from core.safe_parser import quote_path

# 跨平台路径处理
source_path = Path(source_file).resolve()

# 安全引用
cmd = f"gcc -I{quote_path(include_dir)} -o {quote_path(output)}"
```

### 3. FPB_INJECT 标记解析

**问题**: 单一正则难以处理跨行 `__attribute__`、复杂声明

**解决方案**: 两阶段解析
1. 定位标记注释
2. 解析后续函数定义

```python
class FPBMarkerParser:
    MARKER_PATTERNS = [...]  # 阶段1: 标记模式
    FUNC_DEF_PATTERN = ...   # 阶段2: 函数定义模式
    
    @classmethod
    def find_marked_functions(cls, content):
        # 先找标记，再找函数
        for marker in find_markers(content):
            func = find_function_after(marker)
            if func:
                yield func
```

### 4. 链接脚本模板化

**问题**: 硬编码链接脚本，难以配置段名与对齐

**解决方案**: 模板驱动生成

```python
# 默认模板
DEFAULT_LINKER_SCRIPT_TEMPLATE = """
SECTIONS
{
    . = 0x${base_addr};
    ${text_section} : { ... }
    ${bss_section} : {
        . = ALIGN(${bss_alignment});
    }
}
"""

# 支持外部模板
generator = LinkerScriptGenerator(template_path="custom.ld.in")
```

### 5. 依赖文件格式支持

**问题**: 仅支持 `cmd_... :=` 格式

**解决方案**: 支持多种格式

```python
DEP_FILE_PATTERNS = [
    (r'^cmd_[^\s:]+\s*:=\s*(.+)$', 'gnu_make'),   # GNU Make
    (r'^command\s*=\s*(.+)$', 'ninja'),            # Ninja
    (r'^(?:CC|CXX)\s*=\s*(.+)$', 'simple'),        # 简单赋值
]
```

### 6. 缓存优化

**问题**: 重复解析同一文件

**解决方案**: LRU 缓存

```python
@cached_parse(maxsize=64)
def parse_compile_commands(path, source_file=None):
    # 基于文件路径和修改时间缓存
    ...
```

## 新增测试

| 测试文件 | 测试数量 | 覆盖内容 |
|----------|----------|----------|
| `test_safe_parser.py` | 44 | 安全解析、路径处理、FPB标记 |
| `test_linker_script.py` | 16 | 模板生成、配置 |
| `test_compiler_extended.py` | 28 | 边界用例、特殊字符 |

### 边界用例覆盖

- 未配对引号的 command 字符串
- 路径含空格与特殊字符
- 跨行 `__attribute__` 与模板化函数声明
- `.d` 文件格式变体
- Unicode 路径

## 验收标准达成

| 标准 | 状态 |
|------|------|
| 路径与参数通过 `shlex.quote` 安全化 | ✅ |
| `shlex.split` 异常有日志与降级行为 | ✅ |
| FPB_INJECT 提取支持复杂声明 | ✅ |
| 链接脚本模板驱动，支持外部配置 | ✅ |
| 新增测试全部通过 | ✅ |
| 测试覆盖率 core 模块 83% | ✅ |

## 使用示例

### 编译注入代码

```python
from core.compiler import compile_inject

data, symbols, error = compile_inject(
    source_content=source,
    base_addr=0x20001000,
    compile_commands_path="build/compile_commands.json",
    linker_config={"bss_alignment": 8},  # 可选配置
)
```

### 生成补丁

```python
from core.patch_generator import PatchGenerator

gen = PatchGenerator()
patch_content, funcs = gen.generate_patch("source.c", "patch.c")
```

## 文件结构

```
core/
├── __init__.py          # 导出新模块
├── safe_parser.py       # 安全解析工具
├── linker_script.py     # 链接脚本模板
├── compile_commands.py  # 重构：使用 safe_parser
├── compiler.py          # 重构：使用模板系统
└── patch_generator.py   # 重构：使用 FPBMarkerParser

templates/
└── inject.ld.in         # 链接脚本模板文件

tests/
├── test_safe_parser.py
├── test_linker_script.py
└── test_compiler_extended.py
```
