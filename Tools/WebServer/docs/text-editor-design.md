# 设备文件文本编辑器设计方案

## 1. 需求概述

在现有设备文件浏览器（File Transfer）基础上，增加文本编辑器功能：

| 需求 | 说明 |
|------|------|
| 双击打开文本文件 | 在编辑器 Tab 中预览和编辑设备上的文本文件 |
| 大文件保护 | 超过 100KB 的文本文件弹窗提示，提供"继续打开 / 立即下载 / 取消"三个选项 |
| 广泛格式支持 | 支持常见文本格式（.txt, .json, .xml, .yaml, .ini, .cfg, .log, .csv, .md, .c, .h, .cpp, .py, .sh, .js 等） |
| 右键菜单 | 新增"以文本方式打开"菜单项，可对任意文件强制以文本方式打开 |
| 图片预览保留 | 图片文件双击仍走图片预览流程，不受影响 |
| 保存回写 | 编辑后可保存回设备 |

## 2. 架构设计

### 2.1 整体流程

```
双击设备文件 / 右键"以文本方式打开"
        │
        ▼
  ┌─────────────┐
  │ 判断文件类型  │
  │ (图片/文本)   │
  └──────┬──────┘
         │
    ┌────┴────┐
    │         │
  图片      文本(或强制文本)
    │         │
    ▼         ▼
 previewDev  ┌───────────┐
 iceImage()  │ fstat 获取 │
             │ 文件大小   │
             └─────┬─────┘
                   │
            ┌──────┴──────┐
            │  size>100KB? │
            └──────┬──────┘
              yes  │  no
            ┌──────┴──────┐
            │              │
            ▼              ▼
     弹窗三选一        直接下载并
     继续打开/         打开编辑器Tab
     立即下载/取消
            │
     ┌──────┼──────┐
     │      │      │
   继续   下载    取消
   打开   到PC   (关闭)
     │      │
     ▼      ▼
   编辑器  浏览器下载
   Tab    (不打开编辑器)
```

### 2.2 模块划分

| 模块 | 文件 | 变更类型 | 说明 |
|------|------|----------|------|
| 前端：文本编辑器 | `static/js/features/transfer.js` | 修改 | 新增 `openDeviceTextFile()` 和 `saveDeviceTextFile()` 等函数 |
| 前端：设备文件列表 | `static/js/features/transfer.js` | 修改 | 修改双击行为，增加文本文件判断 |
| 前端：Tab 关闭逻辑 | `static/js/features/editor.js` | 修改 | `closeTab()` 增加 dirty 确认 |
| 前端：右键菜单 | `templates/partials/sidebar_transfer.html` | 修改 | 新增"以文本方式打开"菜单项 |
| 前端：CSS | `static/css/workbench.css` | 修改 | dirty 指示器、文本工具条样式 |
| 国际化 | `static/js/locales/en.js`, `zh-CN.js`, `zh-TW.js` | 修改 | 新增文本编辑器相关翻译 |
| 前端测试 | `tests/js/test_transfer.js` | 修改 | 新增文本编辑器相关测试 |

> 后端无任何改动。设备文件的读取和写入完全复用现有 `/api/transfer/download` 和 `/api/transfer/upload` 接口。

## 3. 详细设计

### 3.1 文本文件类型识别

定义文本文件扩展名白名单：

```javascript
const _TEXT_EXTENSIONS = [
  // 通用文本
  '.txt', '.log', '.md', '.csv', '.tsv',
  // 配置文件
  '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
  '.properties', '.env',
  // 脚本/代码
  '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx',
  '.py', '.js', '.ts', '.sh', '.bash', '.bat', '.cmd',
  '.lua', '.rb', '.pl', '.go', '.rs', '.java', '.kt',
  // Web
  '.html', '.htm', '.css', '.scss', '.less', '.svg',
  // 其他
  '.cmake', '.makefile', '.mk', '.ld', '.s', '.asm',
  '.gitignore', '.editorconfig',
];
```

判断逻辑：
- `_isTextFile(name)` — 检查扩展名是否在白名单中
- 无扩展名的文件不自动识别为文本，但可通过右键"以文本方式打开"

### 3.2 Ace Editor 模式映射

根据文件扩展名自动选择 Ace Editor 的语法高亮模式：

