# 快捷指令分组功能增强方案

## 1. 问题描述

当前分组只是渲染时按 `cmd.group` 字符串聚合的"虚拟分组"，没有独立元数据，导致：

| 缺陷 | 现状 |
|------|------|
| 不可重命名 | 只能逐个移动命令到新分组间接实现 |
| 不可拖动排序 | 顺序由 `Object.entries()` 插入顺序决定 |
| 不可删除 | 只能逐个移出命令后分组自动消失 |
| 命令不可拖拽排序 | 命令项无拖拽能力（仅宏步骤有） |

## 2. 整改方案

### 2.1 数据模型变更

新增分组元数据存储，localStorage key `fpbinject-quick-command-groups`：

```javascript
[
  { name: "System", order: 0 },
  { name: "Init",   order: 1 }
]
```

命令仍通过 `cmd.group` 字符串关联。

导出格式直接改为 version 2，不兼容旧格式：

```json
{
  "version": 2,
  "groups": [
    { "name": "System", "order": 0 },
    { "name": "Init",   "order": 1 }
  ],
  "commands": [ ... ]
}
```

### 2.2 新增函数

```javascript
// 分组元数据
function loadGroupMeta()
function saveGroupMeta(groups)
function ensureGroupMeta(commands)

// 分组操作
function renameGroup(oldName)
function deleteGroup(groupName)
function showGroupContextMenu(event, name)
function qcGroupContextAction(action)

// 拖拽排序
function initCommandDrag()
function initGroupDrag()

// 选择性导入/导出
function openExportDialog()              // 打开导出选择对话框
function openImportDialog(fileData)      // 打开导入预览 + 冲突处理对话框
function resolveImportConflicts(incoming, existing)  // 检测并返回冲突列表
```

### 2.3 修改函数

| 函数 | 修改内容 |
|------|----------|
| `renderQuickCommands()` | 按 groupMeta order 排序；分组 header 加右键菜单和拖拽手柄；命令项加拖拽手柄 |
| `saveQuickCommand()` | 新分组时同步追加 groupMeta |
| `moveToGroup()` | 同步更新 groupMeta |
| `clearAllQuickCommands()` | 同时清空 groupMeta |
| `exportQuickCommands()` | 改为调用 `openExportDialog()` |
| `importQuickCommands()` | 文件读取后调用 `openImportDialog()` |

### 2.4 UI 变更

#### 分组 header 增强

```
现有：  ▼ 📁 System                        （仅折叠）
改为：  ≡ ▼ 📁 System                [⋯]   （拖拽 + 右键菜单）
```

#### 命令项增强

```
现有：  ▸ ps -A                    [▶] [⋯]
改为：  ≡ ▸ ps -A                  [▶] [⋯]  （新增拖拽手柄）
```

#### 分组右键菜单（新增 `qcGroupContextMenu`）

```html
<div class="qc-context-menu" id="qcGroupContextMenu" style="display: none">
  <div class="qc-context-item" onclick="qcGroupContextAction('rename')">
    <i class="codicon codicon-edit"></i>
    <span data-i18n="quick_commands.rename_group">Rename Group</span>
  </div>
  <div class="qc-context-separator"></div>
  <div class="qc-context-item danger" onclick="qcGroupContextAction('delete')">
    <i class="codicon codicon-trash"></i>
    <span data-i18n="quick_commands.delete_group">Delete Group</span>
  </div>
</div>
```

#### 导出选择对话框

点击 Export 后弹出模态框，按分组展示 checkbox 树：

```
┌─────────────────────────────────────────┐
│ Export Commands                       ✕  │
├─────────────────────────────────────────┤
│                                         │
│ Select commands to export:              │
│                                         │
│ ☑ Select All                            │
│                                         │
│ ☑ 📁 System                             │
│   ☑ ps -A                               │
│   ☑ free                                │
│   ☐ top -n 1                            │
│ ☑ 📁 Init Sequence                      │
│   ☑ [Macro] Init Sequence               │
│ ☑ (Ungrouped)                           │
│   ☑ reboot                              │
│                                         │
├─────────────────────────────────────────┤
│ Selected: 4 / 5 commands                │
│                    [Cancel]   [Export]   │
└─────────────────────────────────────────┘
```

交互细节：
- 勾选分组 checkbox → 全选/全不选该分组下所有命令
- 子命令部分勾选时分组 checkbox 显示 indeterminate 状态（`[-]`）
- "Select All" 控制全局
- 底部实时显示已选数量
- 导出时只包含选中命令及其所属分组

#### 导入预览 + 冲突处理对话框

选择文件后弹出模态框，展示即将导入的内容和冲突：

