---
inclusion: fileMatch
fileMatchPattern: "Tools/WebServer/**"
---

# WebServer 开发指南

当修改 `Tools/WebServer/` 下的代码时，遵循以下约定。

## 后端架构（Python Flask）

入口：`Tools/WebServer/main.py`，Flask 应用，端口 5500。

### 模块职责

| 目录 | 职责 |
|------|------|
| `core/state.py` | 全局状态 `AppState` / `DeviceState`，配置持久化到 `config.json` |
| `core/serial_protocol.py` | 串口通信协议，`FPBProtocol` 类，`Platform` 枚举（NuttX/BareMetal） |
| `core/compiler.py` | `compile_inject()` 交叉编译注入代码，`fix_veneer_thumb_bits()` |
| `core/elf_utils.py` | ELF 解析：符号表、反汇编、Ghidra 反编译、函数签名 |
| `core/patch_generator.py` | `PatchGenerator` 类，解析 `/* FPB_INJECT */` 标记，生成补丁源码 |
| `core/config_schema.py` | 配置 schema 定义，`PERSISTENT_KEYS` |
| `core/file_transfer.py` | 文件传输协议 |
| `fpb_inject.py` | `FPBInject` 类，注入主逻辑：编译 → 上传 → patch |
| `fpb_cli.py` | CLI 工具，所有命令输出 JSON |
| `services/` | 后台服务：device_worker、file_watcher、log_recorder、timer |
| `app/routes/` | Flask Blueprint 路由，每个文件一个 Blueprint |

### API 路由约定

- 路由文件在 `app/routes/`，使用 Flask Blueprint
- 所有 API 返回 `jsonify({"success": True/False, ...})`
- 懒加载 `_get_fpb_inject()` 避免循环依赖
- 全局状态通过 `from core.state import state` 访问

## 前端架构（原生 JS）

- 入口：`static/js/app.js`，DOMContentLoaded 初始化
- 模块化：`core/`（状态、连接、终端）、`features/`（功能模块）、`ui/`（布局）
- 编辑器：ACE Editor，支持多标签页
- 样式：`static/css/workbench.css`（主布局）、`style.css`
- 模板：`templates/` 下 Jinja2 HTML
- 国际化：`static/js/core/i18n.js` + `static/js/locales/`
- 前端测试：`tests/test_frontend.js`，Node.js 运行

## 测试（重要）

### 后端 Python 测试

- 框架：`pytest` + `unittest` + `unittest.mock`
- 测试目录：`Tools/WebServer/tests/`
- 命名规则：`test_<module>.py`，类名 `Test<Feature>`，方法名 `test_<scenario>`
- Mock 外部依赖（subprocess、serial、文件系统），不依赖真实硬件
- 覆盖率要求：≥ 80%（CI 强制检查）

### 运行测试命令

```bash
# 运行所有后端测试（推荐，包含 API 一致性检查 + 中文扫描）
cd Tools/WebServer && python tests/run_tests.py --coverage --html --target 80

# 用 pytest 运行所有测试
cd Tools/WebServer && python -m pytest tests/ -v

# 运行单个测试文件
cd Tools/WebServer && python -m pytest tests/test_compiler.py -v

# 运行单个测试类
cd Tools/WebServer && python -m pytest tests/test_compiler.py::TestCompileInject -v

# 运行单个测试方法
cd Tools/WebServer && python -m pytest tests/test_compiler.py::TestCompileInject::test_no_config -v

# 前端 JS 测试
cd Tools/WebServer && node tests/test_frontend.js --coverage --ci --threshold 80
```

### 添加新测试的步骤

1. 在 `Tools/WebServer/tests/` 下创建 `test_<module>.py`
2. 使用 `unittest.TestCase` 基类
3. Mock 所有外部依赖（`@patch`）
4. 测试文件会被 `unittest.TestLoader().discover()` 自动发现，无需手动注册
5. 运行 `python -m pytest tests/test_<module>.py -v` 验证

### 代码格式化与 Lint

```bash
# 检查格式 + lint（CI 会执行）
cd Tools/WebServer && ./format.sh --check --lint

# 自动格式化
cd Tools/WebServer && ./format.sh
```

## 补丁代码规范

- 注入函数必须标记 `/* FPB_INJECT */` 注释
- 函数属性：`__attribute__((section(".fpb.text"), used))`
- 函数签名必须与原始函数一致
- 不支持从注入代码调用原始函数（FPB 硬件限制，会无限递归）
- 使用 `\r\n` 换行符用于串口输出
