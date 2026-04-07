# NuttX FPB Comp 自动分配问题整改方案

> 日期: 2026-04-07
> 状态: 待实施

## 1. 问题描述

### 1.1 现象

在 NuttX 平台上使用 dpatch 模式注入时，手动指定 `--comp 1` 后：
- `fl -c info` 显示 `Slot[0]` 的 COMP 寄存器有值（on），`Slot[1]` 的 COMP 为 0（off）
- `fl -c enable --comp 1 --enable 1` 返回 `[FLERR] Failed to enable patch 1: -2`
- 但 patch 代码内部的 `fpb_enable_patch(0, false/true)` 可以正常工作（因为恰好对上了 comp 0）

### 1.2 根因

NuttX 的 `arm_breakpoint_add`（`arch/arm/src/armv8-m/arm_dbgmonitor.c`）不支持指定硬件 comparator 编号，而是从 comp 0 开始遍历，找到第一个空闲的自动分配：

```c
// NuttX arm_breakpoint_add 核心逻辑
for (i = 0; i < num; i++) {
    uint32_t comp = getreg32(FPB_COMP0 + i * 4);
    if (comp == fpb_comp)       // 已设置，返回
        return 0;
    else if (comp & ENABLE)     // 被占用，跳过
        continue;
    else                        // 空闲，使用这个
        putreg32(fpb_comp, FPB_COMP0 + i * 4);
        return 0;
}
```

因此 `fpb_debugmon_nuttx.c` 中 `set_redirect(comp_id=1, ...)` 调用 `up_debugpoint_add` 后，NuttX 实际将断点写入了硬件 FPB_COMP[0]（第一个空闲的）。`comp_id` 只是 `g_debugmon_state.redirects[]` 数组的索引，与硬件 comparator 编号不对应。

而 `fpb_enable_patch(1, true)` 直接操作 `FPB_COMP(1)` 寄存器，该寄存器为空，返回 `FPB_ERR_INVALID_PARAM`。

### 1.3 影响范围

| 场景 | 是否受影响 | 说明 |
|------|:----------:|------|
| dpatch --comp 0（且 comp 0 空闲） | ✅ 正常 | NuttX 自动分配到 comp 0，恰好对上 |
| dpatch --comp 1（且 comp 0 空闲） | ❌ 异常 | NuttX 分配到 comp 0，但 enable 操作 comp 1 |
| dpatch --comp 1（且 comp 0 已占用） | ✅ 正常 | NuttX 跳过 comp 0，分配到 comp 1 |
| patch/tpatch（FPBv1 REMAP 模式） | ✅ 正常 | 直接写 FPB_COMP 寄存器，不走 NuttX API |
| patch 代码内 fpb_enable_patch | ✅ 正常 | 操作的是实际有值的硬件 comp |

核心矛盾：用户指定的 `comp_id` 是逻辑槽位号，NuttX 分配的是物理 comparator 号，两者不一定相等。

## 2. 整改方案

### 2.1 思路

不改下位机固件。在上位机侧保证逻辑槽位号与物理 comparator 号一致：

1. **Slot 下拉菜单默认自动模式**：复用 `find_slot_for_target` 的分配逻辑（从 slot 0 开始找第一个空闲），与 NuttX `arm_breakpoint_add` 的分配算法一致
2. **Patch 模板中 comp id 参数化**：通过编译宏 `-DFPB_PATCH_COMP_ID=N` 传入，避免源码中硬编码

### 2.2 整改点一：Slot 下拉菜单增加自动模式

**文件**: `templates/partials/editor.html`

在 `slotSelect` 下拉菜单最前面增加 "Auto" 选项，value 为 -1，设为默认选中：

```html
<select id="slotSelect" ...>
  <option value="-1" selected data-i18n="device.slot_auto">Auto</option>
  <option value="0" ...>Slot 0</option>
  ...
</select>
```

**文件**: `static/js/core/slots.js`

- `onSlotSelectChange`：当选择 Auto（-1）时，`state.selectedSlot = -1`
- `updateSlotUI`：Auto 模式下状态栏显示 "Slot: Auto"

**文件**: `static/js/features/patch.js` — `performInject`