```javascript
function _getAceMode(fileName) {
  const ext = fileName.split('.').pop().toLowerCase();
  const modeMap = {
    'c': 'c_cpp', 'h': 'c_cpp', 'cpp': 'c_cpp', 'hpp': 'c_cpp',
    'cc': 'c_cpp', 'cxx': 'c_cpp',
    'py': 'python', 'js': 'javascript', 'ts': 'typescript',
    'json': 'json', 'xml': 'xml', 'html': 'html', 'htm': 'html',
    'css': 'css', 'scss': 'scss', 'less': 'less',
    'yaml': 'yaml', 'yml': 'yaml', 'toml': 'toml',
    'sh': 'sh', 'bash': 'sh', 'md': 'markdown',
    'sql': 'sql', 'lua': 'lua', 'rb': 'ruby',
    'go': 'golang', 'rs': 'rust', 'java': 'java',
    'ini': 'ini', 'cfg': 'ini', 'conf': 'ini',
    'cmake': 'cmake', 'makefile': 'makefile', 'mk': 'makefile',
    's': 'assembly_x86', 'asm': 'assembly_x86',
    'svg': 'svg',
  };
  return modeMap[ext] || 'text';
}
```

### 3.3 前端核心函数

#### `openDeviceTextFile(remotePath, fileName, forceText = false)`

主函数，负责打开设备文本文件：

```
1. 检查是否已有同路径的 Tab 打开 → 有则切换过去
2. 调用 statDeviceFile(remotePath) 获取文件大小
3. 如果 size > 100KB (102400):
   a. 弹出大文件确认弹窗
   b. 用户选择"继续打开" → 继续步骤 4
   c. 用户选择"立即下载" → 调用 downloadFromDevice() 触发浏览器下载，return（不打开编辑器）
   d. 用户选择"取消" → return
4. 调用 downloadFileFromDevice() 下载文件
5. 将二进制数据转为 UTF-8 文本
6. 创建编辑器 Tab（type: 'textfile'）
7. 初始化 Ace Editor，设置对应语法模式
8. Tab 标题显示文件名，带修改标记（dirty indicator）
```

#### `saveDeviceTextFile(tabId)`

保存编辑内容回设备（全量保存）：

```
1. 从 aceEditors 获取编辑器全部内容
2. 将文本编码为 UTF-8 Uint8Array
3. 构造 File 对象
4. 调用 uploadFileToDevice(file, remotePath) 全量上传覆盖
5. 上传成功后更新 originalContent 为当前内容，清除 dirty 标记
```

**保存策略：全量保存**

| 方案 | 优点 | 缺点 |
|------|------|------|
| 全量保存 | 实现简单可靠；复用现有 upload + CRC 校验；对嵌入式文件系统兼容性好 | 大文件传输耗时较长 |
| 差分保存 | 小修改时传输量少 | 需要设备端 fseek+局部写入支持；FAT/LittleFS 不保证原地覆盖可靠性；差分计算复杂度高；文件长度变化时仍需全量重写 |

选择全量保存的理由：
1. 设备端嵌入式文件系统（FAT/LittleFS）对 fseek + 局部覆盖写入的可靠性不一致
2. 文本编辑场景中插入/删除操作会导致后续内容偏移，差分实际上退化为全量重写
3. 已有 100KB 大文件保护机制，实际编辑的文件通常较小，全量传输开销可接受
4. 完全复用现有 `uploadFileToDevice()` 流程，包括分块传输、CRC 校验、重试机制，无需新增传输逻辑

#### dirty 状态追踪

```javascript
// 在 editorTabs 条目中增加字段：
{
  id: 'textfile_xxx',
  title: 'config.json',
  type: 'textfile',
  closable: true,
  remotePath: '/data/config.json',
  originalContent: '...', // 原始内容，用于比较
  dirty: false,           // 是否有未保存修改
}
```

- Ace Editor 注册 `change` 事件，比较当前内容与 `originalContent`
- dirty 时 Tab 标题显示 `●` 前缀
- 关闭 dirty Tab 时弹出确认提示

### 3.4 双击行为修改

修改 `refreshDeviceFiles()` 中的 `ondblclick` 逻辑：

