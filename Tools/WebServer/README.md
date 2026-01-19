# FPBInject WebServer

FPB (Flash Patch and Breakpoint) 运行时代码注入 Web 服务。

## 功能特性

- 🔌 串口设备连接管理
- 📁 ELF 文件符号解析
- ✏️ Patch 代码编辑与编译
- 📤 二进制上传与注入
- 👁️ 文件变更监控 (自动/手动模式)
- 📺 串口日志实时显示 (xterm.js)

## 目录结构

```
WebServer/
├── main.py              # Flask 应用入口
├── routes.py            # API 路由定义
├── state.py             # 应用状态管理
├── device_worker.py     # 设备通信工作线程
├── fpb_inject.py        # FPB 注入操作
├── file_watcher.py      # 文件系统监控
├── templates/
│   └── index.html       # Web UI 模板
├── static/
│   ├── css/
│   │   └── style.css    # 样式文件
│   └── js/
│       └── app.js       # 前端逻辑
├── test/
│   └── test_api.py      # API 测试用例
└── README.md
```

## 依赖安装

```bash
pip install flask flask-cors pyserial watchdog
```

## 启动服务

```bash
cd apps/examples/FPBInject/Tools/WebServer
python main.py
```

默认在 `http://localhost:5000` 启动服务。

## API 端点

### 设备连接

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/ports` | GET | 获取可用串口列表 |
| `/api/connect` | POST | 连接串口设备 |
| `/api/disconnect` | POST | 断开设备连接 |
| `/api/status` | GET | 获取连接状态 |

### 配置管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/config` | GET | 获取当前配置 |
| `/api/config` | POST | 更新配置 |

### FPB 操作

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/fpb/ping` | POST | Ping 设备 |
| `/api/fpb/info` | GET | 获取 FPB 信息 |
| `/api/fpb/upload` | POST | 上传二进制数据 |
| `/api/fpb/patch` | POST | 执行 patch 操作 |
| `/api/fpb/tpatch` | POST | Trampoline patch |
| `/api/fpb/dpatch` | POST | DebugMon patch |

### 符号管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/symbols` | GET | 获取所有符号 |
| `/api/symbols/search` | GET | 搜索符号 |

### Patch 编译

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/patch/generate` | POST | 生成 patch 模板 |
| `/api/patch/compile` | POST | 编译 patch 代码 |
| `/api/patch/inject` | POST | 编译并注入 |

### 文件监控

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/watch/status` | GET | 获取监控状态 |
| `/api/watch/start` | POST | 启动监控 |
| `/api/watch/stop` | POST | 停止监控 |
| `/api/watch/changes` | GET | 获取变更列表 |

### 日志

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/log` | GET | 获取日志内容 |
| `/api/log` | DELETE | 清空日志 |

### 文件浏览

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/browse` | GET | 浏览目录 |

## Patch 模式

### Trampoline (FPB REMAP)

使用 Cortex-M FPB 单元将目标函数重映射到 patch 代码。

```c
__attribute__((used, section(".text.inject")))
void target_func_patch(void) {
    // 新的实现
}
```

### DebugMon (ARMv8-M)

使用 DebugMon 异常处理断点事件执行 patch。

### Direct

直接修改目标函数地址。

## 运行测试

```bash
cd apps/examples/FPBInject/Tools/WebServer
python -m pytest test/ -v
```

或使用 unittest:

```bash
python test/test_api.py
```

## 相关项目

- [fpb_loader.py](../fpb_loader.py) - FPB CLI 加载工具
- [inject.cpp](../inject.cpp) - Patch 代码示例

## 许可证

MIT License
