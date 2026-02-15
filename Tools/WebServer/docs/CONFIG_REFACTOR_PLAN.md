# Configuration System Refactor Plan

## 现状分析

### 问题 1: 配置项分散在多个文件中

添加一个新配置项需要修改 **6 个文件**：

| 文件 | 修改内容 |
|------|----------|
| `core/state.py` | 1. 添加到 `PERSISTENT_KEYS` 列表<br>2. 在 `DeviceState.__init__` 中初始化默认值 |
| `app/routes/connection.py` | 3. 在 `api_get_config()` 返回值中添加<br>4. 在 `api_config()` POST 处理中添加 |
| `static/js/features/config.js` | 5. 在 `loadConfig()` 中添加读取逻辑<br>6. 在 `saveConfig()` 中添加保存逻辑<br>7. 可能需要添加 `onXxxChange()` 回调<br>8. 在 `setupAutoSave()` 中注册 |
| `templates/partials/sidebar_config.html` | 9. 添加 HTML 表单元素 |
| `tests/test_routes.py` | 10. 添加 GET/POST 测试 |
| `tests/test_state.py` | 11. 更新 `test_round_trip_all_keys` |

### 问题 2: UI 布局混乱

当前配置面板存在以下问题：

1. **无分类分组** - 所有配置项平铺，没有逻辑分组
2. **排版不整齐** - 路径输入框、数字输入框、checkbox 混杂
3. **label 宽度不一致** - 都是 80px，但有些文字太长被截断
4. **缺少视觉层次** - 没有分隔线或分组标题

当前配置项可分为以下类别：

| 类别 | 配置项 |
|------|--------|
| **项目路径** | ELF Path, Compile DB, Toolchain, Ghidra Path |
| **注入设置** | Inject Mode, Auto Inject on Save, Watch Directories |
| **传输参数** | Chunk Size, TX Chunk, TX Delay, Max Retries, Verify CRC |
| **日志设置** | Log Path, Record Serial Logs |
| **分析工具** | Ghidra Path, Enable Decompilation |

### 问题 3: 代码重复

- `api_get_config()` 和 `api_config()` 中的字段列表需要手动同步
- `loadConfig()` 和 `saveConfig()` 中的字段映射需要手动同步
- HTML 中的 `id` 和 JS 中的 `getElementById` 需要手动匹配

---

## 重构方案

### 方案概述

采用 **配置元数据驱动** 的方式，将配置项定义集中到一个地方，其他代码通过元数据自动生成。

### 阶段 1: 后端配置元数据化

#### 1.1 创建配置定义文件 `core/config_schema.py`

