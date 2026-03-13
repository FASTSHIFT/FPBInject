# FPBInject WebServer 前端 UI 升级方案

## 1. 现状分析

### 1.1 技术栈

| 层面 | 当前方案 |
|------|----------|
| CSS | 手写原生 CSS，3112 行 `workbench.css` + 398 行 `tutorial.css` |
| HTML | Jinja2 模板 + `{% include %}` partials |
| JS | Vanilla JS，全局 `window` 对象通信，`innerHTML` 拼接 |
| 构建 | 无打包工具，`<script>` 标签顺序加载 |
| 主题 | `--vscode-*` CSS 变量，`[data-theme]` 切换 |
| 图标 | `@vscode/codicons` 0.0.32 (CDN) |
| 编辑器 | Ace Editor 1.32.6 (CDN) |
| 终端 | xterm.js 5.3.0 (CDN) |

### 1.2 组件清单（全部手写）

| 组件 | 实现方式 | 痛点 |
|------|----------|------|
| 按钮 | `<button class="vscode-btn">` | 样式单一，无 loading/icon 变体 |
| 输入框 | `<input class="vscode-input">` | 无验证反馈、无前缀/后缀 |
| 下拉框 | `<select class="vscode-select">` | 原生 select 无法自定义样式，各平台不一致 |
| 模态框 | `.modal-overlay` + JS 切换 | 无动画、无 ESC 关闭、无焦点陷阱 |
| 右键菜单 | `.qc-context-menu` + 手动定位 | 无子菜单、无溢出检测 |
| Tab | `.panel-tab` + `.active` 类切换 | 无键盘导航、无关闭动画 |
| 进度条 | `.progress-bar` + JS 设 width | 无不确定态、无标签 |
| 树形视图 | JS 手动构建 DOM | 无虚拟滚动、大数据量卡顿 |
| 通知 | `alert()` / 自定义 `showNotification()` | `alert()` 阻塞线程 |
| 复选框 | 原生 `<input type="checkbox">` | 仅靠 `accent-color`，样式受限 |
| 折叠面板 | `<details>/<summary>` | 无动画过渡 |
| 文件列表 | JS `createElement` 循环 | 无虚拟滚动、无拖拽排序 |
| Tooltip | 无 | 仅靠 `title` 属性，样式不可控 |

### 1.3 核心优势（需保留）

- VS Code 风格的视觉一致性
- 零框架依赖，加载快
- Codicons 图标体系
- CSS 变量驱动的主题系统
- Ace Editor / xterm.js 等专业组件

### 1.4 核心问题

1. **原生 `<select>` 无法定制** — 各平台渲染不同，暗色主题下尤其突兀
2. **`alert()` / `prompt()` / `confirm()` 阻塞** — 打断用户流程，样式不可控
3. **无 Tooltip 组件** — `title` 属性延迟高、样式固定
4. **右键菜单简陋** — 无子菜单、无分隔线、无图标
5. **树形视图无虚拟滚动** — 大量符号/文件时性能差
6. **模态框无无障碍支持** — 无焦点陷阱、无 ARIA 属性
7. **CSS 3100+ 行单文件** — 维护困难

## 2. 组件库选型

### 2.1 候选方案对比

| 维度 | Shoelace / Web Awesome | Radix Primitives | 自研改进 |
|------|----------------------|------------------|----------|
| 技术 | Web Components (Lit) | React only | Vanilla JS |
| 框架依赖 | 无，原生 Custom Elements | 需要 React | 无 |
| CDN 使用 | ✅ 两行引入即可 | ❌ 需打包 | N/A |
| 暗色主题 | ✅ 内置 | ✅ | 已有 |
| 自定义样式 | ✅ CSS Parts + Variables | ✅ | 完全控制 |
| 无障碍 | ✅ ARIA 内置 | ✅ | 需手动 |
| 包体积 | ~80KB (autoloader 按需) | 需 React 运行时 | 0 |
| 迁移成本 | 中（渐进替换） | 高（需引入 React） | 低 |
| 组件丰富度 | 60+ 组件 | 30+ 原语 | 按需开发 |
| 维护状态 | Shoelace → Web Awesome 演进 | 活跃 | 自维护 |

### 2.2 推荐方案：Shoelace (Web Awesome) + 自研补充

**理由：**

1. **Web Components 标准** — 与现有 Vanilla JS 架构完美兼容，无需引入框架
2. **CDN 即用** — 两行代码引入，与现有 CDN 加载模式一致
3. **渐进式迁移** — 可逐个组件替换，不需要一次性重写
4. **暗色主题内置** — 可映射到现有 `--vscode-*` CSS 变量
5. **Autoloader** — 按需加载，只加载页面用到的组件，不影响首屏性能

## 3. 迁移计划

### 3.1 Phase 0：基础设施（预计 0.5 天）

引入 Shoelace CDN，配置主题变量映射：

```html
<!-- base.html -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/themes/dark.css" />
<script type="module" src="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/shoelace-autoloader.js"></script>
```

```css
/* 主题变量映射 */
:root {
  --sl-color-primary-600: var(--vscode-button-bg, #007acc);
  --sl-color-neutral-0: var(--vscode-background, #1e1e1e);
  --sl-color-neutral-50: var(--vscode-sidebar-bg, #252526);
  --sl-input-background-color: var(--vscode-input-bg, #3c3c3c);
  --sl-input-border-color: var(--vscode-input-border, #3c3c3c);
  --sl-font-sans: var(--vscode-font-family);
  --sl-font-size-medium: 13px;
  --sl-border-radius-medium: 2px;
}
```