```
┌─────────────────────────────────────────┐
│ Import Commands                      ✕  │
├─────────────────────────────────────────┤
│                                         │
│ File: my_commands.json (5 commands)     │
│                                         │
│ ☑ 📁 System                             │
│   ⚠ ps -A          [Skip] [Overwrite]  │  ← 冲突：同名命令已存在
│   ☑ free                                │  ← 新命令，直接导入
│ ☑ 📁 Debug                              │
│   ☑ trace on                            │
│   ☑ trace off                           │
│ ☑ (Ungrouped)                           │
│   ☑ reboot         [Skip] [Overwrite]  │  ← 冲突
│                                         │
│ ─────────────────────────────────────── │
│ Conflict strategy:                      │
│   (●) Ask per item (above)              │
│   ( ) Skip all duplicates               │
│   ( ) Overwrite all duplicates          │
│                                         │
├─────────────────────────────────────────┤
│ New: 3  Conflicts: 2  Skip: 0           │
│                    [Cancel]   [Import]  │
└─────────────────────────────────────────┘
```

交互细节：
- 冲突检测规则：`name` + `type` + `command`（单条）或 `name` + `type`（宏）相同视为重复
- 每个冲突项可单独选择 Skip / Overwrite
- 底部提供全局策略快捷切换（切换后批量更新所有冲突项状态）
- 非冲突项默认勾选导入，也可取消
- 分组冲突（同名分组已存在）：自动合并，命令追加到已有分组末尾
- 底部统计实时更新

### 2.5 i18n 新增 key

```
quick_commands.rename_group              → "Rename Group" / "重命名分组"
quick_commands.delete_group              → "Delete Group" / "删除分组"
quick_commands.confirm_delete_group      → "Delete group \"{{name}}\"? Commands will be ungrouped."
quick_commands.rename_prompt             → "Enter new group name:"
quick_commands.drag_command              → "Drag to reorder"
quick_commands.export_title              → "Export Commands" / "导出指令"
quick_commands.import_title              → "Import Commands" / "导入指令"
quick_commands.select_all                → "Select All" / "全选"
quick_commands.selected_count            → "Selected: {{selected}} / {{total}} commands"
quick_commands.conflict_found            → "Conflicts: {{count}}"
quick_commands.conflict_skip             → "Skip" / "跳过"
quick_commands.conflict_overwrite        → "Overwrite" / "覆盖"
quick_commands.strategy_per_item         → "Ask per item" / "逐项选择"
quick_commands.strategy_skip_all         → "Skip all duplicates" / "跳过所有重复"
quick_commands.strategy_overwrite_all    → "Overwrite all duplicates" / "覆盖所有重复"
quick_commands.import_summary            → "New: {{new}}  Conflicts: {{conflicts}}  Skip: {{skip}}"
quick_commands.ungrouped                 → "(Ungrouped)" / "(未分组)"
```

## 3. 实现计划

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| S1 | 分组元数据存储 + load/save/ensure | 0.5d |
| S2 | 分组重命名 + 删除 + 右键菜单 | 0.5d |
| S3 | 分组拖拽排序 + 命令项拖拽排序 | 0.5d |
| S4 | 选择性导出对话框 | 0.5d |
| S5 | 导入预览 + 冲突处理对话框 | 1d |
| S6 | i18n + 测试 | 0.5d |

总计 **3.5 人天**。

## 4. 测试用例

### 4.1 分组元数据存储

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T01 | loadGroupMeta 无数据 | localStorage 无 key | 返回 `[]` |
| T02 | loadGroupMeta 异常 JSON | 存入非法 JSON | 返回 `[]`，不抛异常 |
| T03 | saveGroupMeta 正确存储 | 保存 `[{name:"A",order:0}]` | localStorage 写入正确 |
| T04 | saveGroupMeta 处理异常 | setItem 抛异常 | 不崩溃 |
| T05 | ensureGroupMeta 补全缺失 | 命令有 group="X" 但元数据无 | 自动追加 |
| T06 | ensureGroupMeta 清理孤立 | 元数据有 "Y" 但无命令引用 | 移除 "Y" |

### 4.2 分组重命名

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T07 | 正常重命名 | 输入 "NewName" 确认 | 分组名和所有命令 group 字段同步更新 |
| T08 | 重命名为空串 | 输入空串 | 不执行，保持原名 |
| T09 | 重命名为已有分组名 | 输入 "System" | 两组合并 |
| T10 | 取消重命名 | prompt 返回 null | 无操作 |
| T11 | 重命名后 UI 刷新 | 完成重命名 | 侧边栏立即更新 |

### 4.3 分组删除

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T12 | 正常删除 | 确认删除 | 分组消失，命令移至未分组 |
| T13 | 取消删除 | confirm 返回 false | 无操作 |
| T14 | 删除后命令 group 清空 | 删除 "Init" | 原属命令 group 变 null |
| T15 | 删除后元数据同步 | 删除 | groupMeta 移除对应条目 |

