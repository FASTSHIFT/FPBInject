---
inclusion: auto
---

# FPBInject MCP Server

项目内置 MCP server（`Tools/WebServer/fpb_mcp_server.py`），提供 14 个 tools 用于 ARM 固件分析和运行时注入。

## Tools 一览

| 类别 | Tool | 说明 |
|------|------|------|
| 离线 | `search` | 按名称搜索符号表 |
| 离线 | `analyze` | 分析函数（地址、签名、汇编行数） |
| 离线 | `disasm` | 反汇编函数 |
| 离线 | `decompile` | Ghidra 反编译（需安装） |
| 离线 | `signature` | 获取 DWARF 函数签名 |
| 离线 | `compile_patch` | 离线编译验证补丁 |
| 连接 | `connect` | 连接串口设备 |
| 连接 | `disconnect` | 断开连接 |
| 在线 | `info` | FPB 硬件状态、slot 占用、内存使用 |
| 在线 | `inject` | 注入补丁替换目标函数 |
| 在线 | `unpatch` | 移除补丁（单个 slot 或全部） |
| 在线 | `test_serial` | 测试串口吞吐量 |
| 串口 | `serial_read` | 读取设备串口输出 |
| 串口 | `serial_send` | 发送命令到设备 |

## 使用流程

1. 用 `search` / `analyze` / `disasm` 了解目标函数
2. 编写补丁 `.c` 文件（必须含 `/* FPB_INJECT */` 标记）
3. `compile_patch` 离线验证编译
4. `connect` → `inject` → `serial_read` 观察效果
5. `unpatch` 清理 → `disconnect`

## 补丁代码规范

- 必须包含 `/* FPB_INJECT */` 注释
- 必须添加 `__attribute__((section(".fpb.text"), used))`
- 函数签名必须与原始函数完全一致
- printf 使用 `\r\n` 换行（串口输出需要）
- 可通过 `extern` 声明调用固件中已有的函数（如 `millis()`）
- trampoline 模式：补丁执行后自动调用原函数
- direct 模式：补丁完全替换原函数

## 常用路径

- ELF：`build/FPBInject.elf`（需先构建固件）
- compile_commands：`build/compile_commands.json`
- 串口：`/dev/ttyACM0`，波特率 `115200`

## 注意事项

- 在线操作前必须先 `connect`
- `serial_send` 避免发送 `fl` 开头的命令（会干扰 FPB 协议）
- FPB 硬件通常有 6 个 slot，用完需要 `unpatch` 释放
- 操作完成后记得 `unpatch --all` + `disconnect` 清理
- 临时补丁文件用完后删除
