# FPBInject WebServer

The WebServer (`fpbinject-server`) is the host-side workbench. It owns the
serial port, serves a browser UI, and exposes a REST API that the
[CLI](CLI.md) and the [Python SDK](SDK.md) use as a proxy.

## Features

- **Hot patching**: compile, upload and patch a function in about a second, no reflashing
- **Marker-based development**: mark functions with `/* FPB_INJECT */`, optionally re-inject on every save
- **Symbols**: search the ELF symbol table, view disassembly or decompiled source (Ghidra, optional)
- **Watch**: evaluate variables and expressions from the ELF debug info against live device memory
- **File transfer**: browse, upload and download device files with CRC checks and drag-and-drop
- **Quick commands**: one-click serial commands and timed macros
- **Terminals**: tool log (OUTPUT) and raw serial (SERIAL PORT)
- **Remote use**: token authentication and mDNS advertisement, so one workbench can be shared on the LAN
- **Virtual serial passthrough**: mirror the device stream to a PTY for other tools
- **Tutorial**: guided walkthrough, reachable from the title bar

## Installation

Requirements: Python 3.9+ and an ARM GCC toolchain (`arm-none-eabi-gcc`) for compiling patches.

```bash
pip install fpbinject          # or: pip install --pre fpbinject
```

Python dependencies (Flask, pyserial, zeroconf, ...) are installed with the
package. From a source checkout run `pip install .` in the repository root.

## Start the Server

```bash
fpbinject-server                         # http://127.0.0.1:5500
fpbinject-server --http-port 5501        # change the HTTP port
fpbinject-server --port /dev/ttyACM0 --baudrate 921600 --auto-connect
fpbinject-server --host 0.0.0.0          # reachable from the LAN (token required)
```

| Option | Meaning |
|--------|---------|
| `--host` | Bind address (default `0.0.0.0`) |
| `--http-port` | HTTP port (default `5500`) |
| `--no-browser` | Do not open a browser on start |
| `--no-auth` | Disable token authentication for non-localhost access |
| `--no-mdns` | Do not advertise the server over mDNS |
| `--skip-port-check` | Start even if the HTTP port looks busy |
| `--config <file>` | Config file (see below) |
| `--debug` | Flask debug mode |

Serial and transfer flags (`--port`, `--baudrate`, `--auto-connect`,
`--data-bits`, `--parity`, `--stop-bits`, `--flow-control`, `--upload-chunk-size`,
`--download-chunk-size`, `--serial-tx-fragment-size`, `--serial-tx-fragment-delay`,
`--transfer-max-retries`, ...) come from the shared config schema, so the
server and the `fpbinject` CLI accept the same options. `--port` selects the
**serial device**; the web server's TCP port is `--http-port`.

Quit other programs that hold the serial port (`minicom`, ...) first.

### Config file

Settings are stored as JSON. The path is chosen in this order:

1. `--config <file>` (created on first save)
2. an existing `./.fpbinject.json`, then `./config.json`, then the legacy `config.json` next to the installed package
3. otherwise, in an interactive terminal the server offers to create `./.fpbinject.json`; when non-interactive (CI, auto-launched by the CLI) it runs with in-memory defaults and saves nothing

### Authentication

Requests from `localhost` need no token. For other hosts the server prints a
token in its startup banner; open the printed URL (it carries `?token=...`),
or pass the token to the CLI/SDK with `--token` / `FPB_TOKEN`.
`--no-auth` turns this off. Tokens are never sent over mDNS.

## Configuration

Settings are edited in the **CONFIGURATION** section of the sidebar and are
saved to the config file. The main ones:

| Group | Keys |
|-------|------|
| Project | `elf_path`, `compile_commands_path`, `toolchain_path` |
| Inject | `patch_mode` (`trampoline`, `debugmon`, `direct`), `watch_dirs`, `auto_compile` |
| Transfer | `upload_chunk_size`, `download_chunk_size`, `serial_tx_fragment_size`, `serial_tx_fragment_delay`, `transfer_max_retries`, `wakeup_shell_cnt` |
| Logging | `log_file_enabled`, `log_file_path`, `log_file_append`, `log_file_timestamp`, `serial_echo_enabled` |
| Tools | `ghidra_path`, `enable_decompile`, `external_gdb_port` (default 3333, 0 disables), `vserial_enable`, `vserial_symlink` |
| UI | `ui_theme`, `ui_language` |

Serial connection settings (`port`, `baudrate`, `data_bits`, ...) live in the
**CONNECTION** section. Click **Connect** to open the port.

`GET /api/config/schema` returns the full list with defaults, ranges and tooltips.

## Usage

### 1. Mark functions for injection

```c
/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void my_function(int arg) {
    // Patch implementation
}
```

The marker is matched case-insensitively and may be written as
`/* FPB_INJECT */`, `/* FPB-INJECT */`, `/*FPB_INJECT*/` or `// FPB_INJECT`.
The function name must match the firmware function you want to replace.

### 2. Manual injection

Search a symbol, open its disassembly, write the replacement and press
**Inject**. The server compiles the patch against `compile_commands.json`,
allocates device memory, uploads the code and configures the redirection.
Injection can be cancelled while it runs.

### 3. Auto-injection

Add the source directories to `watch_dirs` and start the file watcher. On save,
the server detects the markers, recompiles and re-injects. It also watches the
ELF and warns when the firmware on the device no longer matches it.

### 4. Patch modes

| Mode | Description |
|------|-------------|
| `trampoline` | FPB redirects to a trampoline in Flash that jumps to RAM (FPB v1) |
| `debugmon` | FPB breakpoint handled by the DebugMonitor exception (FPB v1 and v2) |
| `direct` | Direct code replacement (FPB v1) |

