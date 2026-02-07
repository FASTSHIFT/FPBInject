# FPB Remap Table 索引 Bug 分析与修复

**日期**: 2026-02-07  
**修复者**: GitHub Copilot  
**影响版本**: fpb_inject.c 修复前版本

---

## 1. Bug 描述

FPB (Flash Patch and Breakpoint) 的 REMAP 功能在使用非零 Comparator 槽位时会导致系统 crash。

### 症状

| 测试场景 | 结果 |
|---------|------|
| 仅使用 SLOT0 | ✅ 正常工作 |
| 仅使用 SLOT1 | ❌ Crash |
| 同时使用 SLOT0 和 SLOT1 | ⚠️ 仅 SLOT0 生效 |
| 先设置 SLOT0+1，再禁用 SLOT0 | ❌ 立即 Crash |

### 硬件环境

- MCU: STM32F103C8T6 (Cortex-M3)
- FPB: v1, 6 code + 2 lit = 8 total comparators

---

## 2. 根因分析

### ARM 官方手册规格 (DDI0403E C1.11)

根据 ARM ARMv7-M Architecture Reference Manual (DDI0403E) 第 C1-755 至 C1-761 页：

> **FP_REMAP register (C1-758):**
> 
> "Software writes to the FP_REMAP Register with the base address for the remap vectors, Remap_Base. **Comparator n remaps to address (Remap_Base + 4n)** when it is configured for remapping and a match occurs."

这意味着 FPB 硬件期望的 remap table 布局是：

```
Remap_Base + 0   → Comparator 0 的重映射指令
Remap_Base + 4   → Comparator 1 的重映射指令
Remap_Base + 8   → Comparator 2 的重映射指令
Remap_Base + 12  → Comparator 3 的重映射指令
...
Remap_Base + 4n  → Comparator n 的重映射指令
```

每个条目恰好是 **1 个 32-bit word (4 bytes)**。

### 错误代码

原代码中使用了 `comp_id * 2` 作为 remap table 索引：

```c
// ❌ 错误的实现
static uint32_t g_fpb_remap_table[FPB_REMAP_TABLE_SIZE * 2];  // 错误：大小翻倍

int fpb_set_patch(uint8_t comp_id, ...) {
    uint32_t remap_index = comp_id * 2;  // 错误：索引翻倍
    g_fpb_remap_table[remap_index] = jump_instr;
    g_fpb_remap_table[remap_index + 1] = patch_addr | 1;  // 错误：多余的存储
    ...
}
```

### 内存布局对比

**原代码的 remap table 布局（错误）：**

| 数组索引 | 字节偏移 | 实际内容 | FPB 硬件期望 |
|---------|---------|---------|-------------|
| [0] | +0 | SLOT0 跳转指令 | SLOT0 跳转指令 ✅ |
| [1] | +4 | SLOT0 目标地址 | SLOT1 跳转指令 ❌ |
| [2] | +8 | SLOT1 跳转指令 | SLOT2 跳转指令 ❌ |
| [3] | +12 | SLOT1 目标地址 | SLOT3 跳转指令 ❌ |

**正确的 remap table 布局：**

| 数组索引 | 字节偏移 | 内容 |
|---------|---------|------|
| [0] | +0 | SLOT0 跳转指令 |
| [1] | +4 | SLOT1 跳转指令 |
| [2] | +8 | SLOT2 跳转指令 |
| [3] | +12 | SLOT3 跳转指令 |

### Crash 原因

当只使用 SLOT1 时：
1. 代码将跳转指令存储到 `remap_table[2]`（偏移 +8）
2. FPB 硬件从 `Remap_Base + 4`（偏移 +4）取指令
3. 偏移 +4 位置存储的是未初始化数据或 SLOT0 的目标地址
4. CPU 执行无效指令 → **HardFault**

---

## 3. 修复方案

### 修改点 1: 修正 remap table 大小

```c
// ✅ 修复后
/* Remap Table - stores jump instructions, must be 32-byte aligned
 * 
 * ARM FPB Remap mechanism:
 *   - Comparator n remaps to address (Remap_Base + 4*n)
 *   - Each remap table entry is 32 bits (one word)
 */
static uint32_t g_fpb_remap_table[FPB_REMAP_TABLE_SIZE];
```

### 修改点 2: 修正索引计算

```c
// ✅ 修复后
int fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr) {
    uint32_t jump_instr = generate_b_w_instruction(original_addr, patch_addr);
    
    /* Store jump instruction at correct index for this comparator */
    g_fpb_remap_table[comp_id] = jump_instr;  // 直接使用 comp_id 作为索引
    
    /* Set remap base */
    FPB_REMAP = remap_base & 0x1FFFFFE0UL;
    ...
}
```

### 修改点 3: 修正 clear 函数

```c
// ✅ 修复后
int fpb_clear_patch(uint8_t comp_id) {
    FPB_COMP(comp_id) = 0;
    g_fpb_remap_table[comp_id] = 0;  // 直接使用 comp_id
    ...
}
```

---

## 4. FP_REMAP 寄存器补充说明

### 寄存器格式

```
31  30  29  28                              5   4       0
+---+---+---+------------------------------+---+--------+
| Reserved |          REMAP[28:5]          | Reserved   |
+---+---+---+------------------------------+---+--------+
        ^
        |
     RMPSPT (bit 29): 1 = 支持 remap，硬连线到 SRAM 区域
```

### 关键特性

1. **RMPSPT (bit 29)**: 指示是否支持 Flash Patch remap
   - 0: 仅支持断点功能
   - 1: **硬连线 remap 到 SRAM 区域 (0x20000000-0x3FFFFFFF)**

2. **REMAP[28:5]**: 存储 remap 表基地址的 bits[28:5]

3. **地址重建**: 实际 remap 地址 = `0x20000000 | (FP_REMAP & 0x1FFFFFE0)`
   - bits[31:29] 硬编码为 `0b001`（SRAM 区域）

4. **对齐要求**: 表必须按 `(NUM_CODE + NUM_LIT)` 个 word 对齐，最小 8 word (32 bytes)

---

## 5. 经验总结

### 教训

1. **仔细阅读硬件手册**: FPB 的 remap 机制有明确的地址计算公式 `(Remap_Base + 4n)`，不应该自行设计索引算法。

2. **不要存储冗余数据**: 原代码将 `patch_addr | 1` 存储在 remap table 中，这不仅浪费空间，还破坏了硬件期望的布局。

3. **边界测试很重要**: 原代码仅在 SLOT0 上测试通过，如果当时测试了 SLOT1，问题会更早被发现。

### 调试技巧

1. 使用 PDF 解析脚本 (`Tools/extract_fpb_section.py`) 快速检索 ARM 手册中的相关章节
2. 对照硬件手册逐行验证寄存器配置
3. 使用 `fpb_cli.py info` 命令检查 FPB 状态

---

## 6. 相关文件

- `Source/fpb_inject.c` - FPB 驱动实现
- `Source/fpb_inject.h` - FPB 驱动头文件
- `Docs/DDI0403E_e_armv7m_arm.pdf` - ARM ARMv7-M 架构参考手册
- `Tools/extract_fpb_section.py` - PDF 章节提取工具

---

## 7. 参考资料

- ARM DDI 0403E.e - ARMv7-M Architecture Reference Manual
  - C1.11 Flash Patch and Breakpoint unit (C1-755 ~ C1-761)
  - C1.11.4 Flash Patch Remap register, FP_REMAP (C1-758)
  - C1.11.5 Flash Patch Comparator register, FP_COMPn (C1-758)
