# Tutorial: 手动注入 fl_cmd_demo 体验教学设计

> 日期: 2026-03-05
> 状态: Draft
> 关联: `tutorial-system-design.md`, `fl.c` → `fl_cmd_demo()`

## 1. 背景

当前教学引导共 11 步（welcome → complete），覆盖了各面板功能介绍，但缺少一个**端到端的注入实操环节**。用户走完教学后仍不清楚"注入到底是什么效果"。

固件侧已新增 `fl_cmd_demo` 函数（`__attribute__((noinline))`，非 static），通过 `fl -c demo` 调用，输出：

```
Hello from original fl_cmd_demo!
Inject a new version to change this message.
[FLOK] DEMO original
```

本方案在教学流程中追加 **3 个实操步骤**，让用户亲手完成一次完整的 **搜索 → 注入 → 验证 → 取消注入 → 再验证** 闭环。

## 2. 新增步骤概览

在现有 `config`（步骤 9）和 `complete`（步骤 10）之间插入 3 个步骤：

| 序号 | id | 面板 | 核心操作 | Gate 条件 |
|------|-----|------|---------|-----------|
| 10 | `demo_search` | Symbols | 搜索 `fl_cmd_demo` 符号并双击创建补丁标签页 | Editor 中存在 `fl_cmd_demo` 补丁标签页 |
| 11 | `demo_inject` | Editor | 编辑补丁代码并点击 Inject 注入 | 对应 slot 状态变为 active |
| 12 | `demo_verify` | — (居中) | 运行 demo 命令观察注入效果，然后 Unpatch 再运行观察原始效果 | 无 gate（纯观察步骤） |

原 `complete` 步骤顺延为步骤 13。

## 3. 步骤详细设计

### 3.1 步骤 10: `demo_search` — 搜索符号

**目标**: 让用户在 Symbols 面板搜索 `fl_cmd_demo`，双击符号创建补丁标签页。

```js
{
  id: 'demo_search',
  sidebar: 'details-symbols',
  gate: () => {
    // 检查 Editor 标签页中是否存在 fl_cmd_demo 的补丁标签
    const tabs = document.querySelectorAll('#editorTabsHeader .tab');
    return Array.from(tabs).some(t => t.textContent.includes('fl_cmd_demo'));
  },
  gateHint: 'tutorial.gate_demo_search',
  gateOk: 'tutorial.gate_demo_search_ok',
}
```

**渲染内容**:
- 说明：在搜索框输入 `fl_cmd_demo`，找到该符号后双击打开补丁编辑器
- 3 个 feature-item：
  1. 🔍 输入搜索关键词 — 在 Symbol Search 输入框中输入 `fl_cmd_demo`
  2. 📋 查看搜索结果 — 列表中会显示函数地址和名称
  3. ✏️ 双击创建补丁 — 双击符号自动生成补丁模板代码
- Gate 状态提示

**交互提示**: 可在搜索框预填 placeholder 或用 `tutorial-field-guide` class 高亮搜索输入框。

### 3.2 步骤 11: `demo_inject` — 编辑并注入

**目标**: 用户在编辑器中修改补丁代码（改变输出消息），然后点击 Inject 按钮完成注入。

```js
{
  id: 'demo_inject',
  highlight: '#editorContainer',
  gate: () => {
    // 检查是否有 active 的 FPB slot
    const slotStates = window.FPBState?.slotStates || [];
    return slotStates.some(s => s && s.active);
  },
  gateHint: 'tutorial.gate_demo_inject',
  gateOk: 'tutorial.gate_demo_inject_ok',
}
```

**渲染内容**:
- 说明：修改补丁代码中的输出消息，然后点击 Inject 按钮
- 提供建议修改示例（用代码块展示）：

```c
// 将 fl_println 的内容改为你想要的消息，例如：
fl_println("Hello from INJECTED fl_cmd_demo!");
fl_response(true, "DEMO injected");
```

- 3 个 feature-item：
  1. ✏️ 修改代码 — 编辑 `fl_println` 中的字符串，改为你自己的消息
  2. 🎯 选择 Slot — 确认 Slot 下拉框选择了可用槽位
  3. 🚀 点击 Inject — 点击工具栏的 Inject 按钮，等待注入完成
- Gate 状态提示

### 3.3 步骤 12: `demo_verify` — 验证注入效果

**目标**: 用户通过 Quick Commands 运行 `fl -c demo` 观察注入后的输出，然后 Unpatch 再运行一次观察恢复原始输出。

```js
{
  id: 'demo_verify',
  // 无 sidebar / highlight → 居中显示 + tutorial-blocking 遮罩
  // 无 gate → 纯观察步骤，用户自行确认后点 Next
}
```

**渲染内容**:
- 分两个阶段说明（用有序列表 + callout 风格）：

