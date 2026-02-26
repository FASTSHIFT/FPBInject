# 重新注入功能设计方案

## 问题描述

设备重启后所有 patch 丢失，用户需要手动修改源文件触发重新注入，多文件时操作繁琐。

## 简化方案

**核心思路**：缓存触发注入的文件路径 + 重新注入按钮，复用现有自动注入流程。

## 实现设计

### 1. 前端：缓存注入文件路径

```javascript
// static/js/features/autoinject.js

// 缓存已注入的文件路径（Set 自动去重）
let injectedFilePaths = new Set();

// 在自动注入成功后缓存路径
function onAutoInjectSuccess(filePath) {
    injectedFilePaths.add(filePath);
    updateReinjectButton();
}

// 清空缓存
function clearInjectedPaths() {
    injectedFilePaths.clear();
    updateReinjectButton();
}

// 获取缓存的文件数量
function getInjectedPathCount() {
    return injectedFilePaths.size;
}
```

### 2. 前端：重新注入按钮

```html
<!-- templates/partials/sidebar_device.html -->
<button class="vscode-btn secondary" 
        id="btn-reinject"
        onclick="reinjectAll()" 
        title="Re-inject all cached patches"
        style="display: none;">
    <i class="codicon codicon-sync"></i>
</button>
```

### 3. 前端：重新注入逻辑

```javascript
// static/js/features/autoinject.js

// 更新按钮显示状态
function updateReinjectButton() {
    const btn = document.getElementById('btn-reinject');
    if (!btn) return;
    
    const count = injectedFilePaths.size;
    btn.style.display = count > 0 ? 'inline-flex' : 'none';
    btn.title = t('tooltips.reinject_all', { count });
}

// 重新注入所有缓存的文件
async function reinjectAll() {
    const paths = Array.from(injectedFilePaths);
    
    if (paths.length === 0) {
        showPopup('info', t('messages.no_inject_cache'));
        return;
    }
    
    log.info(t('messages.reinject_start', { count: paths.length }));
    
    let successCount = 0;
    let failCount = 0;
    
    for (const filePath of paths) {
        try {
            // 复用现有的自动注入流程
            await triggerAutoInject(filePath);
            successCount++;
        } catch (e) {
            log.error(`Re-inject failed: ${filePath} - ${e.message}`);
            failCount++;
        }
    }
    
    // 显示结果
    if (failCount === 0) {
        showPopup('success', t('messages.reinject_success', { count: successCount }));
    } else {
        showPopup('warning', t('messages.reinject_partial', { success: successCount, fail: failCount }));
    }
}

// 触发单个文件的自动注入（复用现有逻辑）
async function triggerAutoInject(filePath) {
    // 调用现有的 /api/autoinject/trigger 接口
    const response = await fetch('/api/autoinject/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
    });
    
    const result = await response.json();
    if (!result.success) {
        throw new Error(result.error || 'Unknown error');
    }
    return result;
}
```

### 4. i18n 翻译键

```javascript
// en.js
tooltips: {
    reinject_all: 'Re-inject all ({{count}} files)',
},
messages: {
    no_inject_cache: 'No injection cache available',
    reinject_start: 'Re-injecting {{count}} file(s)...',
    reinject_success: 'Re-injection complete: {{count}} succeeded',
    reinject_partial: 'Re-injection: {{success}} succeeded, {{fail}} failed',
}

// zh-CN.js
tooltips: {
    reinject_all: '重新注入全部 ({{count}} 个文件)',
},
messages: {
    no_inject_cache: '没有可重新注入的缓存',
    reinject_start: '正在重新注入 {{count}} 个文件...',
    reinject_success: '重新注入完成：{{count}} 个成功',
    reinject_partial: '重新注入：{{success}} 个成功，{{fail}} 个失败',
}

// zh-TW.js
tooltips: {
    reinject_all: '重新注入全部 ({{count}} 個檔案)',
},
messages: {
    no_inject_cache: '沒有可重新注入的快取',
    reinject_start: '正在重新注入 {{count}} 個檔案...',
    reinject_success: '重新注入完成：{{count}} 個成功',
    reinject_partial: '重新注入：{{success}} 個成功，{{fail}} 個失敗',
}
```

## 实现步骤

### Step 1: 修改 autoinject.js - 添加缓存逻辑 ✅

在自动注入成功的回调中添加文件路径缓存。

### Step 2: 修改 sidebar_device.html - 添加按钮 ✅

在设备信息面板添加重新注入按钮（🔄 图标），初始隐藏。

### Step 3: 添加 i18n 翻译键 ✅

在三个语言文件中添加相关翻译。

### Step 4: 后端添加触发接口 ✅

添加 `/api/autoinject/trigger` 接口支持手动触发指定文件。

## UI 效果

```
┌─────────────────────────────────────┐
│  DEVICE INFO                        │
├─────────────────────────────────────┤
│  [Ping] [Get Info] [🔄]             │  ← 有缓存时显示
│  [Clear All] [Throughput]           │
└─────────────────────────────────────┘
```

按钮 hover 提示：`重新注入全部 (3 个文件)`

## 注意事项

1. **缓存生命周期**：页面刷新后缓存清空（仅内存缓存，简单可靠）
2. **文件去重**：使用 Set 自动去重，同一文件多次注入只记录一次
3. **复用现有流程**：不新增后端逻辑，直接调用现有自动注入接口
4. **源文件变更**：如果源文件被修改，重新注入会使用最新内容
