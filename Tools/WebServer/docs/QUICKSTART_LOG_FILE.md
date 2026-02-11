# 控制台日志保存功能 - 快速开始

## 功能说明

在 WebServer 中添加了控制台日志保存到文件的功能，支持：
- ✅ 网页界面控制开关和路径
- ✅ 自动恢复记录状态
- ✅ 带时间戳的日志条目
- ✅ 线程安全的并发写入

## 使用方法

### 1. 网页界面

打开 http://localhost:5500，在左侧边栏的 **CONFIGURATION** 部分：

1. 勾选 **Save Logs to File** 复选框
2. 输入日志文件路径，例如：`/tmp/fpb_console.log`
3. 或点击文件夹图标浏览选择文件
4. 日志将自动保存到指定文件

### 2. API 调用

```bash
# 启动日志记录
curl -X POST http://localhost:5500/api/log_file/start \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/console.log"}'

# 停止日志记录
curl -X POST http://localhost:5500/api/log_file/stop

# 查询记录状态
curl http://localhost:5500/api/log_file/status
```

## 日志格式

```
============================================================
Log recording started at 2026-02-11 14:30:00
============================================================

[2026-02-11 14:30:05.123] [INFO] Connected to /dev/ttyACM0
[2026-02-11 14:30:10.456] [SUCCESS] Injection completed

============================================================
Log recording stopped at 2026-02-11 14:35:00
============================================================
```

## 测试

运行测试验证功能：

```bash
cd Tools/WebServer
python -m pytest tests/test_log_recorder.py tests/test_log_file_routes.py -v
```

所有 19 个测试用例应该全部通过 ✅

## 实现文件

### 新增文件
- `services/log_recorder.py` - 日志记录服务
- `tests/test_log_recorder.py` - 单元测试
- `tests/test_log_file_routes.py` - 集成测试
- `tests/js/test_log_file.js` - 前端测试
- `docs/LOG_FILE_RECORDING.md` - 详细文档

### 修改文件
- `core/state.py` - 添加状态字段
- `app/routes/logs.py` - 添加 API 端点
- `main.py` - 添加状态恢复
- `templates/partials/sidebar_config.html` - 添加 UI 控件
- `static/js/features/config.js` - 添加前端逻辑

## 更多信息

详细文档请参考：`docs/LOG_FILE_RECORDING.md`
