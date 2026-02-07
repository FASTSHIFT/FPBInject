# FPBInject WebServer

A web-based interface for real-time function injection with file monitoring support.

## Features

- **Hot Patching**: Modify target functions in real-time without reflashing
- **Marker-based Development**: Add `/* FPB_INJECT */` markers to auto-detect patchable functions
- **File Monitoring**: Auto-inject on file save
- **Modern UI**: VS Code-style web interface
- **Built-in Terminal**: Serial monitor and interaction terminal

## Installation

### Requirements

- Python 3.8+
- ARM GCC Toolchain (`arm-none-eabi-gcc`)
- pyserial

### Setup

```bash
cd Tools/WebServer
pip install -r requirements.txt
```

### Start Server

```bash
python3 main.py
# Default: http://127.0.0.1:5500
```

## Configuration

### Settings Panel

1. **Serial Port**: Device port (e.g., `/dev/ttyACM0`, `COM3`)
2. **ELF Path**: Compiled firmware ELF file path
3. **Toolchain Path**: Cross-compiler prefix (e.g., `arm-none-eabi-`)
4. **Compile Commands**: Path to `compile_commands.json` for include paths and defines

Click **Connect** to establish device connection.

## Usage

### 1. Mark Functions for Injection

Add marker comments before patchable functions:

```c
/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void my_function(int arg) {
    // Patch implementation
}
```

Supported markers:
- `/* FPB_INJECT */`
- `/* FPB-INJECT */`
- `// FPB_INJECT`
- `/*FPB_INJECT*/` (case-insensitive)

### 2. Auto-Injection Workflow

1. Open the web interface
2. Configure and connect to device
3. Edit source files with FPB_INJECT markers
4. Save file → automatic injection

The WebServer monitors source files and:
- Detects FPB_INJECT markers
- Compiles injection code
- Uploads to device RAM
- Configures FPB redirection

### 3. Manual Injection

Use the interface to manually select functions and inject patches.

## Web Interface Sections

### Explorer Panel
- Browse project files
- View file tree structure

### Editor Panel
- Monaco-based code editor
- Syntax highlighting for C/C++

### Terminal Panel
- Serial output monitor
- Interactive command input

### Settings Panel
- Connection configuration
- Build settings

## API Endpoints

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/connect` | POST | Connect to device |
| `/api/disconnect` | POST | Disconnect |
| `/api/info` | GET | Get FPB info |
| `/api/inject` | POST | Inject patch |
| `/api/unpatch` | POST | Remove patch |
| `/api/files` | GET | List files |

### WebSocket

Real-time updates via WebSocket at `/ws`:
- Serial output streaming
- File change notifications
- Injection status updates

## Troubleshooting

### Connection Issues

```bash
# Check serial port permissions
sudo chmod 666 /dev/ttyACM0
# Or add user to dialout group
sudo usermod -a -G dialout $USER
```

### Compilation Errors

Ensure:
- ARM toolchain is in PATH
- `compile_commands.json` exists and is correct
- Include paths are accessible

### Injection Fails

Check:
- Device is in function loader mode
- ELF file matches running firmware
- RAM allocation has space

## Architecture

```
WebServer/
├── main.py           # Flask application entry
├── fpb_inject.py     # Core injection logic
├── fpb_cli.py        # CLI interface
├── templates/        # HTML templates
├── static/           # JS/CSS assets
└── tests/            # Test suite
```

## Related Documentation

- [CLI Tool](CLI.md) - Command-line interface
- [Architecture](Architecture.md) - Technical details
- [SKILLS.md](../Tools/WebServer/docs/SKILLS.md) - AI integration skills