当 `state.selectedSlot === -1` 时，传 `comp: -1` 给后端。后端 `inject()` 已有 `comp < 0` 时调用 `find_slot_for_target` 的逻辑，无需改动。

**关键点**：`find_slot_for_target` 的分配算法是"找第一个空闲 slot"，与 NuttX `arm_breakpoint_add` 的"找第一个空闲 comp"一致，因此自动模式下逻辑槽位号 = 物理 comparator 号。

**重复注入行为**：`find_slot_for_target` 已实现 Smart Reuse 策略 — 如果同一个 `target_addr` 已在某个 slot 中，直接复用该 slot（先 unpatch 再重新注入），不会新开 slot。

### 2.3 整改点二：Patch 模板 comp id 参数化

**现状**（`static/js/features/patch.js` — `generatePatchTemplate`）：

```c
/**
 * Patch for: fl_hello
 * Slot: 0
 * Original: 0x08001234
 */
...
fpb_enable_patch(0, false);
ORIG_FL_HELLO();
fpb_enable_patch(0, true);
```

slot 值写死在源码里。如果用户切换 slot 或使用自动模式重新注入，源码里的 comp id 不会更新。

**整改后**：

模板中 `fpb_enable_patch` 改为使用宏，头部注释去掉 Slot 行：

```c
/**
 * Patch for: fl_hello
 * Original: 0x08001234
 */
...
fpb_enable_patch(FPB_PATCH_COMP_ID, false);
ORIG_FL_HELLO();
fpb_enable_patch(FPB_PATCH_COMP_ID, true);
```

`FPB_PATCH_COMP_ID` 完全由编译时 `-D` 注入，源码中不定义默认值。未定义时编译报错，这是期望行为 — 强制要求通过构建系统传入，避免静默使用错误的 comp id。

**文件**: `core/compiler.py` — `compile_inject`

新增 `comp_id` 参数，在构建编译命令时追加 `-DFPB_PATCH_COMP_ID=N`：

```python
def compile_inject(
    ...
    comp_id: int = -1,  # 新增
) -> Tuple[...]:
```

```python
# 在 cmd 构建完成后
if comp_id >= 0:
    cmd.extend(["-D", f"FPB_PATCH_COMP_ID={comp_id}"])
```

**文件**: `fpb_inject.py` — `inject`

将 `actual_comp` 传递给第二次 `compile_inject`（此时 comp 已确定）：

```python
# 第二次编译（已知 actual_comp）
data, inject_symbols, error = self.compile_inject(
    ...
    comp_id=actual_comp,
)
```

第一次编译（用于计算 code_size，base_addr=0x20000000）也需要传一个临时值。由于第一次编译只是为了确定大小，comp_id 不影响二进制大小，传 0 即可：

```python
# 第一次编译（确定大小）
data, inject_symbols, error = self.compile_inject(
    ...
    comp_id=0,  # 临时值，不影响 code_size
)
```

## 3. 兼容性

| 场景 | 影响 |
|------|------|
| 已有 patch 源码（硬编码 comp id） | 不受影响，`-D` 不会覆盖源码中的字面量 |
| 已有 patch 源码（使用 `FPB_PATCH_COMP_ID` 宏） | 由 `-D` 自动赋值，正常工作 |
| MCP 工具注入（comp=-1） | 已支持自动分配，无需改动 |
| 手动选择 Slot 0~7 | 行为不变，传指定的 comp id |
| NuttX dpatch 自动模式 | 修复，逻辑槽位 = 物理 comp |

## 4. 涉及文件

| 文件 | 改动 |
|------|------|
| `templates/partials/editor.html` | slotSelect 增加 Auto 选项（默认选中） |
| `static/js/core/slots.js` | 支持 selectedSlot = -1，状态栏显示 "Auto" |
| `static/js/features/patch.js` | 模板使用 `FPB_PATCH_COMP_ID` 宏，去掉 Slot 注释行 |
| `core/compiler.py` | 新增 comp_id 参数，编译时注入 `-DFPB_PATCH_COMP_ID=N` |
| `fpb_inject.py` | 两次 compile_inject 调用传递 comp_id |
