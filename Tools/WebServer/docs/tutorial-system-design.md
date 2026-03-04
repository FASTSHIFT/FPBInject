# FPBInject WebServer 教学引导系统 — 技术评估方案

**编写日期**: 2026-03-04  
**版本**: v1.0

---

## 一、需求概述

### 1.1 核心目标

实现一个交互式教学引导系统，在以下场景自动/手动触发：

1. **首次启动**：`config.json` 不存在时，自动弹出引导流程
2. **手动触发**：用户点击版本号旁的教学按钮，随时重新进入引导

### 1.2 设计原则

- 替代传统文档维护，降低用户上手门槛
- 分步骤引导，每步聚焦一个功能区域
- **所有步骤均为非强制性**，包括欢迎页在内均可跳过
- 支持跳过、返回、重做
- 完整 i18n 支持（en / zh-CN / zh-TW）

---

## 二、现有系统分析

### 2.1 配置系统

| 项目 | 详情 |
|------|------|
| Schema 定义 | `core/config_schema.py`，21 个配置项，7 个分组 |
| 存储文件 | `config.json`（项目根目录） |
| 加载逻辑 | `core/state.py` → `load_config()`，文件不存在时使用默认值 |
| 保存逻辑 | `core/state.py` → `save_config()`，写入 `{"version": 1, ...}` |
| 前端 API | `GET /api/config`、`POST /api/config`、`GET /api/config/schema` |

**首次启动检测点**：`load_config()` 中已有 `os.path.exists(CONFIG_FILE)` 检查，当前仅打印日志，可扩展。

### 2.2 UI 布局（仿 VS Code Workbench）

```
┌──────────────────────────────────────────────────┐
│  TITLE BAR  [🧪 FPBInject] [v1.4.3] [🕐] [👤]  │
├────┬───────────────────┬─────────────────────────┤
│ A  │    SIDEBAR         │    EDITOR AREA          │
│ C  │  ┌─Connection      │    (Ace Editor tabs)    │
│ T  │  ├─Device Info     │                         │
│ I  │  ├─Quick Commands  │                         │
│ V  │  ├─File Transfer   ├─────────────────────────┤
│ I  │  ├─Symbols         │    TERMINAL PANEL       │
│ T  │  └─Configuration   │    OUTPUT | SERIAL      │
│ Y  │                    │                         │
├────┴───────────────────┴─────────────────────────┤
│  STATUS BAR  [● Connected] [Slot: 0] [UTF-8]    │
└──────────────────────────────────────────────────┘
```

**版本号位置**：Title Bar 左侧，`<span id="versionDisplay" class="version-badge">`，教学按钮应紧邻其右侧。

### 2.3 现有 Modal 模式

File Browser Modal 使用 `.modal-overlay` + `.modal` 结构，教学系统可复用此模式，但需要额外的步骤导航和高亮遮罩。

### 2.4 功能模块清单

| 区域 | 功能 | 关键配置项 | 教学优先级 |
|------|------|-----------|-----------|
| Connection | 串口选择、波特率、连接 | `port`, `baudrate`, `auto_connect` | ⭐⭐⭐⭐⭐ |
| Project | ELF 路径、编译数据库、工具链 | `elf_path`, `compile_commands_path`, `toolchain_path` | ⭐⭐⭐⭐⭐ |
| Inject | 注入模式、文件监视、自动编译 | `patch_mode`, `watch_dirs`, `auto_compile` | ⭐⭐⭐⭐ |
| Editor | 补丁编辑、编译、注入 | — | ⭐⭐⭐⭐ |
| Terminal | 输出日志、串口终端 | — | ⭐⭐⭐ |
| Quick Commands | 快捷指令管理 | — | ⭐⭐ |
| File Transfer | 设备文件上传/下载 | `chunk_size`, `verify_crc` | ⭐⭐ |
| Symbols | 符号搜索、反汇编 | — | ⭐⭐ |
| Device Info | FPB 信息、Ping | — | ⭐⭐ |
| Configuration | 全局设置面板 | 所有 | ⭐⭐⭐ |

### 2.5 i18n 系统

- 翻译函数：`t(key, fallback, options)` 全局可用
- Locale 文件：`static/js/locales/{en,zh-CN,zh-TW}.js`
- 结构：嵌套对象，如 `messages.xxx`、`statusbar.xxx`、`tooltips.xxx`
- 教学文本应新增 `tutorial` 命名空间

---

## 三、教学流程设计

### 3.1 引导步骤规划