```python
"""Configuration schema definition."""

from dataclasses import dataclass, field
from typing import Any, List, Optional
from enum import Enum

class ConfigType(Enum):
    STRING = "string"
    PATH = "path"          # 路径，带浏览按钮
    DIR_PATH = "dir_path"  # 目录路径
    FILE_PATH = "file_path"  # 文件路径，可指定扩展名
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    PATH_LIST = "path_list"  # 目录列表

class ConfigGroup(Enum):
    PROJECT = "project"      # 项目路径
    INJECT = "inject"        # 注入设置
    TRANSFER = "transfer"    # 传输参数
    LOGGING = "logging"      # 日志设置
    TOOLS = "tools"          # 分析工具

@dataclass
class ConfigItem:
    key: str                          # 配置键名 (snake_case)
    label: str                        # 显示标签
    group: ConfigGroup                # 所属分组
    type: ConfigType                  # 类型
    default: Any                      # 默认值
    tooltip: str = ""                 # 提示文字
    # 类型特定选项
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    unit: str = ""                    # 单位 (Bytes, ms, times)
    options: List[tuple] = field(default_factory=list)  # select 选项
    file_ext: str = ""                # 文件扩展名过滤
    # UI 控制
    depends_on: Optional[str] = None  # 依赖的配置项
    order: int = 0                    # 排序权重

# 配置项定义
CONFIG_SCHEMA: List[ConfigItem] = [
    # === 项目路径 ===
    ConfigItem(
        key="elf_path",
        label="ELF Path",
        group=ConfigGroup.PROJECT,
        type=ConfigType.FILE_PATH,
        default="",
        tooltip="Path to the compiled ELF file for symbol lookup and disassembly",
        file_ext=".elf",
        order=10,
    ),
    ConfigItem(
        key="compile_commands_path",
        label="Compile DB",
        group=ConfigGroup.PROJECT,
        type=ConfigType.FILE_PATH,
        default="",
        tooltip="Path to compile_commands.json for accurate compile flags",
        file_ext=".json",
        order=20,
    ),
    ConfigItem(
        key="toolchain_path",
        label="Toolchain",
        group=ConfigGroup.PROJECT,
        type=ConfigType.DIR_PATH,
        default="",
        tooltip="Path to cross-compiler toolchain bin directory",
        order=30,
    ),
    
    # === 注入设置 ===
    ConfigItem(
        key="patch_mode",
        label="Inject Mode",
        group=ConfigGroup.INJECT,
        type=ConfigType.SELECT,
        default="trampoline",
        tooltip="Trampoline: Use code trampoline\nDebugMonitor: Use DebugMonitor exception\nDirect: Direct code replacement",
        options=[
            ("trampoline", "Trampoline"),
            ("debugmon", "DebugMonitor"),
            ("direct", "Direct"),
        ],
        order=10,
    ),
    ConfigItem(
        key="auto_compile",
        label="Auto Inject on Save",
        group=ConfigGroup.INJECT,
        type=ConfigType.BOOLEAN,
        default=False,
        order=20,
    ),
    ConfigItem(
        key="watch_dirs",
        label="Watch Directories",
        group=ConfigGroup.INJECT,
        type=ConfigType.PATH_LIST,
        default=[],
        depends_on="auto_compile",
        order=30,
    ),
    
    # === 传输参数 ===
    ConfigItem(
        key="chunk_size",
        label="Chunk Size",
        group=ConfigGroup.TRANSFER,
        type=ConfigType.NUMBER,
        default=128,
        tooltip="Size of each uploaded data block",
        min_value=16,
        max_value=1024,
        step=16,
        unit="Bytes",
        order=10,
    ),
    ConfigItem(
        key="tx_chunk_size",
        label="TX Chunk",
        group=ConfigGroup.TRANSFER,
        type=ConfigType.NUMBER,
        default=0,
        tooltip="TX chunk size for serial commands. 0 = disabled.",
        min_value=0,
        max_value=256,
        step=8,
        unit="Bytes",
        order=20,
    ),
    ConfigItem(
        key="tx_chunk_delay",
        label="TX Delay",
        group=ConfigGroup.TRANSFER,
        type=ConfigType.NUMBER,
        default=0.005,
        tooltip="Delay between TX chunks (seconds)",
        min_value=0.001,
        max_value=0.1,
        step=0.001,
        unit="ms",  # 前端显示时 *1000
        order=30,
    ),
    ConfigItem(
        key="transfer_max_retries",
        label="Max Retries",
        group=ConfigGroup.TRANSFER,
        type=ConfigType.NUMBER,
        default=10,
        tooltip="Maximum retry attempts for file transfer",
        min_value=0,
        max_value=20,
        step=1,
        unit="times",
        order=40,
    ),
    ConfigItem(
        key="verify_crc",
        label="Verify CRC",
        group=ConfigGroup.TRANSFER,
        type=ConfigType.BOOLEAN,
        default=True,
        tooltip="Verify file integrity with CRC after transfer",
        order=50,
    ),
    
    # === 日志设置 ===
    ConfigItem(
        key="log_file_path",
        label="Log Path",
        group=ConfigGroup.LOGGING,
        type=ConfigType.PATH,
        default="",
        tooltip="Path to save serial logs",
        order=10,
    ),
    ConfigItem(
        key="log_file_enabled",
        label="Record Serial Logs",
        group=ConfigGroup.LOGGING,
        type=ConfigType.BOOLEAN,
        default=False,
        tooltip="Record serial communication logs to file",
        order=20,
    ),
    
    # === 分析工具 ===
    ConfigItem(
        key="ghidra_path",
        label="Ghidra Path",
        group=ConfigGroup.TOOLS,
        type=ConfigType.DIR_PATH,
        default="",
        tooltip="Path to Ghidra installation directory",
        order=10,
    ),
    ConfigItem(
        key="enable_decompile",
        label="Enable Decompilation",
        group=ConfigGroup.TOOLS,
        type=ConfigType.BOOLEAN,
        default=False,
        tooltip="Enable decompilation when creating patch templates (requires Ghidra)",
        order=20,
    ),
]

# 生成 PERSISTENT_KEYS
PERSISTENT_KEYS = [item.key for item in CONFIG_SCHEMA]

# 分组显示名称
GROUP_LABELS = {
    ConfigGroup.PROJECT: "Project Paths",
    ConfigGroup.INJECT: "Injection",
    ConfigGroup.TRANSFER: "Transfer",
    ConfigGroup.LOGGING: "Logging",
    ConfigGroup.TOOLS: "Analysis Tools",
}
```

