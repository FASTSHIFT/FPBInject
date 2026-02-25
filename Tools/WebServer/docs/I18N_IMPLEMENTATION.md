# FPBInject WebServer 多语言支持技术评估

## 1. 需求概述

- 支持语言：简体中文 (zh-CN)、繁体中文 (zh-TW)、英文 (en)
- 翻译范围：UI 标签、按钮、提示信息、配置项标签/tooltip
- 不翻译：日志输出（保持英文便于调试）
- 用户可在配置面板切换语言

## 2. 技术选型

### 2.1 框架选择：i18next

选择 i18next 的原因：
- 业界最流行的 JavaScript 国际化框架
- 支持浏览器端直接使用（无需构建工具）
- 支持命名空间、插值、复数等高级特性
- 轻量级，CDN 可用
- 活跃维护，文档完善

### 2.2 CDN 引入

```html
<script src="https://unpkg.com/i18next@23.11.5/i18next.min.js"></script>
```

备选本地化方案：下载到 `/static/js/lib/i18next.min.js`

## 3. 实现方案

### 3.1 目录结构

```
static/js/
├── locales/
│   ├── en.js          # 英文翻译
│   ├── zh-CN.js       # 简体中文翻译
│   └── zh-TW.js       # 繁体中文翻译
├── core/
│   └── i18n.js        # i18n 初始化和工具函数
```

### 3.2 翻译文件格式

```javascript
// locales/en.js
window.i18nResources = window.i18nResources || {};
window.i18nResources['en'] = {
  translation: {
    // 侧边栏
    sidebar: {
      connection: 'CONNECTION',
      config: 'CONFIG',
      explorer: 'EXPLORER'
    },
    // 配置组
    config: {
      groups: {
        project: 'Project Paths',
        inject: 'Injection',
        transfer: 'Transfer',
        logging: 'Logging',
        tools: 'Analysis Tools'
      }
    },
    // 按钮
    buttons: {
      connect: 'Connect',
      disconnect: 'Disconnect',
      inject: 'Inject',
      compile: 'Compile'
    }
  }
};
```

### 3.3 配置项

在 `config_schema.py` 添加语言配置：

```python
ConfigItem(
    key="ui_language",
    label="Language",
    group=ConfigGroup.CONNECTION,  # 放在连接组但显示在侧边栏
    config_type=ConfigType.SELECT,
    default="en",
    tooltip="UI display language",
    options=[
        ("en", "English"),
        ("zh-CN", "简体中文"),
        ("zh-TW", "繁體中文"),
    ],
    show_in_sidebar=True,
    order=100,  # 放在最后
)
```

### 3.4 HTML 元素标记

使用 `data-i18n` 属性标记需要翻译的元素：

```html
<span data-i18n="sidebar.connection">CONNECTION</span>
<button data-i18n="buttons.connect">Connect</button>
<input placeholder="..." data-i18n="[placeholder]input.search">
```

### 3.5 初始化流程

```javascript
// core/i18n.js
async function initI18n(language = 'en') {
  await i18next.init({
    lng: language,
    fallbackLng: 'en',
    resources: window.i18nResources
  });
  
  // 翻译所有标记元素
  translatePage();
}

function translatePage() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (key.startsWith('[')) {
      // 属性翻译 [placeholder]key
      const match = key.match(/\[(\w+)\](.+)/);
      if (match) {
        el.setAttribute(match[1], i18next.t(match[2]));
      }
    } else {
      el.textContent = i18next.t(key);
    }
  });
}

function changeLanguage(lng) {
  i18next.changeLanguage(lng).then(() => {
    translatePage();
  });
}
```

## 4. 实现步骤

### Phase 1: 基础设施
1. 添加 i18next 库引用
2. 创建 `core/i18n.js` 初始化模块
3. 创建翻译文件目录和基础翻译
4. 添加语言配置项

### Phase 2: UI 翻译
1. 标记侧边栏标题
2. 标记配置面板标签
3. 标记按钮和操作项
4. 标记状态栏

### Phase 3: 动态内容
1. 配置 schema 的 label/tooltip 翻译
2. 对话框和提示信息翻译

## 5. 注意事项

1. **性能**：翻译文件较小，直接内联加载，无需异步请求
2. **兼容性**：保持英文作为 fallback，确保翻译缺失时不影响使用
3. **维护性**：翻译 key 使用层级结构，便于管理
4. **日志不翻译**：`log.info/error/success` 等保持英文输出

## 6. 工作量估计

- Phase 1: 1-2 小时
- Phase 2: 2-3 小时
- Phase 3: 1-2 小时
- 总计: 4-7 小时
