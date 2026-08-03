# FPBInject 开发与测试指南

## 项目概述

FPBInject 是一个 ARM Cortex-M 运行时代码注入工具，利用 FPB（Flash Patch and Breakpoint）硬件单元实现固件热补丁。项目分为两部分：

- **下位机 (Lower Machine)**：嵌入式固件，C 语言，位于 `Source/`、`App/`、`cmake/`
- **上位机 (Upper Machine)**：WebServer，Python + JavaScript，位于 `Tools/WebServer/`

---

## CI 流程 (.github/workflows/ci.yml)

CI 包含两个并行 Job：`lower-machine` 和 `upper-machine`。

---

## 上位机 (WebServer) 开发流程

### 工作目录

```bash
cd FPBInject/Tools/WebServer
```

### 1. 代码格式化与 Lint 检查

```bash
# 检查格式（不修改文件）
./format.sh --check --lint

# 自动格式化
./format.sh

# 格式化后确认无 diff
git diff --quiet || echo "需要提交格式化修改"
```

- Python: 使用 `black` 格式化，`flake8` lint
- JavaScript/HTML/CSS: 使用 `prettier` 格式化

### 2. 后端 Python 测试（覆盖率目标 ≥85%）

```bash
# CI 标准命令（含覆盖率 + HTML 报告）
python3 tests/run_tests.py --coverage --html --target 85

# 快速运行所有测试（无覆盖率）
python3 -m pytest tests/ -v --tb=short

# 运行单个测试文件
python3 -m pytest tests/test_main.py -v

# 运行特定测试
python3 -m pytest tests/test_main.py::TestAutoOpenBrowser::test_startup_banner_shows_lan_ip -v

# 查看覆盖率详情（含未覆盖行号）
python3 -m pytest --cov=. --cov-report=term-missing --tb=no -q

# 只看低覆盖率文件
python3 -m pytest --cov=. --cov-report=term-missing --tb=no -q 2>&1 | grep -E "[0-9]+%"
```

**覆盖率说明**：
- CI 目标：≥85%（`--target 85`）
- 建议本地保持 ≥86%，因为 CI 环境可能跳过部分测试
- `tests/run_tests.py` 会排除 `tests/`、`static/`、`templates/` 目录
- 覆盖率报告输出到 `tests/htmlcov/`

### 3. 前端 JavaScript 测试（覆盖率目标 ≥80%）

```bash
# 安装依赖
npm install

# CI 标准命令
node tests/test_frontend.js --coverage --ci --threshold 80
```

### 4. 完整 CI 本地模拟

```bash
cd FPBInject/Tools/WebServer

# Step 1: 格式化检查
./format.sh --check --lint

# Step 2: 后端测试
python3 tests/run_tests.py --coverage --html --target 85

# Step 3: 前端测试
npm install && node tests/test_frontend.js --coverage --ci --threshold 80
```

---

## 下位机 (Firmware) 开发流程

### 1. 构建测试

```bash
cd FPBInject
Tools/build_test.sh
```

### 2. 固件单元测试（覆盖率目标 ≥80%）

```bash
cd FPBInject/App/tests
./run_tests.sh coverage --threshold 80
```

### 3. 代码格式检查

```bash
cd FPBInject
Tools/code_format.sh --check    # C/C++ (clang-format)
Tools/cmake_format.sh --check   # CMake
```

---

## Git 提交规范

使用 Conventional Commits 格式：

```
feat(module): 简短描述
fix(module): 修复描述
test(module): 测试描述
refactor(module): 重构描述
chore(module): 杂项描述
```

常用 module：`main`, `compiler`, `cli`, `WebServer`, `serial`

---

## 关键文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | WebServer 入口，Flask 应用启动 |
| `fpb_inject.py` | 注入工作流编排 |
| `cli/fpb_cli.py` | CLI 命令行工具 |
| `core/compiler.py` | 编译注入代码 |
| `core/patch_generator.py` | 检测 FPB_INJECT 标记 |
| `core/serial_protocol.py` | 串口协议 (FL 命令) |
| `core/config_schema.py` | 配置项 schema 定义 |
| `services/file_watcher_manager.py` | 文件监控管理 |
| `tests/run_tests.py` | 测试运行器（CI 使用） |
| `format.sh` | 代码格式化脚本 |

---

## 常见问题

### 覆盖率不足
1. 运行 `python3 -m pytest --cov=. --cov-report=term-missing` 找到低覆盖文件
2. 查看未覆盖行号，针对性添加测试
3. 优先覆盖分支逻辑（if/else、try/except、异常路径）

### 格式化失败
运行 `./format.sh` 自动修复，然后 `git add` 提交

### 启动 WebServer
```bash
cd FPBInject/Tools/WebServer
./main.py                    # 默认 0.0.0.0:5500，自动打开浏览器
./main.py --no-browser       # 不打开浏览器
./main.py --port 8001        # 指定端口
```
