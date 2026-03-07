# Log File Recording

## Overview

The log file recording feature allows you to save console logs to a file for later analysis or debugging. This is useful for:

- Long-running sessions where you need to review logs later
- Debugging issues that require log analysis
- Keeping a permanent record of operations
- Sharing logs with team members

## Quick Start

### Web Interface

1. Open the **Configuration** section in the sidebar
2. Check the **Save Logs to File** checkbox
3. Specify the log file path (or use the folder icon to browse)
4. Logs will be automatically saved to the specified file

```
┌─────────────────────────────────────────┐
│ CONFIGURATION                           │
├─────────────────────────────────────────┤
│ ...                                     │
│ ☐ Enable Decompilation                 │
│ ☑ Save Logs to File                    │
│   Log Path: /tmp/console.log           │
│   [📁]                                  │
│ ...                                     │
└─────────────────────────────────────────┘
```

### API Endpoints

```bash
# Start recording
curl -X POST http://localhost:5500/api/log_file/start \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/console.log"}'

# Stop recording
curl -X POST http://localhost:5500/api/log_file/stop

# Get status
curl http://localhost:5500/api/log_file/status
```

Response examples:

```json
// POST /api/log_file/start, POST /api/log_file/stop
{ "success": true, "error": "" }

// GET /api/log_file/status
{
  "success": true,
  "enabled": true,
  "path": "/path/to/logfile.log",
  "config_enabled": true,
  "config_path": "/path/to/logfile.log"
}
```

## Log Format

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

## Features

- **Auto-start on launch**: If enabled, log recording automatically resumes when the server restarts
- **Timestamped entries**: Each log entry includes a precise timestamp `[YYYY-MM-DD HH:MM:SS.mmm]`
- **Append mode**: New sessions append to existing log files
- **Thread-safe**: Safe to use with concurrent operations
- **Auto directory creation**: Automatically creates directories if they don't exist
- **Config persistence**: Settings saved to `config.json`

## Configuration Persistence

Settings are automatically saved to `config.json`:

```json
{
  "log_file_enabled": true,
  "log_file_path": "/path/to/logfile.log"
}
```

## Error Handling

If the path is invalid or permissions are insufficient, the system shows an error:

```
[ERROR] Failed to start log recording: Permission denied
```

The checkbox will automatically uncheck, requiring the user to fix the path and retry.

## Implementation Details

### Backend

| File | Role |
|------|------|
| `services/log_recorder.py` | Thread-safe log recording service (~100 lines) |
| `core/state.py` | `log_file_enabled` / `log_file_path` state fields, integrated in `add_tool_log()` |
| `app/routes/logs.py` | API endpoints: start, stop, status |
| `main.py` | State restoration on startup via `restore_state()` |

### Frontend

| File | Role |
|------|------|
| `templates/partials/sidebar_config.html` | Checkbox + path input UI |
| `static/js/features/config.js` | `onLogFileEnabledChange()`, `browseLogFile()`, config load/save |

### Tests

| File | Count |
|------|-------|
| `tests/test_log_recorder.py` | 11 unit tests |
| `tests/test_log_file_routes.py` | 8 integration tests |
| `tests/js/test_log_file.js` | 9 frontend tests |

## Notes

- Ensure the log file path has write permissions
- Long-running sessions produce large logs — monitor disk space
- Log writes are asynchronous and do not block the main thread
- Logs are not translated (kept in English for debugging)
