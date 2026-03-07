# Serial Quick Command Design

## 1. 背景与动机

当前 WebServer 的串口终端基于 xterm.js，用户只能逐字符手动输入命令。在嵌入式调试场景中，存在以下痛点：

- **重复输入**：调试时需要反复执行相同命令（如 `ps`、`free`、`top`）
- **组合操作**：某些调试流程需要按顺序执行多条命令，且命令间需要等待设备响应
- **手速依赖**：时序敏感的操作（如快速连续发送初始化序列）难以手动完成
- **知识传递**：团队成员间无法方便地共享常用调试命令集

## 2. 功能概述

新增「快捷指令」功能，支持：

| 能力 | 说明 |
|------|------|
| 单条快捷命令 | 一键发送预设串口命令 |
| 命令组合（宏） | 按顺序执行多条命令，支持自定义延迟 |
| 命令管理 | 增删改查、拖拽排序、分组管理 |
| 导入/导出 | JSON 格式，便于团队共享 |
| 快捷键绑定 | 支持为常用命令绑定键盘快捷键 |

## 3. 交互设计

### 3.1 入口与布局

在侧边栏新增 **QUICK COMMANDS** section，位于 CONNECTION 和 DEVICE INFO 之间：

```
┌─────────────────────────────┐
│ ▶ CONNECTION                │
├─────────────────────────────┤
│ ▼ QUICK COMMANDS    [+] [▶] │  ← 新增 section
│ ┌─────────────────────────┐ │
│ │ 📁 System               │ │  ← 分组
│ │   ▸ ps                  │ │  ← 单条命令
│ │   ▸ free                │ │
│ │   ▸ top -n 1            │ │
│ │ 📁 Init Sequence        │ │
│ │   ▸ [3 commands, 1.5s]  │ │  ← 命令组合（宏）
│ │ ▸ reboot                │ │  ← 未分组命令
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ▶ DEVICE INFO               │
└─────────────────────────────┘
```

header 区域按钮：
- `[+]` — 新建命令/宏
- `[▶]` — 执行选中项

### 3.2 命令列表交互

#### 单条命令项

```
┌──────────────────────────────────────┐
│ ▸ ps -A                    [▶] [⋯]  │
└──────────────────────────────────────┘
```

- **单击** → 选中（高亮）
- **双击** → 立即执行
- **右键 / `[⋯]`** → 上下文菜单（编辑、复制、删除、绑定快捷键）
- **拖拽** → 排序 / 移入分组
- **`[▶]`** → 悬停时显示，点击执行

#### 命令组合（宏）项

```
┌──────────────────────────────────────┐
│ ▸ Init Sequence [3 cmds]   [▶] [⋯]  │
│   展开后：                            │
│   1. echo "start"          0ms       │
│   2. config load           500ms     │
│   3. app run               1000ms    │
└──────────────────────────────────────┘
```

- 折叠时显示命令数量和总延迟
- 展开后显示每条子命令及其前置延迟
- 执行时在终端面板实时显示进度

### 3.3 新建/编辑命令 — 模态框

点击 `[+]` 或编辑时弹出模态框，根据类型切换两种模式：

#### 模式 A：单条命令

```
┌─────────────────────────────────────────┐
│ New Quick Command                    ✕  │
├─────────────────────────────────────────┤
│                                         │
│ Type:  (●) Single Command               │
│        ( ) Command Macro                │
│                                         │
│ Name:  [ps -A________________]          │
│                                         │
│ Command:                                │
│ [ps -A\n_____________________]          │
│                                         │
│ ☐ Append newline (\n)                   │
│                                         │
│ Group:  [System__________ ▾]            │
│                                         │
│ Shortcut: [ Click to bind... ]          │
│                                         │
├─────────────────────────────────────────┤
│                    [Cancel]    [Save]    │
└─────────────────────────────────────────┘
```

关键交互细节：

- **Name** 自动从 Command 内容推导，用户可覆盖
- **Command** 输入框支持 `\n`、`\r`、`\t`、`\x1b` 等转义字符的可视化显示
- **Append newline** 默认勾选，大多数命令需要回车结尾
- **Group** 下拉框列出已有分组 + "New Group..." 选项
- **Shortcut** 点击后进入录制模式，按下组合键即绑定（如 `Ctrl+1`）

