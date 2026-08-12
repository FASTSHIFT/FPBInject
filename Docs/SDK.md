# FPBInject Python SDK

The `fpbinject` package ships a stable Python SDK — a single `Client` facade
that covers every capability the CLI exposes: ELF analysis, code injection,
memory/serial/file operations, and the virtual serial passthrough.

```bash
pip install fpbinject
```

```python
from fpbinject import Client

client = Client.discover(token="...")      # auto-find a WebServer on the LAN
client.serial_send("help\r\n")
print(client.serial_read()["raw_data"])
```

> Use this SDK instead of importing internal modules (`cli.*`, `core.*`).
> Those are implementation details and may change without notice; `Client`
> is the supported, versioned surface.

## Contents

- [Connecting](#connecting)
- [Return values & errors](#return-values--errors)
- [Offline: ELF analysis](#offline-elf-analysis)
- [Device info & injection](#device-info--injection)
- [Memory](#memory)
- [Serial](#serial)
- [Files](#files)
- [Connection & virtual serial](#connection--virtual-serial)
- [Full method reference](#full-method-reference)

## Connecting

There are three ways to create a `Client`:

```python
from fpbinject import Client

# 1. Direct — connect to a known WebServer
client = Client("http://127.0.0.1:5500", token="021c1509")

# 2. Discover — find a WebServer via mDNS (like `fpbinject discover`)
client = Client.discover(token="021c1509")               # unique server on LAN
client = Client.discover(handle="bench-pc:5500")         # pick a specific one

# 3. Offline — ELF analysis only, no server or device
off = Client.offline(toolchain_path="/opt/toolchain/bin")
```

**Token** resolution matches the CLI: explicit `token=` wins, otherwise the
`FPB_TOKEN` environment variable is used. Tokens are never sent over mDNS;
obtain one from the WebServer startup log.

**List servers** without connecting:

```python
for s in Client.list_servers(timeout=3.0):
    print(s.handle, s.url, s.version)
```

**Auto-launch** a local server if none is running:

```python
client = Client()          # defaults to http://127.0.0.1:5500
client.ensure_server()     # starts a headless server if needed
```

**Context manager** for cleanup:

```python
with Client.discover() as client:
    client.info()
```

## Return values & errors

Methods return the **raw JSON response as a `dict`**, identical to the REST
API and CLI JSON output. For example:

```python
info = client.info()
# {"success": True, "info": {"num_comparators": 6, ...}}
if info["success"]:
    print(info["info"]["num_comparators"])
```

Errors raise exceptions:

| Exception | When |
|-----------|------|
| `AuthError` | WebServer returned 401/403 (missing/invalid token) |
| `ServerUnavailable` | No server reachable / discovery found none |
| `DeviceNotConnected` | Operation needs a device but none is connected |
| `FPBError` | Base class for all of the above and other errors |

```python
from fpbinject import Client, AuthError, ServerUnavailable

try:
    client = Client.discover(token="...")
    client.info()
except ServerUnavailable:
    print("start the WebServer first")
except AuthError:
    print("check your token")
```

## Offline: ELF analysis

No device or server required — analyze a firmware ELF locally.

```python
off = Client.offline(toolchain_path="/opt/toolchain/bin")

off.analyze("firmware.elf", "target_function")   # addr + signature + asm size
off.disasm("firmware.elf", "target_function")     # {"disasm": "..."}
off.decompile("firmware.elf", "target_function")  # requires Ghidra configured
off.signature("firmware.elf", "target_function")  # "void target_function(int)"
off.search("firmware.elf", "gpio")                # symbols matching a pattern
off.get_symbols("firmware.elf", filter="uart", limit=50)
off.compile("patch.c", elf="firmware.elf",
            compile_commands="build/compile_commands.json")
```

## Device info & injection

```python
client.info()                      # FPB info: version, comparators, slots
client.test_serial()               # probe max serial transfer size

# Inject a patch (compiles + uploads + patches)
client.inject("target_function", "patch.c",
              elf="firmware.elf",
              patch_mode="trampoline",   # or "debugmon" / "direct"
              comp=-1)                   # -1 = auto-assign slot

client.unpatch(comp=0)             # remove one slot
client.unpatch(all=True)           # remove all patches
```

## Memory

```python
client.mem_read(0x20000000, 16)             # {"data": "..."} (hex by default)
client.mem_read(0x20000000, 16, fmt="u32")  # 32-bit words
client.mem_write(0x20000000, "deadbeef")    # hex bytes
client.mem_dump(0x20000000, 4096, "dump.bin")  # region -> local file
```

## Serial

```python
client.serial_send("am start com.example.app\r\n")
client.serial_read()                 # {"raw_data": "...", "raw_next": <cursor>}

# Incremental read using a cursor
cur = client.serial_read()["raw_next"]
client.serial_send("run_test\r\n")
delta = client.serial_read(since=cur)["raw_data"]
```

> **Deep-sleep note:** some devices ignore `serial_send` while asleep. A
> transfer op wakes them — use `client.wake()` (a shortcut for
> `file_stat("/")`) before sending commands if needed.

```python
client.wake()
client.serial_send("...\r\n")
```

## Files

```python
client.file_list("/data")                        # directory entries
client.file_stat("/data/log.bin")                 # size/type/...
client.file_download("/data/log.bin", "log.bin")  # device -> local
client.file_upload("patch.bin", "/data/patch.bin")# local -> device
client.file_remove("/data/old.bin")
client.file_mkdir("/data/new")
client.file_rename("/data/a.bin", "/data/b.bin")
```

## Connection & virtual serial

```python
# Ask the server to open a physical port (proxy mode)
client.connect("/dev/ttyACM0", baudrate=921600)
client.disconnect()

# Virtual serial passthrough (Linux/macOS): exposes a PTY device file that
# external tools (minicom, pyserial) can open while the server keeps the port.
client.vserial_start()                 # symlink derived from the port name
client.vserial_start(symlink="/tmp/mytty")
client.vserial_status()                # {"slave": "/dev/pts/N", "symlink": ...}
client.vserial_stop()
```

## Full method reference

| Method | Mode | Purpose |
|--------|------|---------|
| `Client(base_url, token=None, timeout=30)` | — | Direct connect |
| `Client.discover(token=None, timeout=3.0, handle=None)` | — | mDNS auto-discovery |
| `Client.offline(toolchain_path=None)` | — | Offline (no server) |
| `Client.list_servers(timeout=3.0)` | — | List servers via mDNS |
| `ensure_server()` | proxy | Auto-launch local server |
| `connected` (property) | proxy | Device connected? |
| `status()` | proxy | Full server status |
| `analyze(elf, func)` | offline | Address + signature + asm size |
| `disasm(elf, func)` | offline | Disassembly |
| `decompile(elf, func)` | offline | Ghidra decompile |
| `signature(elf, func)` | offline | Function signature |
| `search(elf, pattern, limit=20)` | offline | Symbols matching pattern |
| `get_symbols(elf, filter=None, limit=0)` | offline | All symbols |
| `compile(source, elf=None, base_addr=..., compile_commands=None)` | offline | Compile a patch |
| `info()` | proxy | Device FPB info |
| `test_serial(start_size=16, max_size=4096, timeout=2.0)` | proxy | Serial throughput |
| `inject(target_func, source, elf=None, compile_commands=None, patch_mode="trampoline", comp=-1)` | proxy | Inject a patch |
| `unpatch(comp=0, all=False)` | proxy | Remove patch(es) |
| `mem_read(addr, length, fmt="hex")` | proxy | Read memory |
| `mem_write(addr, hexdata)` | proxy | Write memory |
| `mem_dump(addr, length, out_path)` | proxy | Dump region to file |
| `serial_send(data)` | proxy | Send serial data |
| `serial_read(since=0)` | proxy | Read serial log |
| `wake()` | proxy | Wake a sleeping device |
| `file_list(path="/")` | proxy | List directory |
| `file_stat(path)` | proxy | File info |
| `file_download(remote, local)` | proxy | Download file |
| `file_upload(local, remote)` | proxy | Upload file |
| `file_remove(path)` | proxy | Delete file |
| `file_mkdir(path)` | proxy | Create directory |
| `file_rename(old, new)` | proxy | Rename |
| `connect(port, baudrate=115200)` | proxy | Open a serial port |
| `disconnect()` | proxy | Close the serial port |
| `vserial_start(symlink=None)` | proxy | Start virtual serial |
| `vserial_status()` | proxy | Virtual serial status |
| `vserial_stop()` | proxy | Stop virtual serial |

See also: [CLI Reference](CLI.md) · [Architecture](Architecture.md) · [WebServer Guide](WebServer.md)