```javascript
item.ondblclick = () => {
  if (entry.type === 'dir') {
    pathInput.value = item.dataset.path;
    refreshDeviceFiles();
  } else if (_isImageFile(entry.name)) {
    previewDeviceImage(item.dataset.path, entry.name);
  } else if (_isTextFile(entry.name)) {
    openDeviceTextFile(item.dataset.path, entry.name);
  }
  // 其他类型文件双击无操作
};
```

### 3.5 右键菜单扩展

在 `sidebar_transfer.html` 的 context menu 中，在 "Preview Image" 之后新增：

```html
<div class="qc-context-item" onclick="transferContextAction('openAsText')">
  <i class="codicon codicon-file-code"></i>
  <span data-i18n="transfer.open_as_text">Open as Text</span>
</div>
```

在 `showTransferContextMenu()` 中控制启用/禁用：
- 仅当选中单个文件（非目录）时启用

在 `transferContextAction()` 中增加 case：

```javascript
case 'openAsText':
  if (transferSelectedFiles.length === 1) {
    const f = transferSelectedFiles[0];
    openDeviceTextFile(f.path, f.path.split('/').pop(), true);
  }
  break;
```

### 3.6 大文件确认弹窗（复用原生 alert/confirm）

项目中统一使用原生 `alert()` / `confirm()` 弹窗，不引入自定义 modal。
由于原生 `confirm()` 只支持两个按钮，采用两步 confirm 实现三选一逻辑：

```javascript
/**
 * 大文件确认弹窗（两步 confirm）
 * @returns {'open' | 'download' | 'cancel'}
 */
function confirmLargeFile(fileName, fileSize) {
  const sizeStr = formatFileSize(fileSize);
  const msg = t('transfer.large_file_message',
    'File "{{name}}" ({{size}}) is too large for in-browser editing.\nDownload and edit locally instead?',
    { name: fileName, size: sizeStr });

  // 第一步：是否下载？
  const wantDownload = confirm(msg);
  if (wantDownload) {
    return 'download';
  }

  // 第二步：用户拒绝下载，是否仍要在浏览器中打开？
  const forceOpen = confirm(
    t('transfer.force_open_confirm',
      'Open "{{name}}" ({{size}}) in browser anyway?\nThis may be slow.',
      { name: fileName, size: sizeStr }));
  return forceOpen ? 'open' : 'cancel';
}
```

交互流程：
```
confirm("文件过大，是否下载到本地编辑？")
  ├─ 确定 → 触发浏览器下载，结束
  └─ 取消 → confirm("仍要在浏览器中打开？可能较慢")
               ├─ 确定 → 打开编辑器 Tab
               └─ 取消 → 什么都不做
```

优点：
- 零新增 HTML/CSS，完全复用项目现有弹窗风格
- 逻辑清晰，每步只做一个决策
- 测试中可直接 mock `confirm()` 返回值

### 3.7 编辑器 Tab 保存与 Ctrl+S（贴近 VS Code 体验）

#### Tab dirty 指示器

仿照 VS Code 的行为：未保存时在 Tab 文件名前显示圆点 `●`，保存后消失。

Tab HTML 结构：
```html
<div class="tab" data-tab="${tabId}">
  <i class="codicon codicon-file-code tab-icon" style="color: #e37933;"></i>
  <span class="tab-dirty-indicator" style="display: none;">●</span>
  <span class="tab-label">${fileName}</span>
  <div class="tab-close" onclick="closeTab('${tabId}', event)">
    <i class="codicon codicon-close"></i>
  </div>
</div>
```

CSS 样式：
```css
.tab-dirty-indicator {
  color: var(--vscode-foreground);
  opacity: 0.8;
  font-size: 10px;
  margin-right: 2px;
  flex-shrink: 0;
}
```

dirty 状态更新逻辑：
```javascript
function updateTabDirtyState(tabId, isDirty) {
  const state = window.FPBState;
  const tabInfo = state.editorTabs.find(t => t.id === tabId);
  if (!tabInfo) return;

  tabInfo.dirty = isDirty;

  // 更新 Tab 上的圆点显示
  const tabEl = document.querySelector(`.tab[data-tab="${tabId}"]`);
  if (tabEl) {
    const dot = tabEl.querySelector('.tab-dirty-indicator');
    if (dot) dot.style.display = isDirty ? 'inline' : 'none';

    // VS Code 风格：dirty 时关闭按钮变成圆点，hover 时恢复为 ×
    const closeBtn = tabEl.querySelector('.tab-close');
    if (closeBtn) {
      if (isDirty) {
        closeBtn.classList.add('dirty');
      } else {
        closeBtn.classList.remove('dirty');
      }
    }
  }
}
```