### 3.2 Phase 1：高收益替换（预计 2-3 天）

优先替换视觉提升最明显、迁移成本最低的组件：

| 原生组件 | 替换为 | 收益 |
|----------|--------|------|
| `<select>` | `<sl-select>` + `<sl-option>` | 暗色主题一致、可搜索、多选 |
| `alert()` / `confirm()` | `<sl-dialog>` | 非阻塞、主题一致、动画 |
| `prompt()` | `<sl-dialog>` + `<sl-input>` | 同上 |
| `title="..."` | `<sl-tooltip>` | 即时显示、可定制样式 |
| 自定义右键菜单 | `<sl-menu>` + `<sl-menu-item>` | 子菜单、图标、分隔线、键盘导航 |

**示例 — Select 替换：**

```html
<!-- 之前 -->
<select class="vscode-select" id="portSelect">
  <option value="">Select port...</option>
</select>

<!-- 之后 -->
<sl-select id="portSelect" placeholder="Select port..." size="small">
  <sl-option value="/dev/ttyUSB0">/dev/ttyUSB0</sl-option>
</sl-select>
```

**示例 — confirm 替换：**

```javascript
// 之前
if (!confirm('Are you sure?')) return;

// 之后
const confirmed = await showConfirmDialog(
  t('messages.confirm_delete', 'Are you sure?')
);
if (!confirmed) return;
```

### 3.3 Phase 2：交互增强（预计 2-3 天）

| 原生组件 | 替换为 | 收益 |
|----------|--------|------|
| `.vscode-btn` | `<sl-button>` | loading 态、icon slot、尺寸变体 |
| `.vscode-input` | `<sl-input>` | 前缀/后缀图标、clearable、密码切换 |
| `<input type="checkbox">` | `<sl-checkbox>` / `<sl-switch>` | 统一样式、动画 |
| `.progress-bar` | `<sl-progress-bar>` | 不确定态、标签、动画 |
| `showNotification()` | `<sl-alert>` (toast) | 自动关闭、图标、多类型 |
| `<details>` 折叠 | `<sl-details>` | 平滑动画、图标自定义 |

### 3.4 Phase 3：高级组件（预计 3-5 天）

| 场景 | 方案 | 收益 |
|------|------|------|
| 符号/文件树 | `<sl-tree>` + `<sl-tree-item>` | 内置展开/折叠、选中、懒加载 |
| Tab 系统 | `<sl-tab-group>` + `<sl-tab>` | 键盘导航、可关闭、滚动 |
| 文件浏览器 | `<sl-breadcrumb>` + `<sl-tree>` | 路径导航 + 树形浏览 |
| 拖拽上传 | 保留自研 + `<sl-progress-bar>` | 进度可视化增强 |

### 3.5 不替换的部分

以下组件保持现状，不做替换：

| 组件 | 原因 |
|------|------|
| Ace Editor | 专业代码编辑器，无可替代 |
| xterm.js | 专业终端模拟器，无可替代 |
| Activity Bar | 高度定制的 VS Code 布局，替换无收益 |
| Status Bar | 同上 |
| Title Bar | 同上 |
| Sash 拖拽分隔 | 自研逻辑与布局深度耦合 |
| CSS Grid 布局 | 工作台骨架布局，无需改动 |
| Codicons 图标 | 与 VS Code 风格一致，保留 |

## 4. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| Shoelace 停止维护 | 中 | 已演进为 Web Awesome，社区活跃；Web Components 标准不会过时 |
| CDN 不可用 | 高 | 可本地化部署 Shoelace 资源到 `static/lib/` |
| 主题不匹配 | 中 | Phase 0 先做变量映射验证，确保视觉一致 |
| 事件模型差异 | 中 | Web Components 使用 `CustomEvent`，需适配现有 `onclick` 绑定 |
| 包体积增加 | 低 | Autoloader 按需加载，实测首屏增加 ~30KB gzip |
| 测试用例失效 | 中 | 每个 Phase 完成后运行全量测试，逐步更新选择器 |

## 5. 预期收益

| 维度 | 改善 |
|------|------|
| 视觉一致性 | `<select>` / `confirm()` / `tooltip` 等原生组件不再破坏暗色主题 |
| 交互体验 | 非阻塞对话框、平滑动画、键盘导航 |
| 无障碍 | ARIA 属性内置，焦点管理自动化 |
| 开发效率 | 减少手写 CSS，组件开箱即用 |
| 可维护性 | 组件职责清晰，减少 `workbench.css` 体积 |
| 跨平台一致 | Web Components 渲染不依赖平台原生控件 |

## 6. 总结

当前项目的 VS Code 风格布局骨架（Grid + Activity Bar + Sidebar + Editor + Panel）设计良好，无需改动。升级重点在于将**原生表单控件**和**阻塞式对话框**替换为 Shoelace Web Components，以获得主题一致性、交互动画和无障碍支持。

推荐采用渐进式迁移策略，按 Phase 0-3 分步执行，每步独立可验证，总工期约 **8-12 天**。