```
Step 1: 欢迎页
  ├─ 项目简介 + 功能概览
  └─ 语言选择（影响后续所有步骤）

Step 2: 项目配置 ⭐
  ├─ 高亮 Sidebar → Configuration 区域
  ├─ 引导设置 ELF 路径（推荐）
  ├─ 引导设置 compile_commands.json 路径（可选）
  └─ 引导设置工具链路径（可选）

Step 3: 串口连接 ⭐
  ├─ 高亮 Sidebar → Connection 区域
  ├─ 引导选择串口 + 波特率
  └─ 引导点击连接按钮

Step 4: 注入工作流
  ├─ 高亮 Editor 区域
  ├─ 演示：打开/创建补丁文件
  ├─ 演示：编译 → 注入流程
  └─ 介绍 patch_mode 选项

Step 5: 自动注入
  ├─ 高亮 Configuration → watch_dirs
  ├─ 介绍文件监视 + 自动编译
  └─ 介绍进度条状态含义

Step 6: 辅助功能
  ├─ 快捷指令面板简介
  ├─ 文件传输功能简介
  ├─ 符号搜索功能简介
  └─ 终端面板简介

Step 7: 完成
  ├─ 配置摘要确认
  ├─ 保存配置
  └─ 提示教学按钮位置（可随时重新进入）
```

### 3.2 步骤交互模式

每个步骤采用 **Spotlight + Tooltip** 模式：

```
┌──────────────────────────────────────┐
│          半透明遮罩层                 │
│    ┌─────────────────┐               │
│    │  高亮目标区域    │ ← 无遮罩      │
│    │  (spotlight)     │               │
│    └─────────────────┘               │
│         ┌──────────────────────┐     │
│         │ 📖 步骤说明卡片       │     │
│         │                      │     │
│         │ 这是配置面板，你可以   │     │
│         │ 在这里设置 ELF 路径   │     │
│         │                      │     │
│         │ [上一步] [跳过] [下一步]│    │
│         └──────────────────────┘     │
└──────────────────────────────────────┘
```

---

## 四、技术方案

### 4.1 文件结构

```
static/
├── css/
│   └── tutorial.css              # 教学系统样式
├── js/
│   ├── features/
│   │   └── tutorial.js           # 教学系统核心逻辑
│   └── locales/
│       ├── en.js                 # +tutorial 命名空间
│       ├── zh-CN.js              # +tutorial 命名空间
│       └── zh-TW.js              # +tutorial 命名空间
templates/
└── partials/
    └── tutorial.html             # 教学 overlay HTML 结构
```

### 4.2 首次启动检测

**后端**：在 `/api/config` 响应中增加 `first_launch` 字段：

```python
# core/state.py
def load_config(self):
    self.first_launch = not os.path.exists(CONFIG_FILE)
    if self.first_launch:
        logger.info("First launch detected, tutorial will be shown")
        return
    # ... existing load logic

# app/routes/connection.py - GET /api/config
def api_config():
    return jsonify({
        **config_data,
        "first_launch": state.first_launch
    })
```

**前端**：在 `app.js` 初始化完成后检测：

```javascript
// 初始化完成后
const config = await fetch('/api/config').then(r => r.json());
if (config.first_launch) {
    startTutorial();
}
```

### 4.3 教学按钮

在 Title Bar 版本号右侧添加按钮：

```html
<!-- partials/titlebar.html -->
<span id="versionDisplay" class="version-badge"></span>
<button id="tutorialBtn" class="tutorial-btn" title="Tutorial"
        onclick="startTutorial()">
    <i class="codicon codicon-mortar-board"></i>
</button>
```

样式与版本号 badge 协调，使用 `codicon-mortar-board`（学士帽图标）。

### 4.4 核心类设计

```javascript
class Tutorial {
    constructor() {
        this.currentStep = 0;
        this.steps = [];           // TutorialStep[]
        this.overlay = null;       // 遮罩层 DOM
        this.tooltip = null;       // 说明卡片 DOM
        this.onComplete = null;    // 完成回调
    }

    // 生命周期
    start()                        // 开始教学
    next()                         // 下一步
    prev()                         // 上一步
    skip()                         // 跳过当前步骤
    finish()                       // 完成教学
    abort()                        // 中止教学

    // 渲染
    renderStep(step)               // 渲染当前步骤
    highlightElement(selector)     // 高亮目标元素
    positionTooltip(target, pos)   // 定位说明卡片
    removeHighlight()              // 移除高亮

    // 状态
    isActive()                     // 是否正在教学
    getProgress()                  // 获取进度 (current/total)
}
```

```javascript
// 步骤定义
const TutorialStep = {
    id: 'project-config',
    title: t('tutorial.step2_title'),
    content: t('tutorial.step2_content'),
    target: '#details-configuration',    // 高亮目标 CSS 选择器
    targetPanel: 'details-configuration', // 需要展开的 sidebar panel
    position: 'right',                   // tooltip 位置: top/right/bottom/left
    action: null,                        // 可选：步骤触发的动作函数
    validation: null,                    // 可选：进入下一步前的提示函数（不阻止跳过）
    canSkip: true,                       // 始终为 true，所有步骤均可跳过
};
```

### 4.5 Spotlight 实现方案

使用 CSS `clip-path` 实现镂空遮罩，避免 z-index 层级问题：