更进一步的 VS Code 风格 — dirty 时关闭按钮区域默认显示圆点，hover 时切回 ×：
```css
/* dirty 状态下，关闭按钮默认显示圆点 */
.tab .tab-close.dirty .codicon-close::before {
  content: '\eab8'; /* codicon circle-filled */
}
.tab .tab-close.dirty {
  opacity: 0.8;
}
/* hover 时恢复为 × */
.tab:hover .tab-close.dirty .codicon-close::before {
  content: '\ea76'; /* codicon close */
}
```

#### Ctrl+S 快捷键

在 Ace Editor 初始化后绑定 Ctrl+S 命令：

```javascript
// 在 openDeviceTextFile() 创建编辑器后
editor.commands.addCommand({
  name: 'saveToDevice',
  bindKey: { win: 'Ctrl-S', mac: 'Command-S' },
  exec: () => saveDeviceTextFile(tabId),
});
```

同时在全局层面拦截 Ctrl+S 防止浏览器默认保存行为（仅当活动 Tab 是 textfile 类型时）：

```javascript
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    const state = window.FPBState;
    const activeTab = state.editorTabs.find(t => t.id === state.activeEditorTab);
    if (activeTab && activeTab.type === 'textfile') {
      e.preventDefault();
      saveDeviceTextFile(activeTab.id);
    }
  }
});
```

#### 关闭 dirty Tab 确认

修改 `closeTab()` 函数，在关闭 `textfile` 类型且 dirty 的 Tab 时弹出确认：

```javascript
// 在 closeTab() 函数开头增加
const tabInfo = state.editorTabs.find(t => t.id === tabId);
if (tabInfo && tabInfo.type === 'textfile' && tabInfo.dirty) {
  const discard = confirm(
    t('transfer.unsaved_changes',
      '"{{name}}" has unsaved changes. Discard?',
      { name: tabInfo.title }));
  if (!discard) return;
}
```

#### 文本文件工具条

在 Tab content 内部顶部添加轻量工具条，显示文件路径和操作按钮：

```html
<div class="textfile-toolbar">
  <span class="textfile-path" title="${remotePath}">${remotePath}</span>
  <div class="textfile-actions">
    <button onclick="saveDeviceTextFile('${tabId}')" title="Save to device (Ctrl+S)">
      <i class="codicon codicon-save"></i>
    </button>
    <button onclick="downloadTextFileLocal('${tabId}')" title="Download to PC">
      <i class="codicon codicon-desktop-download"></i>
    </button>
  </div>
</div>
```

```css
.textfile-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: var(--vscode-titlebar-bg);
  border-bottom: 1px solid var(--vscode-panel-border);
  font-size: 11px;
  flex-shrink: 0;
}

.textfile-path {
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: "Consolas", "Courier New", monospace;
}

.textfile-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.textfile-actions button {
  background: none;
  border: none;
  color: var(--vscode-foreground);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 3px;
  opacity: 0.7;
}

.textfile-actions button:hover {
  opacity: 1;
  background: var(--vscode-list-hover);
}
```

### 3.8 国际化 (i18n)

新增翻译 key：

| Key | EN | ZH-CN |
|-----|----|-------|
| `transfer.open_as_text` | Open as Text | 以文本方式打开 |
| `transfer.large_file_title` | Large File | 文件过大 |
| `transfer.large_file_message` | File "{{name}}" ({{size}}) is too large for in-browser editing. Download and edit locally instead? | 文件 "{{name}}" ({{size}}) 过大，不适合在浏览器中编辑。是否下载到本地编辑？ |
| `transfer.force_open_confirm` | Open "{{name}}" ({{size}}) in browser anyway? This may be slow. | 仍要在浏览器中打开 "{{name}}" ({{size}})？可能较慢。 |
| `transfer.continue_open` | Continue Open | 继续打开 |
| `transfer.saving` | Saving to device... | 正在保存到设备... |
| `transfer.save_success` | Saved: {{name}} | 已保存: {{name}} |
| `transfer.save_failed` | Save failed: {{error}} | 保存失败: {{error}} |
| `transfer.unsaved_changes` | "{{name}}" has unsaved changes. Discard? | "{{name}}" 有未保存的修改，确定丢弃？ |
| `transfer.file_too_large_hint` | File is too large for in-browser editing | 文件过大，不适合在浏览器中编辑 |