#### 模式 B：命令组合（宏）

```
┌─────────────────────────────────────────┐
│ New Command Macro                    ✕  │
├─────────────────────────────────────────┤
│                                         │
│ Type:  ( ) Single Command               │
│        (●) Command Macro                │
│                                         │
│ Name:  [Init Sequence________]          │
│                                         │
│ Steps:                                  │
│ ┌───┬──────────────────┬────────┬───┐   │
│ │ ≡ │ echo "start"\n   │  0 ms  │ ✕ │   │
│ │ ≡ │ config load\n    │ 500 ms │ ✕ │   │
│ │ ≡ │ app run\n        │ 1000ms │ ✕ │   │
│ └───┴──────────────────┴────────┴───┘   │
│                                         │
│ [+ Add Step]                            │
│                                         │
│ Total: 3 commands, ~1.5s               │
│                                         │
│ Group:  [Uncategorized___ ▾]            │
│ Shortcut: [ Ctrl+Shift+I ]             │
│                                         │
├─────────────────────────────────────────┤
│           [Test Run]  [Cancel]  [Save]  │
└─────────────────────────────────────────┘
```

关键交互细节：

- **`≡`** 拖拽手柄，可拖拽调整步骤顺序
- **延迟** 表示该步骤执行前的等待时间（第一步通常为 0）
- **`✕`** 删除该步骤
- **`[+ Add Step]`** 在末尾追加新步骤，自动聚焦命令输入框
- **`[Test Run]`** 试运行宏，不保存，直接在终端执行并观察效果
- **Total** 实时计算命令数和总延迟时间

### 3.4 执行反馈

命令执行时的视觉反馈：

```
单条命令执行：
  1. 命令项短暂闪烁（pulseGlow 动画）
  2. 命令文本写入串口终端（可选：以不同颜色显示用户发送的内容）

宏执行：
  1. 宏项展开，显示步骤列表
  2. 当前执行步骤高亮 + 旋转 spinner
  3. 已完成步骤显示 ✓
  4. 延迟等待时显示倒计时
  5. 全部完成后短暂显示 "✓ Done" 然后恢复

执行中状态：
  ┌──────────────────────────────────────┐
  │ ▼ Init Sequence          [■ Stop]    │
  │   ✓ echo "start"          done       │
  │   ⟳ config load           waiting... │  ← 当前步骤
  │   ○ app run               pending    │
  └──────────────────────────────────────┘
```

- 执行期间 `[▶]` 变为 `[■ Stop]`，可中断宏执行
- 中断时剩余步骤标记为 "skipped"

### 3.5 右键上下文菜单

```
┌─────────────────────┐
│ ▶ Execute            │
│ ✎ Edit               │
│ ⎘ Duplicate          │
│ ─────────────────── │
│ ⌨ Bind Shortcut...   │
│ 📁 Move to Group...  │
│ ─────────────────── │
│ ⤓ Export             │
│ ✕ Delete             │
└─────────────────────┘
```

### 3.6 导入/导出

section header 增加 `[⋯]` 菜单：

```
┌──────────────────────┐
│ ⤒ Import Commands... │  ← 打开文件选择器，接受 .json
│ ⤓ Export All...      │  ← 下载 quick_commands.json
│ ─────────────────── │
│ ✕ Clear All          │  ← 二次确认后清空
└──────────────────────┘
```

JSON 格式示例：

```json
{
  "version": 1,
  "commands": [
    {
      "id": "cmd_1",
      "name": "ps -A",
      "type": "single",
      "command": "ps -A\n",
      "group": "System",
      "shortcut": null
    },
    {
      "id": "cmd_2",
      "name": "Init Sequence",
      "type": "macro",
      "steps": [
        { "command": "echo \"start\"\n", "delay": 0 },
        { "command": "config load\n", "delay": 500 },
        { "command": "app run\n", "delay": 1000 }
      ],
      "group": "Init",
      "shortcut": "Ctrl+Shift+I"
    }
  ]
}
```

