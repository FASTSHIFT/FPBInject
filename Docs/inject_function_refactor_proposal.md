# FPBInject 函数注入机制整改方案

## 1. 问题分析

### 1.1 当前实现方式

当前 FPBInject 通过重命名函数来标识需要注入的目标：

```cpp
// 当前方式：函数被重命名
void renamed_digitalWrite(uint8_t pin, uint8_t value) {
    // 注入代码
}
```

**实现流程：**

1. **patch_generator.py** - 识别 `/* FPB_INJECT */` 标记，重命名函数
2. **compiler.py** - 通过特殊前缀识别目标函数
3. **链接器脚本** - 使用特殊 section 保留代码

### 1.2 存在的问题

| 问题 | 描述 | 影响 |
|------|------|------|
| **函数签名被修改** | 函数名改变 | 依赖该函数的代码链接失败 |
| **ABI 不兼容** | 符号表被破坏 | IDE 和调试器无法识别 |
| **头文件污染** | 声明与实现不匹配 | 编译错误 |

### 1.3 关于调用原函数

**结论：不支持调用原函数。**

FPB 硬件在 CPU 取指令时拦截并重定向，无论通过何种方式（函数指针、别名等）调用原函数地址，都会被 FPB 硬件再次重定向，导致**无限递归**。

可能的解决方案及其问题：
- **临时禁用 FPB** → 竞态风险，需要运行时库支持，复杂
- **Trampoline 技术** → 需要复制原函数头部指令，对 Thumb-2 实现复杂

这些方案都不够简洁，因此**设计上明确不支持调用原函数**。

---

## 2. 新设计方案

### 2.1 核心思路

**保持函数名不变，通过 section 属性标识注入代码。**

```cpp
/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void digitalWrite(uint8_t pin, uint8_t value) {
    // 完全替换原函数的实现
    Serial.printf("pin=%d val=%d\n", pin, value);
    GPIO_WriteBit(GPIOA, pin, value);  // 用户自己实现完整逻辑
}
```

### 2.2 用户接口

```cpp
#include <stdio.h>

/* FPB_INJECT */
void target_function(int arg) {
    // 用户编写完整的替换实现
    // 注意：无法调用原函数，需要自己实现完整逻辑
    printf("Patched: arg=%d\n", arg);
}
```

**设计原则：**
- ✅ 函数名保持不变
- ✅ 使用 `/* FPB_INJECT */` 注释标记
- ✅ 工具自动添加 section 属性
- ❌ 不支持调用原函数（硬件限制）

### 2.3 工具处理流程

```
用户源码                    处理后源码
─────────────────────────────────────────────────────
/* FPB_INJECT */           __attribute__((section(".fpb.text"), used))
void foo(int x) {    →     void foo(int x) {
    ...                        ...
}                          }
```

---

## 3. 工具改造详情

### 3.1 patch_generator.py 改造

**移除的功能：**
- 函数重命名逻辑

**保留/修改的功能：**
- `/* FPB_INJECT */` 标记识别
- 自动添加 `__attribute__((section(".fpb.text"), used))`

```python
class PatchGenerator:
    FPB_INJECT_MARKER = "FPB_INJECT"
    SECTION_ATTR = '__attribute__((section(".fpb.text"), used))'
    
    def process_source_content(self, content: str, marked_functions: list) -> str:
        """处理源码，添加 section 属性"""
        lines = content.split('\n')
        result = []
        
        for i, line in enumerate(lines):
            # 检测 FPB_INJECT 标记
            if self.FPB_INJECT_MARKER in line:
                # 下一行是函数定义，添加属性
                result.append(line)  # 保留注释
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # 在函数定义前插入属性
                    result.append(self.SECTION_ATTR)
                continue
            result.append(line)
        
        return '\n'.join(result)
```

### 3.2 compiler.py 改造

**链接器脚本更新：**

```python
LD_SCRIPT_TEMPLATE = """
MEMORY
{
    PATCH (rx) : ORIGIN = {patch_addr}, LENGTH = {patch_size}
}

SECTIONS
{
    .text : {
        KEEP(*(.fpb.text))    /* 注入代码 section */
        KEEP(*(.fpb.data))    /* 注入数据 section */
        *(.text .text.*)
        *(.rodata .rodata.*)
    } > PATCH
}
"""
```

**函数识别逻辑更新：**

```python
def find_patch_functions(self, source_content: str) -> list:
    """从 FPB_INJECT 标记识别目标函数"""
    pattern = r'/\*\s*FPB_INJECT\s*\*/\s*\n\s*(?:__attribute__.*?\)\s*)?(\w+)\s+(\w+)\s*\('
    matches = re.findall(pattern, source_content)
    return [(ret_type, func_name) for ret_type, func_name in matches]
```

### 3.3 Section 命名规范

| Section | 用途 |
|---------|------|
| `.fpb.text` | 注入的代码 |
| `.fpb.data` | 注入代码使用的数据 |
| `.fpb.rodata` | 只读数据 |

---

## 4. 实施计划

### Phase 1：核心改造 (1 天)

1. **patch_generator.py**
   - 移除函数重命名逻辑
   - 实现 section 属性自动插入
   - 更新函数识别正则

2. **compiler.py**
   - 更新链接器脚本模板
   - 更新函数识别逻辑
   - 移除旧的前缀匹配代码

### Phase 2：测试更新 (0.5 天)

1. 更新现有单元测试
2. 添加新的测试用例
3. 验证编译链接正常

### Phase 3：文档更新 (0.5 天)

1. 更新 README.md
2. 更新 Docs/CLI.md
3. 更新 Docs/WebServer.md

---

## 5. 示例对比

### 旧方式 (废弃)

```cpp
// ❌ 旧方式：函数被重命名，依赖代码会链接失败
void renamed_digitalWrite(uint8_t pin, uint8_t value) {
    GPIO_WriteBit(GPIOA, pin, value);
}

void setup() {
    renamed_digitalWrite(13, 1);  // 必须使用新名字
}
```

### 新方式

```cpp
// ✅ 新方式：保持原函数名
/* FPB_INJECT */
void digitalWrite(uint8_t pin, uint8_t value) {
    Serial.printf("Hooked: pin=%d val=%d\n", pin, value);
    GPIO_WriteBit(GPIOA, pin, value);
}

void setup() {
    digitalWrite(13, 1);  // 正常调用，无需修改
}
```

---

## 6. 总结

| 方面 | 旧方案 | 新方案 |
|------|--------|--------|
| 函数命名 | 被重命名 | 保持原名 |
| 依赖链接 | ❌ 报错 | ✅ 正常 |
| 调用原函数 | ❌ 不支持 | ❌ 不支持 (硬件限制) |
| IDE 兼容 | ⚠️ 符号不匹配 | ✅ 完全兼容 |
| 代码简洁性 | ⚠️ 需要特殊命名 | ✅ 只需注释标记 |

**新方案优势：**
- 函数签名保持不变，依赖代码正常编译链接
- 使用简单的注释标记，对用户代码侵入最小
- 工具自动处理 section 属性，用户无需关心底层细节
