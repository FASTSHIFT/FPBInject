# FPBInject CLI Tool

A lightweight command-line interface for ARM binary patching designed for AI agent integration.

## Overview

`fpb_cli.py` is a pure CLI tool located at `Tools/WebServer/fpb_cli.py`. All commands output JSON for easy parsing by AI assistants or scripts.

Key design principles:
- **Offline ELF analysis** (analyze/disasm/search/compile) works without any device or server.
- **Device commands** go through the WebServer proxy. `--port` is optional when the server already has a device connected.
- **Remote control** lets you operate a device attached to another machine over the network.

## Requirements

- Python 3.8+
- ARM GCC toolchain (`arm-none-eabi-gcc`) — for offline compilation
- pyserial (`pip install pyserial`) — for device communication
- Optional: [Ghidra](https://ghidra-sre.org/) — for decompilation

## Installation

```bash
cd Tools/WebServer
pip install pyserial
```

## Global Options

```
fpb_cli.py [OPTIONS] <command> [args...]

Options:
  -v, --verbose              Enable verbose output
  --version                  Show version
  --port, -p <device>        Serial port (optional in proxy mode, see below)
  --baudrate, -b <rate>      Serial baudrate (default: 115200)
  --elf <path>               Path to ELF file
  --compile-commands <path>  Path to compile_commands.json
  --tx-chunk-size <bytes>    TX fragment size (0=disabled, default: 0)
  --tx-chunk-delay <secs>    Delay between TX fragments (default: 0.005)
  --max-retries <num>        Max retry attempts for file transfer (default: 10)
  --direct                   Force direct serial (skip proxy detection)
  --server-url <url>         WebServer URL (default: http://127.0.0.1:5500)
  --token <token>            Auth token for remote servers (or set FPB_TOKEN env)
```

### About `--port`

The serial port belongs to the **WebServer**, not the CLI. When a server is already running and has a device connected, `--port` is not needed — the CLI attaches to the server's existing connection. This applies to **both local and remote** servers: as long as `/api/status` reports `connected=true`, you can run device commands without `--port`.

`--port` is only required when:
- No server is running locally (triggers auto-launch + direct fallback).
- The local or remote server is reachable but has no device connected yet (tells it which port to open).

Without `--port` the CLI never opens a serial port directly — it either attaches to a server that already owns one, or stays offline (ELF analysis / compile commands always work). In remote mode the CLI still attaches to a reachable server even before a device is connected; device commands will fail until you connect a device, but offline ELF/compile commands remain available.

## Operating Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Offline (local) | No `--port`, no local server (or server has no device) | ELF analysis / compile only |
| Local proxy (port-less) | No `--port`, local server already has a device | Attach to server's existing connection |
| Local proxy | `--port` + local server running | Attach to server, forward device ops |
| Local auto-launch | `--port` + no local server | Auto-launch server, then proxy |
| Local direct | `--direct --port` | Open serial directly (bypass server) |
| Remote proxy | `--server-url http://remote:port` | Pure proxy to remote server, no auto-launch (attaches even if no device yet) |

## Remote Control

To operate a device attached to another machine:

```bash
# On the machine with the device (B): start WebServer
./main.py --host 0.0.0.0 --port 5500
#   🔑 Token: dd88d5df

# On the controlling machine (A):
export FPB_TOKEN=dd88d5df
fpb_cli.py --server-url http://192.168.1.20:5500 info
fpb_cli.py --server-url http://192.168.1.20:5500 mem-read 0x20000000 64
fpb_cli.py --server-url http://192.168.1.20:5500 serial-send "ps"

# If the remote server has no device connected yet:
fpb_cli.py --server-url http://192.168.1.20:5500 --port /dev/ttyACM0 connect
```

Notes:
- `--token` is required for non-localhost servers. Use `FPB_TOKEN` env to avoid shell history exposure.
- `--elf` / `--compile-commands` paths in inject commands refer to **server-side** paths.
- ELF analysis commands (analyze/disasm/search) always operate on the **local** ELF file.

## Commands

### Offline Commands (No Device Required)

#### `analyze` - Analyze a function

```bash
fpb_cli.py analyze <elf_path> <func_name>
```

Returns address, signature, and assembly line count.

#### `disasm` - Get disassembly

```bash
fpb_cli.py disasm <elf_path> <func_name>
```

#### `decompile` - Decompile to pseudo-C

```bash
fpb_cli.py decompile <elf_path> <func_name>
```

Requires Ghidra. Set `ghidra_path` in config or ensure `analyzeHeadless` is in PATH.

#### `signature` - Get function signature

```bash
fpb_cli.py signature <elf_path> <func_name>
```

#### `search` - Search for functions

```bash
fpb_cli.py search <elf_path> <pattern>
```

Returns up to 20 matching symbols with addresses.

#### `get-symbols` - Get all symbols from ELF

```bash
fpb_cli.py get-symbols <elf_path> [--filter <pattern>] [--limit <num>]
```

More comprehensive than `search` — returns all symbol types via `nm`.

#### `compile` - Compile patch (offline validation)

```bash
fpb_cli.py compile <source_file> --elf <elf> --compile-commands <path> [--addr <base>]
```

Verifies the patch compiles correctly without needing a device.

### Connection Commands

#### `connect` - Connect to device

```bash
fpb_cli.py --port /dev/ttyACM0 connect
```

#### `disconnect` - Disconnect from device

```bash
fpb_cli.py disconnect
```

#### `server-stop` - Stop CLI-launched WebServer

```bash
fpb_cli.py server-stop [--server-port <port>]
```

### Device Commands (Requires Device)

#### `info` - Get device FPB info

```bash
fpb_cli.py info
```

Returns FPB version, slot count, active patches, and build time.

#### `inject` - Inject patch to device

```bash
fpb_cli.py inject <target_func> <source_file> [options]

Options:
  --mode <mode>   Patch mode: trampoline|debugmon|direct (default: trampoline)
  --comp <num>    FPB slot number (-1 for auto, default: -1)
  --verify        Verify patch after injection
```

**Example:**
```bash
fpb_cli.py --elf firmware.elf --compile-commands build/compile_commands.json \
    inject digitalWrite patch.c
```

#### `unpatch` - Remove patch

```bash
fpb_cli.py unpatch --comp <slot>
fpb_cli.py unpatch --all
```

#### `test-serial` - Test serial throughput

```bash
fpb_cli.py test-serial [--start-size 16] [--max-size 4096] [--timeout 2.0]
```

3-phase probing to find optimal transfer parameters.

### Serial I/O Commands

#### `serial-send` - Send data to device

```bash
fpb_cli.py serial-send <data> [--no-read] [--timeout 1.0]
```

> WARNING: Avoid sending `fl` commands directly — use `inject`/`unpatch`/`info` instead.

#### `serial-read` - Read serial output

```bash
fpb_cli.py serial-read [--timeout 1.0] [--lines 50] [--since <cursor>]
```

`--since` enables incremental reads: pass the `raw_next` value from the previous response to get only new data.

### Memory Access Commands

#### `mem-read` - Read device memory

```bash
fpb_cli.py mem-read <addr> <length> [--fmt hex|raw|u32]
```

#### `mem-write` - Write to device memory

```bash
fpb_cli.py mem-write <addr> <hex_data>
```

#### `mem-dump` - Dump memory to file

```bash
fpb_cli.py mem-dump <addr> <length> <output_file>
```

### File Transfer Commands

#### `file-list` - List device directory

```bash
fpb_cli.py file-list [path]
```

#### `file-stat` - Get file info

```bash
fpb_cli.py file-stat <path>
```

#### `file-download` - Download file from device

```bash
fpb_cli.py file-download <remote_path> <local_path>
```

#### `file-upload` - Upload file to device

```bash
fpb_cli.py file-upload <local_path> <remote_path>
```

#### `file-remove` - Remove file on device

```bash
fpb_cli.py file-remove <path>
```

#### `file-mkdir` - Create directory on device

```bash
fpb_cli.py file-mkdir <path>
```

#### `file-rename` - Rename file/directory on device

```bash
fpb_cli.py file-rename <old_path> <new_path>
```

## Typical Workflow

```bash
# Step 1: Search for target functions (offline)
fpb_cli.py search firmware.elf "write"

# Step 2: Analyze the target function
fpb_cli.py analyze firmware.elf digitalWrite

# Step 3: Compile and validate patch offline
fpb_cli.py compile patch.c --elf firmware.elf --compile-commands build/compile_commands.json

# Step 4: Inject to device
fpb_cli.py --port /dev/ttyACM0 --elf firmware.elf \
    --compile-commands build/compile_commands.json \
    inject digitalWrite patch.c

# Step 5: Verify or rollback
fpb_cli.py info
fpb_cli.py unpatch --comp 0
```

## Writing Patch Code

Create a source file with `/* FPB_INJECT */` marker:

```c
// patch_digitalWrite.c
#include <stdint.h>
#include <stdio.h>

/* FPB_INJECT */
void digitalWrite(uint8_t pin, uint8_t val) {
    printf("Patched: pin=%d val=%d\r\n", (int)pin, (int)val);
}
```

The function name must match the target function you want to replace in the firmware.

> **Note**: Calling the original function from injected code is NOT supported due to FPB hardware limitations.

### Patch Modes

| Mode | Description | FPB Version |
|------|-------------|-------------|
| `trampoline` | Code trampoline (default) | v1 only |
| `debugmon` | DebugMonitor exception | v1 and v2 |
| `direct` | Direct code replacement | v1 only |

FPB v2 devices auto-switch to `debugmon` mode regardless of the requested mode.

## Output Format

All commands return JSON to stdout:

```json
{"success": true, ...}
{"success": false, "error": "Error message"}
```

Verbose logging goes to stderr (`-v` flag).

## Tips for AI Agents

1. Check the `success` field before processing results.
2. Use `jq` for filtering: `fpb_cli.py search firmware.elf gpio | jq '.symbols[].name'`
3. **`--port` is optional** when a WebServer is already running with a connected device.
4. FPB slot count varies by device (typically 6 for v1, 8 for v2).
5. Patch functions MUST include `/* FPB_INJECT */` marker comment.
6. For remote devices, set `FPB_TOKEN` env and use `--server-url`.
7. Paths in `inject` via proxy refer to the **server's** filesystem.

## Related Documentation

- [Architecture](Architecture.md) - Technical implementation details
- [WebServer Guide](../Tools/WebServer/docs/) - Web-based injection interface