FPB v2 devices (ARMv8-M) are always patched in `debugmon` mode.
See [Architecture](Architecture.md#debugmonitor-unavailable-on-trustzone-targets)
if `debugmon` fails with `DebugMonitor init failed`.

## Web Interface

| Area | Content |
|------|---------|
| Activity bar | Switches between the sidebar sections |
| CONNECTION | Serial port, baudrate, connect/disconnect, virtual serial |
| DEVICE INFO | FPB version, patch slots, build time, exec support |
| QUICK COMMANDS | Single commands and macros, groups, import/export |
| FILE TRANSFER | Device file browser, upload/download with progress |
| SYMBOLS | Symbol search, disassembly, decompile |
| WATCH | Variable and expression watch, live memory read/write |
| CONFIGURATION | Project, inject, transfer, logging, tools |
| Editor | Monaco editor for patches and viewed sources |
| Terminal | **OUTPUT** (tool log) and **SERIAL PORT** (raw device stream) |

### Quick commands

Commands are stored in the browser. A command is sent to the serial port as
text; a macro sends several commands with a delay before each step.
In the command text, `\n`, `\r`, `\t`, `\\` and `\xHH` (any byte, for example
`\x03` for Ctrl-C) are replaced before sending; turn off "Append newline" for
steps that must not end with a newline. Commands can be exported to and
imported from a JSON file to share with a team.

After upgrading the package, restart the server and force-reload the page
(Ctrl+F5), otherwise the browser keeps the old scripts.

## REST API

All endpoints are under `/api`. Responses are JSON; long operations also have
`/stream` variants that report progress as server-sent events. The CLI and SDK
call these endpoints, so prefer them over scripting the API directly.

| Group | Endpoints |
|-------|-----------|
| Connection | `GET /ports`, `POST /connect`, `POST /disconnect`, `GET /status` |
| Config | `GET`/`POST /config`, `GET /config/schema` |
| FPB | `GET /fpb/info`, `POST /fpb/inject` (`/stream`, `/multi`, `/multi/stream`, `/cancel`), `POST /fpb/unpatch`, `POST /fpb/enable`, `POST /fpb/ping`, `POST /fpb/test-serial`, `POST /fpb/exec`, `POST /fpb/mem-read`, `POST /fpb/mem-write` |
| Patch source | `GET`/`POST /patch/source`, `GET /patch/template`, `POST /patch/auto_generate`, `POST /patch/detect_markers`, `POST /patch/preview` |
| Symbols | `GET /symbols`, `/symbols/search`, `/symbols/disasm`, `/symbols/decompile` (`/stream`), `/symbols/signature`, `/symbols/value`, `POST /symbols/reload`, `/symbols/read`, `/symbols/write` |
| Watch expressions | `/watch_expr/add`, `/remove`, `/clear`, `/list`, `/evaluate`, `/deref` |
| File watcher | `/watch/start`, `/stop`, `/status`, `/clear`, `/elf_status`, `/elf_acknowledge`, `/auto_inject_status`, `/auto_inject_reset`, `/autoinject/trigger` |
| Serial | `POST /serial/send`, `GET /serial/read`, `GET /logs`, `GET /logs/stream`, `GET /raw_log`, `POST /log/clear`, `POST /raw_log/clear`, `/log_file/start`, `/stop`, `/status` |
| File transfer | `/transfer/list`, `/stat`, `/upload`, `/download`, `/download-sync`, `/mkdir`, `/rename`, `/delete`, `/cancel` |
| Memory | `GET /memory/read`, `POST /memory/read/stream`, `POST /memory/write` |
| Virtual serial | `POST /vserial/start`, `POST /vserial/stop`, `GET /vserial/status` |

The UI receives logs through `GET /api/logs/stream` (server-sent events).
There is no WebSocket endpoint.

## Troubleshooting

### Connection issues

```bash
# Serial port permission
sudo usermod -a -G dialout $USER   # then log out and in
sudo chmod 666 /dev/ttyACM0        # temporary, lost on reboot
```

Also check the baudrate, that no other program holds the port, and that the
firmware was built with `FPBINJECT=y`. In a serial terminal, typing `fl`
should print the `fl>` prompt.

### Transfers fail or time out

Run `fpbinject doctor` to probe the link; it prints chunk-size and TX-fragment
settings to apply. If `nsh` drops characters, set `serial_tx_fragment_size`
(for example 16 bytes) and `serial_tx_fragment_delay` (for example 2 ms).

### Compilation errors

- the ARM toolchain is in `PATH` or `toolchain_path` is set
- `compile_commands.json` exists and is current
- inline functions or code pulled in with `#include "*.c"` cannot be compiled on their own; copy the function into the patch file

### Injection fails

- the device is running the function loader
- the ELF matches the running firmware (the UI warns on a mismatch)
- the device has free RAM for the patch
- on ARMv8-M with TrustZone, `debugmon` needs a Non-secure-owned DebugMonitor (see above)

## Source layout

```
Tools/WebServer/
├── main.py           # Flask app and server entry (fpbinject-server)
├── fpb_inject.py     # Injection workflow
├── client.py         # Python SDK (Client)
├── cli/              # fpbinject command
├── core/             # Serial protocol, transfer, compiler, ELF, config schema
├── app/              # Routes and auth middleware
├── services/         # Background services
├── templates/        # HTML templates
├── static/           # JS/CSS assets
└── tests/            # Test suite
```

## Related Documentation

- [CLI Tool](CLI.md) - Command-line interface and AI integration guide
- [Python SDK](SDK.md) - `Client` API
- [Architecture](Architecture.md) - Technical details
