---
inclusion: always
---

# FPBInject 项目概览

FPBInject 是一个 ARM Cortex-M 微控制器的运行时代码注入系统，利用 FPB（Flash Patch and Breakpoint）硬件单元在不修改 Flash 的情况下实现函数热替换。

## 项目结构

- `App/` — 固件端 C/C++ 代码（func_loader、inject、blink、test）
- `App/tests/` — 固件端单元测试（C，自定义测试框架）
- `Tools/WebServer/` — Python Flask Web 服务器 + 前端（注入控制界面）
- `Tools/WebServer/core/` — 核心模块：编译器、ELF 解析、串口协议、补丁生成
- `Tools/WebServer/services/` — 后台服务：设备通信、文件监控、日志
- `Tools/WebServer/app/routes/` — Flask API 路由
- `Tools/WebServer/static/` — 前端 JS/CSS
- `Tools/WebServer/templates/` — Jinja2 HTML 模板
- `Tools/WebServer/docs/` — WebServer 相关设计文档
- `Project/` — 裸机平台代码（STM32F10x、ArduinoAPI）
- `Docs/` — 项目级文档（架构、CLI、FPB 分析）

## 核心概念

- FPB 硬件提供 6-8 个代码比较器，可拦截指定地址的取指操作
- 三种补丁模式：Trampoline（默认）、DebugMonitor、Direct
- 补丁代码必须标记 `/* FPB_INJECT */` 注释
- 编译流程：提取编译参数 → 交叉编译 → 链接到目标地址 → 提取二进制 → 串口上传

## 技术栈

- 固件：C/C++，ARM GCC 工具链，Cortex-M3（STM32F103），支持 NuttX 和裸机
- 后端：Python 3.8+，Flask，pyserial
- 前端：原生 JS，ACE Editor，Bootstrap
- CLI：`Tools/WebServer/fpb_cli.py`，所有命令输出 JSON
- 构建：CMake（固件），pip（Python）
- 反编译：可选 Ghidra 集成

## 关键文件参考

- 架构文档：`Docs/Architecture.md`
- CLI 文档：`Docs/CLI.md`