#### 1.2 重构 `core/state.py`

```python
from core.config_schema import CONFIG_SCHEMA, PERSISTENT_KEYS

class DeviceState:
    def __init__(self):
        # 从 schema 自动初始化默认值
        for item in CONFIG_SCHEMA:
            setattr(self, item.key, item.default)
        
        # 非持久化的运行时状态
        self.ser = None
        self.device_info = None
        # ...
```

#### 1.3 重构 `app/routes/connection.py`

```python
from core.config_schema import CONFIG_SCHEMA

@bp.route("/config", methods=["GET"])
def api_get_config():
    """Get current device configuration."""
    device = state.device
    return jsonify({item.key: getattr(device, item.key) for item in CONFIG_SCHEMA})

@bp.route("/config", methods=["POST"])
def api_config():
    """Update device configuration."""
    data = request.json or {}
    device = state.device
    
    for item in CONFIG_SCHEMA:
        if item.key in data:
            setattr(device, item.key, data[item.key])
            # 特殊处理逻辑
            if item.key == "elf_path":
                _reload_symbols()
            elif item.key == "toolchain_path":
                _update_toolchain()
            # ...
    
    state.save_config()
    return jsonify({"success": True})

@bp.route("/config/schema", methods=["GET"])
def api_get_config_schema():
    """Get configuration schema for frontend."""
    return jsonify({
        "schema": [asdict(item) for item in CONFIG_SCHEMA],
        "groups": {g.value: label for g, label in GROUP_LABELS.items()},
    })
```

### 阶段 2: 前端配置元数据化

#### 2.1 创建 `static/js/core/config-schema.js`

```javascript
// 从后端获取 schema 并缓存
let configSchema = null;

async function loadConfigSchema() {
  if (configSchema) return configSchema;
  const res = await fetch('/api/config/schema');
  configSchema = await res.json();
  return configSchema;
}

// 根据 schema 生成表单元素
function renderConfigItem(item) {
  switch (item.type) {
    case 'path':
    case 'file_path':
    case 'dir_path':
      return renderPathInput(item);
    case 'number':
      return renderNumberInput(item);
    case 'boolean':
      return renderCheckbox(item);
    case 'select':
      return renderSelect(item);
    case 'path_list':
      return renderPathList(item);
  }
}

// 根据 schema 自动生成 loadConfig/saveConfig
function loadConfigFromSchema(data, schema) {
  for (const item of schema) {
    const el = document.getElementById(item.key);
    if (!el) continue;
    
    if (item.type === 'boolean') {
      el.checked = data[item.key] ?? item.default;
    } else {
      el.value = data[item.key] ?? item.default;
    }
  }
}

function saveConfigFromSchema(schema) {
  const config = {};
  for (const item of schema) {
    const el = document.getElementById(item.key);
    if (!el) continue;
    
    if (item.type === 'boolean') {
      config[item.key] = el.checked;
    } else if (item.type === 'number') {
      config[item.key] = parseFloat(el.value) || item.default;
    } else {
      config[item.key] = el.value;
    }
  }
  return config;
}
```

#### 2.2 重构 HTML 模板

使用 Jinja2 模板从后端 schema 动态生成：

```html
<!-- templates/partials/sidebar_config.html -->
{% for group_id, group_label in config_groups.items() %}
<div class="config-group">
  <div class="config-group-header">{{ group_label }}</div>
  {% for item in config_schema if item.group == group_id %}
    {{ render_config_item(item) }}
  {% endfor %}
</div>
{% endfor %}
```

或者前端动态渲染：

```javascript
async function renderConfigPanel() {
  const { schema, groups } = await loadConfigSchema();
  const container = document.getElementById('configContainer');
  
  // 按分组渲染
  for (const [groupId, groupLabel] of Object.entries(groups)) {
    const groupItems = schema.filter(item => item.group === groupId);
    if (groupItems.length === 0) continue;
    
    const groupEl = document.createElement('div');
    groupEl.className = 'config-group';
    groupEl.innerHTML = `<div class="config-group-header">${groupLabel}</div>`;
    
    for (const item of groupItems.sort((a, b) => a.order - b.order)) {
      groupEl.appendChild(renderConfigItem(item));
    }
    
    container.appendChild(groupEl);
  }
}
```

