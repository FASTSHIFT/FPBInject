# Log File Recording Feature

## Overview

The log file recording feature allows you to save console logs to a file for later analysis or debugging. This is useful for:

- Long-running sessions where you need to review logs later
- Debugging issues that require log analysis
- Keeping a permanent record of operations
- Sharing logs with team members

## Usage

### Web Interface

1. Open the **Configuration** section in the sidebar
2. Check the **Save Logs to File** checkbox
3. Specify the log file path (or use the folder icon to browse)
4. Logs will be automatically saved to the specified file

### Features

- **Auto-start on launch**: If enabled, log recording will automatically resume when the server restarts
- **Timestamped entries**: Each log entry includes a precise timestamp
- **Append mode**: New sessions append to existing log files
- **Thread-safe**: Safe to use with concurrent operations

### API Endpoints

#### Start Recording

```bash
POST /api/log_file/start
Content-Type: application/json

{
  "path": "/path/to/logfile.log"
}
```

Response:
```json
{
  "success": true,
  "error": ""
}
```

#### Stop Recording

```bash
POST /api/log_file/stop
```

Response:
```json
{
  "success": true,
  "error": ""
}
```

#### Get Status

```bash
GET /api/log_file/status
```

Response:
```json
{
  "success": true,
  "enabled": true,
  "path": "/path/to/logfile.log",
  "config_enabled": true,
  "config_path": "/path/to/logfile.log"
}
```

## Log Format

Log files include:

- Session headers with start/stop timestamps
- Timestamped log entries in format: `[YYYY-MM-DD HH:MM:SS.mmm] message`
- Clear session boundaries

Example:

```
============================================================
Log recording started at 2026-02-11 14:30:00
============================================================

[2026-02-11 14:30:05.123] [INFO] Connected to /dev/ttyACM0
[2026-02-11 14:30:10.456] [SUCCESS] Injection completed
[2026-02-11 14:30:15.789] [ERROR] Failed to read file

============================================================
Log recording stopped at 2026-02-11 14:35:00
============================================================
```

## Implementation Details

### Backend

- **Service**: `services/log_recorder.py` - Thread-safe log recording service
- **State**: Log file settings stored in `DeviceState` and persisted to `config.json`
- **Routes**: API endpoints in `app/routes/logs.py`
- **Integration**: Logs written via `DeviceState.add_tool_log()` method

### Frontend

- **UI**: Configuration controls in `templates/partials/sidebar_config.html`
- **Logic**: JavaScript handlers in `static/js/features/config.js`
- **State**: Settings loaded/saved with other configuration

### Tests

- **Unit tests**: `tests/test_log_recorder.py` (11 test cases)
- **Integration tests**: `tests/test_log_file_routes.py` (8 test cases)
- **Frontend tests**: `tests/js/test_log_file.js` (9 test cases)

All tests pass successfully.

## Configuration Persistence

Log file settings are automatically saved to `config.json`:

```json
{
  "log_file_enabled": true,
  "log_file_path": "/path/to/logfile.log"
}
```

When the server restarts, log recording will automatically resume if it was enabled.