```css
.tutorial-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 10000;
    transition: clip-path 0.3s ease;
    /* clip-path 由 JS 动态计算 */
}

.tutorial-tooltip {
    position: fixed;
    z-index: 10001;
    background: var(--vscode-editor-background);
    border: 1px solid var(--vscode-focusBorder);
    border-radius: 6px;
    padding: 16px;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}
```

JS 动态计算 spotlight 区域：

```javascript
highlightElement(selector) {
    const el = document.querySelector(selector);
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const padding = 6;
    // 使用 polygon clip-path 创建镂空矩形
    this.overlay.style.clipPath = buildClipPath(rect, padding);
}
```

### 4.6 i18n 文本结构

```javascript
// 新增 tutorial 命名空间
tutorial: {
    btn_title: 'Tutorial',
    welcome_title: 'Welcome to FPBInject Workbench',
    welcome_content: 'This tutorial will guide you through the basic setup...',
    step_project_title: 'Project Configuration',
    step_project_content: 'Set your ELF firmware file path...',
    step_connect_title: 'Connect to Device',
    step_connect_content: 'Select the serial port and click Connect...',
    step_inject_title: 'Inject Workflow',
    step_inject_content: 'Open a patch file, compile and inject...',
    step_autoinject_title: 'Auto Inject',
    step_autoinject_content: 'Set watch directories for automatic...',
    step_tools_title: 'Additional Tools',
    step_tools_content: 'Quick commands, file transfer, symbols...',
    step_complete_title: 'Setup Complete!',
    step_complete_content: 'You can restart this tutorial anytime...',
    btn_next: 'Next',
    btn_prev: 'Previous',
    btn_skip: 'Skip',
    btn_finish: 'Finish',
    btn_restart: 'Restart Tutorial',
    progress: 'Step {{current}} of {{total}}',
}
```

### 4.7 教学完成标记

教学完成后在 `config.json` 中写入标记：

```json
{
    "version": 1,
    "tutorial_completed": true,
    ...
}
```

后端新增配置项（不显示在 sidebar）：

```python
ConfigItem(key="tutorial_completed", label="Tutorial Completed",
           group=ConfigGroup.UI, config_type=ConfigType.BOOLEAN,
           default=False, show_in_sidebar=False)
```

---

## 五、步骤与 UI 元素映射

| 步骤 | 高亮目标 | 需展开面板 | Tooltip 位置 | 交互动作 |
|------|---------|-----------|-------------|---------|
| 1. 欢迎 | 无（全屏卡片） | — | center | 语言选择下拉框 + 「跳过全部教程」按钮 |
| 2. 项目配置 | `#details-configuration` | Configuration | right | 引导点击 ELF 路径浏览按钮 |
| 3. 串口连接 | `#details-connection` | Connection | right | 引导选择端口 |
| 4. 注入流程 | `.editor-area` | — | left | 介绍编辑器 + 工具栏按钮 |
| 5. 自动注入 | `#configContainer` 中 watch_dirs | Configuration | right | 介绍 watch_dirs 配置 |
| 6. 辅助功能 | Activity Bar 各图标 | — | right | 依次闪烁各图标 |
| 7. 完成 | `#tutorialBtn` | — | bottom | 高亮教学按钮位置 |

---

## 六、实现计划

### Phase 1：基础框架（核心）
- [ ] Tutorial 类 + overlay/tooltip 渲染
- [ ] Spotlight clip-path 高亮
- [ ] 步骤导航（上一步/下一步/跳过/完成）
- [ ] 首次启动检测 + 自动触发
- [ ] Title Bar 教学按钮
- [ ] i18n 文本（3 语言）

### Phase 2：步骤内容
- [ ] Step 1: 欢迎页 + 语言选择
- [ ] Step 2: 项目配置引导
- [ ] Step 3: 串口连接引导
- [ ] Step 4: 注入工作流介绍
- [ ] Step 5: 自动注入介绍
- [ ] Step 6: 辅助功能概览
- [ ] Step 7: 完成页

### Phase 3：增强体验
- [ ] 步骤进度指示器（圆点/进度条）
- [ ] 键盘快捷键（Esc 退出、← → 导航）
- [ ] 窗口 resize 时重新定位
- [ ] 步骤动画过渡效果
- [ ] 深色/浅色主题适配

### 预估工作量

| 阶段 | 预估时间 |
|------|---------|
| Phase 1 | 2-3 小时 |
| Phase 2 | 1-2 小时 |
| Phase 3 | 1 小时 |
| 测试 | 1 小时 |
| **合计** | **5-7 小时** |

---

## 七、风险与注意事项

1. **z-index 冲突**：教学 overlay 需要最高层级（10000+），需确保不与现有 modal 冲突
2. **响应式布局**：sidebar 折叠/展开时 spotlight 位置需要重新计算
3. **异步操作**：某些步骤（如串口连接）涉及异步操作，需要等待结果后再允许进入下一步
4. **配置回滚**：教学中途退出时，已修改的配置应保留还是回滚，需要明确策略（建议：保留）
5. **测试覆盖**：需要为 Tutorial 类添加单元测试，保持 80% 覆盖率门槛