### 阶段 3: UI 改进

#### 3.1 分组样式

```css
.config-group {
  margin-bottom: 12px;
  border: 1px solid var(--vscode-panel-border);
  border-radius: 4px;
  overflow: hidden;
}

.config-group-header {
  background: var(--vscode-sideBarSectionHeader-background);
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--vscode-sideBarSectionHeader-foreground);
}

.config-group-content {
  padding: 8px 10px;
}

.config-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.config-item label {
  width: 90px;
  font-size: 11px;
  flex-shrink: 0;
}

.config-item-checkbox {
  padding: 4px 0;
}

.config-item-checkbox label {
  width: auto;
  margin-left: 4px;
}
```

#### 3.2 建议的分组布局

```
┌─ CONFIGURATION ─────────────────────────────┐
│                                             │
│ ┌─ Project Paths ─────────────────────────┐ │
│ │ ELF Path      [____________________] [📁]│ │
│ │ Compile DB    [____________________] [📁]│ │
│ │ Toolchain     [____________________] [📁]│ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─ Injection ─────────────────────────────┐ │
│ │ Inject Mode   [Trampoline         ▼]    │ │
│ │ ☑ Auto Inject on Save                   │ │
│ │   Watch Directories:              [+]   │ │
│ │   [/path/to/dir1              ] [📁][×] │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─ Transfer ──────────────────────────────┐ │
│ │ Chunk Size    [128    ] Bytes           │ │
│ │ TX Chunk      [0      ] Bytes           │ │
│ │ TX Delay      [5      ] ms              │ │
│ │ Max Retries   [10     ] times           │ │
│ │ ☑ Verify CRC after Transfer             │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─ Logging ───────────────────────────────┐ │
│ │ Log Path      [____________________] [📁]│ │
│ │ ☐ Record Serial Logs                    │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─ Analysis Tools ────────────────────────┐ │
│ │ Ghidra Path   [____________________] [📁]│ │
│ │ ☐ Enable Decompilation                  │ │
│ └─────────────────────────────────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 实施计划

### Phase 1: 后端重构 ✅ 已完成

1. [x] 创建 `core/config_schema.py`
2. [x] 重构 `core/state.py` 使用 schema
3. [x] 重构 `app/routes/connection.py` 使用 schema
4. [x] 添加 `/api/config/schema` 端点
5. [x] 更新测试用例 (`tests/test_config_schema.py` - 26 个测试)

### Phase 2: 前端重构 ✅ 已完成

1. [x] 创建 `static/js/core/config-schema.js`
2. [x] 重构 `static/js/features/config.js`
3. [x] 更新 HTML 模板改为动态渲染 (`templates/partials/sidebar_config.html`)
4. [x] 添加分组样式 (`static/css/workbench.css`)
5. [x] 添加 script 引用 (`templates/partials/scripts.html`)

### Phase 3: UI 优化 ✅ 已完成

1. [x] 添加分组标题样式 (`.config-group-header`)
2. [x] 统一配置项布局 (`.config-item`, `.config-item-path`, `.config-item-number`, `.config-item-checkbox`)
3. [x] 添加单位标签样式 (`.config-unit`)
4. [x] 添加路径列表样式 (`.config-path-list`, `.config-path-list-item`)

### Phase 4: 测试和文档 ✅ 已完成

1. [x] 更新单元测试 (`tests/test_templates.py` - 更新为检查动态渲染容器)
2. [x] 所有 984 个测试通过

---

## 收益

1. **添加新配置项只需修改 1 个文件** (`config_schema.py`)
2. **UI 自动分组**，布局整齐
3. **类型安全**，有默认值和验证
4. **前后端一致性**，schema 作为单一数据源
5. **易于测试**，可自动生成测试用例

---

## 风险和注意事项

1. **向后兼容** - 需要处理旧版 config.json 的迁移
2. **特殊逻辑** - 某些配置项有特殊的 onChange 逻辑，需要保留钩子
3. **性能** - 动态渲染可能比静态 HTML 稍慢，但影响可忽略
4. **复杂度** - 引入 schema 增加了一定的抽象层，需要文档说明