### 4.4 分组拖拽排序

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T16 | 拖拽分组到新位置 | 拖 "Init" 到 "System" 上方 | 顺序变为 Init → System，order 更新 |
| T17 | 刷新后保持顺序 | 拖拽后刷新 | 顺序不变 |
| T18 | 拖拽不影响命令归属 | 拖拽分组 | 命令 group 字段不变 |

### 4.5 命令项拖拽排序

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T19 | 同分组内排序 | 拖 "ps" 到 "free" 下方 | order 更新 |
| T20 | 跨分组拖拽 | 拖 "ps" 从 "System" 到 "Init" | group 变为 "Init" |
| T21 | 拖到未分组区域 | 拖出分组 | group 变 null |
| T22 | 从未分组拖入分组 | 拖入 "System" | group 变 "System" |
| T23 | 拖拽后持久化 | 刷新页面 | 顺序保持 |

### 4.6 分组右键菜单

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T24 | 右键显示菜单 | 右键分组 header | 显示 Rename / Delete 菜单 |
| T25 | 菜单定位正确 | 右键 | left/top = clientX/clientY |
| T26 | 超出视口自动调整 | 右下角右键 | 不超出 window |
| T27 | 点击空白关闭 | 点击其他区域 | 菜单隐藏 |
| T28 | 与命令菜单互斥 | 先开命令菜单再右键分组 | 命令菜单关闭 |

### 4.7 选择性导出

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T29 | 打开导出对话框 | 点击 Export | 弹出模态框，所有命令默认勾选 |
| T30 | 全选/全不选 | 点击 "Select All" | 所有 checkbox 联动切换 |
| T31 | 分组 checkbox 联动 | 取消勾选分组 | 该分组下所有命令取消勾选 |
| T32 | 子项部分勾选 | 勾选分组下部分命令 | 分组 checkbox 显示 indeterminate |
| T33 | 选中计数实时更新 | 勾选/取消 | 底部 "Selected: x / y" 实时变化 |
| T34 | 导出选中项 | 勾选 3/5 个命令后点 Export | JSON 只含 3 个命令及其所属分组 |
| T35 | 未选中分组不导出 | 分组下命令全部取消 | 导出 JSON 的 groups 不含该分组 |
| T36 | 空选择禁止导出 | 全部取消勾选 | Export 按钮禁用 |
| T37 | 无命令时提示 | 命令列表为空 | 直接提示无可导出内容，不弹对话框 |

### 4.8 导入预览与冲突处理

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T38 | 打开导入预览 | 选择有效 JSON 文件 | 弹出预览对话框，按分组展示命令 |
| T39 | 无冲突全部导入 | 导入全新命令 | 所有项默认勾选，无冲突标记，直接导入 |
| T40 | 检测同名冲突 | 导入含已有同名命令的文件 | 冲突项显示 ⚠ 和 Skip/Overwrite 按钮 |
| T41 | 逐项选择 Skip | 点击冲突项的 Skip | 该项标记为跳过，统计更新 |
| T42 | 逐项选择 Overwrite | 点击冲突项的 Overwrite | 该项标记为覆盖，统计更新 |
| T43 | 全局策略：Skip all | 选择 "Skip all duplicates" | 所有冲突项批量设为 Skip |
| T44 | 全局策略：Overwrite all | 选择 "Overwrite all duplicates" | 所有冲突项批量设为 Overwrite |
| T45 | 全局策略切回逐项 | 选择 "Ask per item" | 恢复各冲突项独立状态 |
| T46 | 取消勾选非冲突项 | 取消某个新命令的 checkbox | 该命令不导入 |
| T47 | Skip 执行结果 | 导入时冲突项选 Skip | 本地已有命令保持不变 |
| T48 | Overwrite 执行结果 | 导入时冲突项选 Overwrite | 本地命令被导入数据覆盖（保留本地 id） |
| T49 | 同名分组自动合并 | 导入含已有分组名的数据 | 命令追加到已有分组末尾，不创建重复分组 |
| T50 | 导入新分组 | 导入含本地不存在的分组 | groupMeta 追加新分组 |
| T51 | 底部统计正确 | 操作冲突选项 | "New / Conflicts / Skip" 数字实时正确 |
| T52 | 空文件处理 | 导入 commands 为空数组的文件 | 提示无可导入内容 |
| T53 | 非法文件处理 | 导入非 JSON 或缺少 commands 字段 | 提示格式错误 |

### 4.9 边界与回归

| # | 用例 | 操作 | 预期结果 |
|---|------|------|----------|
| T54 | 无分组时无分组菜单入口 | 全部未分组 | 无分组 header |
| T55 | clearAll 清空 groupMeta | Clear All | 两个 key 均清空 |
| T56 | 新建命令选已有分组 | 下拉选 "System" | groupMeta 不变 |
| T57 | 新建命令创建新分组 | 输入 "Debug" | groupMeta 追加 |
| T58 | 特殊字符分组名 | 名为 `<script>` | HTML 转义正确，无 XSS |