## 4. 技术方案

### 4.1 数据模型

```javascript
// QuickCommand 数据结构
{
  id: string,          // UUID
  name: string,        // 显示名称
  type: 'single' | 'macro',
  command: string,     // type=single 时的命令内容
  steps: [             // type=macro 时的步骤列表
    { command: string, delay: number }  // delay 单位 ms
  ],
  group: string | null,
  shortcut: string | null,  // 如 "Ctrl+1"
  appendNewline: boolean,   // type=single 时是否追加 \n
  order: number             // 排序权重
}
```

### 4.2 存储方案

采用 **localStorage** 存储，key 为 `fpbinject-quick-commands`：

| 方案 | 优点 | 缺点 |
|------|------|------|
| localStorage | 无需后端改动，即时生效 | 浏览器隔离，清缓存丢失 |
| 服务端 config.json | 跨浏览器共享 | 需新增 API，与设备配置耦合 |
| 独立 JSON 文件 | 可版本管理 | 需新增文件读写 API |

推荐 **localStorage 为主 + 导入/导出 JSON 为辅**。理由：

1. 快捷指令是用户个人偏好，不应与设备配置混在一起
2. 导入/导出覆盖了团队共享需求
3. 零后端改动，纯前端实现

### 4.3 文件结构

```
static/js/features/quick-commands.js   ← 主逻辑（CRUD、执行、快捷键）
templates/partials/sidebar_quick_commands.html  ← 侧边栏 section
static/js/locales/{en,zh-CN,zh-TW}.js  ← 新增 i18n key
```

不需要新增后端 API。命令发送复用现有 `/api/serial/send`。

### 4.4 命令执行引擎

```
executeCommand(cmd):
  if cmd.type === 'single':
    sendToSerial(cmd.command)
  else:  // macro
    for step in cmd.steps:
      if aborted: break
      await sleep(step.delay)
      sendToSerial(step.command)

sendToSerial(data):
  // 复用现有 sendTerminalCommand()
  fetch('/api/serial/send', { body: { data } })
```

宏执行使用 `async/await` + `setTimeout` 实现延迟，通过 `AbortController` 模式支持中断。

### 4.5 快捷键系统

```javascript
document.addEventListener('keydown', (e) => {
  const key = buildKeyString(e);  // 如 "Ctrl+1"
  const cmd = findCommandByShortcut(key);
  if (cmd && isConnected) {
    e.preventDefault();
    executeCommand(cmd);
  }
});
```

注意事项：
- 避免与浏览器/xterm.js 内置快捷键冲突
- 录制时显示冲突检测提示
- 仅在串口已连接时响应

### 4.6 转义字符处理

用户输入的命令文本需要支持转义：

| 输入 | 实际发送 | 说明 |
|------|----------|------|
| `\n` | `0x0A` | 换行 |
| `\r` | `0x0D` | 回车 |
| `\t` | `0x09` | Tab |
| `\x1b` | `0x1B` | ESC |
| `\\` | `\` | 反斜杠本身 |

在编辑框中以标签形式可视化显示：`ps -A` `↵`

## 5. 实现计划

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| P0 | 侧边栏 section + 单条命令 CRUD + 执行 | 1d |
| P1 | 命令组合（宏）编辑器 + 延迟执行引擎 | 1d |
| P2 | 分组管理 + 拖拽排序 | 0.5d |
| P3 | 快捷键绑定 + 导入/导出 | 0.5d |
| P4 | i18n + 测试用例 | 0.5d |

总计约 **3.5 人天**。

## 6. 风险与约束

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 宏执行期间设备无响应 | 后续命令发送到无响应设备 | 支持超时检测 + 手动中断 |
| 快捷键与浏览器冲突 | 快捷键无法触发 | 录制时检测冲突并警告 |
| localStorage 容量限制 (5MB) | 命令数量极多时溢出 | 单条命令数据极小，实际不会触及 |
| xterm 焦点抢占 | 快捷键被终端捕获 | 仅在终端未聚焦时响应全局快捷键 |