## 4. 对现有功能的影响

### 4.1 图片预览（无影响）

双击判断优先级：目录 > 图片 > 文本 > 其他。图片文件仍走 `previewDeviceImage()` 流程。

### 4.2 现有编辑器 Tab 系统（兼容）

新增 `type: 'textfile'` 类型的 Tab，与现有 `asm`、`c`、`preview` 类型并列。`switchEditorTab()` 和 `closeTab()` 无需修改核心逻辑，仅需：
- `switchEditorTab()`: 文本文件 Tab 不显示 inject 工具栏（已有逻辑，`isManualPatchTab` 判断）
- `closeTab()`: 增加 dirty 检查，关闭前确认

### 4.3 下载/上传流程（复用）

完全复用 `downloadFileFromDevice()` 和 `uploadFileToDevice()`，不修改传输逻辑。

## 5. 测试计划

### 5.1 前端测试 (`tests/js/test_transfer.js`)

新增测试用例：

| 测试 | 说明 |
|------|------|
| `_isTextFile` 识别 | 验证各种扩展名的正确识别 |
| `_getAceMode` 映射 | 验证扩展名到 Ace 模式的映射 |
| `openDeviceTextFile` 基本流程 | mock download，验证 Tab 创建 |
| `openDeviceTextFile` 复用已打开 Tab | 验证切换到已有 Tab |
| `openDeviceTextFile` 大文件弹窗 | mock stat 返回 >100KB，mock confirm 返回值，验证三种路径 |
| `confirmLargeFile` 两步 confirm | mock confirm 序列，验证 download/open/cancel 返回值 |
| `saveDeviceTextFile` 保存流程 | mock upload，验证调用 |
| dirty 状态追踪 | 验证修改后 dirty=true，保存后 dirty=false |
| updateTabDirtyState | 验证 DOM 圆点显示/隐藏、close 按钮 dirty class |
| Ctrl+S 快捷键 | 模拟 keydown 事件，验证 saveDeviceTextFile 被调用 |
| 关闭 dirty Tab 确认 | mock confirm，验证 dirty Tab 关闭前弹出确认 |
| 右键菜单 openAsText | 验证 context action 调用 |

### 5.2 后端测试

无新增后端 API，无需新增后端测试。

### 5.3 CI 自测命令

按照 `ci.yml` 的 upper-machine 流程：

```bash
# 代码格式检查
cd Tools/WebServer && ./format.sh --check --lint

# 后端测试
cd Tools/WebServer && python tests/run_tests.py --coverage --html --target 85

# 前端测试
cd Tools/WebServer && npm install && node tests/test_frontend.js --coverage --ci --threshold 80
```

## 6. 实现步骤

1. **transfer.js** — 新增 `_isTextFile()`, `_getAceMode()`, `openDeviceTextFile()`, `saveDeviceTextFile()`, `downloadTextFileLocal()`, `confirmLargeFile()`, `updateTabDirtyState()` 函数
2. **transfer.js** — 修改 `refreshDeviceFiles()` 双击逻辑、`showTransferContextMenu()` 菜单项控制、`transferContextAction()` 新增 case
3. **editor.js** — 修改 `closeTab()` 增加 dirty 确认逻辑
4. **sidebar_transfer.html** — 右键菜单新增 "Open as Text" 项
5. **workbench.css** — 新增 `.tab-dirty-indicator`、`.tab-close.dirty`、`.textfile-toolbar` 样式
6. **app.js** — 注册全局 Ctrl+S 拦截
7. **locales/en.js, zh-CN.js, zh-TW.js** — 新增翻译
8. **tests/js/test_transfer.js** — 新增测试用例
9. **CI 自测** — 运行 format + lint + 前后端测试