**阶段 A — 验证注入生效**:
1. 在 Quick Commands 面板输入 `fl -c demo` 并发送
2. 在 Serial 日志中观察输出 — 应该看到你修改后的消息
3. 确认 `[FLOK] DEMO injected`（或你自定义的响应）

**阶段 B — 取消注入并对比**:
1. 在 Device Info 面板找到已注入的 slot，点击 ✕ 按钮取消注入（或点击 Clear All）
2. 再次发送 `fl -c demo`
3. 观察输出恢复为原始消息：`Hello from original fl_cmd_demo!`

- 底部提示：这就是 FPB 运行时代码注入的完整流程！无需重新烧录固件即可替换函数行为。

## 4. i18n 翻译键

### 新增键（`tutorial` 命名空间）

```
# demo_search 步骤
demo_search_title
demo_search_desc
demo_search_input
demo_search_input_desc
demo_search_result
demo_search_result_desc
demo_search_dblclick
demo_search_dblclick_desc

# demo_inject 步骤
demo_inject_title
demo_inject_desc
demo_inject_edit
demo_inject_edit_desc
demo_inject_slot
demo_inject_slot_desc
demo_inject_run
demo_inject_run_desc
demo_inject_example

# demo_verify 步骤
demo_verify_title
demo_verify_desc
demo_verify_phase_a
demo_verify_phase_a_desc
demo_verify_phase_b
demo_verify_phase_b_desc
demo_verify_hint

# Gate 消息
gate_demo_search
gate_demo_search_ok
gate_demo_inject
gate_demo_inject_ok
```

### 中文翻译示例

| Key | zh-CN |
|-----|-------|
| `demo_search_title` | 搜索目标函数 |
| `demo_search_desc` | 在符号面板中搜索 fl_cmd_demo，双击创建补丁 |
| `demo_inject_title` | 编辑并注入补丁 |
| `demo_inject_desc` | 修改补丁代码中的输出消息，然后注入到设备 |
| `demo_verify_title` | 验证注入效果 |
| `demo_verify_desc` | 运行 demo 命令对比注入前后的输出差异 |
| `gate_demo_search` | 请在符号面板搜索 fl_cmd_demo 并双击创建补丁 |
| `gate_demo_search_ok` | 补丁标签页已创建！ |
| `gate_demo_inject` | 请修改补丁代码后点击 Inject 按钮注入 |
| `gate_demo_inject_ok` | 注入成功！ |

## 5. 实现清单

### 5.1 tutorial.js

- [ ] 在 `TUTORIAL_STEPS` 数组中 `config` 之后、`complete` 之前插入 3 个步骤定义
- [ ] 在 `stepRenderers` 中添加 `demo_search()`、`demo_inject()`、`demo_verify()` 渲染函数
- [ ] `demo_inject` 渲染器中包含代码示例（用 `<pre><code>` 展示建议修改）
- [ ] `demo_verify` 渲染器中用两个分组（Phase A / Phase B）展示操作步骤
- [ ] `complete` 步骤的步骤摘要需适配新增的 3 步

### 5.2 i18n 翻译文件

- [ ] `static/js/locales/en.js` — 添加所有新增 key 的英文翻译
- [ ] `static/js/locales/zh-CN.js` — 添加中文翻译
- [ ] `static/js/locales/zh-TW.js` — 添加繁体中文翻译

### 5.3 测试

- [ ] `tests/test_frontend.js` — 更新步骤总数（11 → 14）
- [ ] 手动测试：完整走一遍教学流程，验证 gate 轮询、步骤切换、auto-position 正常
- [ ] 验证 `demo_search` gate：双击符号后标签页出现 → gate 通过
- [ ] 验证 `demo_inject` gate：注入成功后 slot active → gate 通过
- [ ] 验证 `demo_verify`：无 gate，Next 按钮始终可用

## 6. 前置条件

教学中这 3 个步骤需要设备已连接且 config 已配置（ELF 路径等），这由前面的 `connection`、`device`、`config` 步骤的 gate 保证。如果用户跳过了前置步骤，`demo_search` 的符号搜索会因缺少 ELF 路径而失败，此时搜索 API 会返回错误提示，用户自然会意识到需要先配置。

## 7. 风险与备选

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 用户跳过 config 步骤 | 符号搜索失败 | 在 `demo_search` 渲染器中检测 ELF 路径是否配置，未配置时显示提示 |
| 设备未连接 | 注入失败 | `demo_inject` gate 依赖 slot active，注入失败时 gate 不通过，用户可 Skip |
| `fl_cmd_demo` 不在 ELF 中 | 搜索无结果 | 固件侧已确保 `noinline` + 非 static，编译后必有符号；文档中注明需使用包含该函数的固件版本 |
| 教学步骤过多导致疲劳 | 用户中途退出 | 保持 Skip / Skip All 按钮可用；3 个新步骤是实操性质，比纯介绍更有吸引力 |
