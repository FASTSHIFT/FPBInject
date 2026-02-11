# 控制台日志保存功能 - 使用演示

## 功能位置

在 WebServer 界面的左侧边栏 **CONFIGURATION** 部分，新增了两个控件：

```
┌─────────────────────────────────────────┐
│ CONFIGURATION                           │
├─────────────────────────────────────────┤
│ ...                                     │
│ ☐ Enable Decompilation                 │
│ ☑ Save Logs to File          <-- 新增  │
│   Log Path: /tmp/console.log <-- 新增  │
│   [📁]                                  │
│ ...                                     │
└─────────────────────────────────────────┘
```

## 操作步骤

### 1. 启用日志记录

1. 勾选 **Save Logs to File** 复选框
2. 在 **Log Path** 输入框中输入日志文件路径
   - 例如: `/tmp/fpb_console.log`
   - 或点击文件夹图标 📁 浏览选择
3. 系统自动开始记录日志

### 2. 查看日志文件

```bash
# 实时查看日志
tail -f /tmp/fpb_console.log

# 查看完整日志
cat /tmp/fpb_console.log
```

### 3. 停止日志记录

取消勾选 **Save Logs to File** 复选框即可停止记录。

## 日志内容示例

```
============================================================
Log recording started at 2026-02-11 14:30:00
============================================================

[2026-02-11 14:30:05.123] [INFO] Serial port opened: /dev/ttyACM0
[2026-02-11 14:30:10.456] [INFO] ELF loaded: /path/to/firmware.elf
[2026-02-11 14:30:15.789] [SUCCESS] Function injected: digitalWrite
[2026-02-11 14:30:20.012] [INFO] Patch compiled successfully
[2026-02-11 14:30:25.345] [SUCCESS] Code uploaded to device
[2026-02-11 14:30:30.678] [ERROR] CRC mismatch, retrying...
[2026-02-11 14:30:35.901] [SUCCESS] Transfer completed

============================================================
Log recording stopped at 2026-02-11 14:35:00
============================================================
```

## 自动恢复

当服务器重启时，如果之前启用了日志记录，系统会自动恢复：

```
[INFO] Restoring log file recording: /tmp/fpb_console.log
[INFO] Log file recording restored
```

## 配置持久化

设置会自动保存到 `config.json`：

```json
{
  "log_file_enabled": true,
  "log_file_path": "/tmp/fpb_console.log",
  ...
}
```

## 错误处理

如果路径无效或权限不足，系统会显示错误提示：

```
[ERROR] Failed to start log recording: Permission denied
```

此时复选框会自动取消勾选，需要修正路径后重试。

## 使用场景

1. **调试问题**: 保存完整的操作日志用于问题分析
2. **长期监控**: 记录设备长时间运行的日志
3. **团队协作**: 分享日志文件给团队成员
4. **自动化测试**: 在测试脚本中启用日志记录
5. **审计追踪**: 保留操作记录用于审计

## 性能说明

- 日志写入是异步的，不会阻塞主线程
- 使用线程锁保证并发安全
- 自动刷新缓冲区，确保数据不丢失
- 对系统性能影响极小

## 注意事项

1. 确保日志文件路径有写入权限
2. 长时间运行会产生大量日志，注意磁盘空间
3. 日志文件使用追加模式，不会覆盖已有内容
4. 可以随时启用/停用，不影响其他功能
