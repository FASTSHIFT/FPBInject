# FPBInject Python SDK

The `fpbinject` package ships a stable Python SDK — a single `Client` facade
that covers every capability the CLI exposes: ELF analysis, code injection,
memory/serial/file operations, the virtual serial passthrough, and server
administration.

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
- [Modes at a glance](#modes-at-a-glance)
- [Return values & errors](#return-values--errors)
- [Offline: ELF analysis](#offline-elf-analysis)
- [Device info & injection](#device-info--injection)
- [Memory](#memory)
- [Serial](#serial)
- [Files](#files)
- [Connection & virtual serial](#connection--virtual-serial)
- [Cookbook: multi-step workflows](#cookbook-multi-step-workflows)
- [Full method reference](#full-method-reference)

## Connecting

There are four ways to create a `Client`:

```python
from fpbinject import Client

# 1. Explicit URL — connect to a known WebServer (proxy mode)
client = Client("http://127.0.0.1:5500", token="021c1509")

# 2. Discover — find a WebServer via mDNS (like `fpbinject discover`)
client = Client.discover(token="021c1509")               # unique server on LAN
client = Client.discover(handle="bench-pc:5500")         # pick a specific one

# 3. Direct — open the serial port yourself, no WebServer needed
#    (SDK equivalent of `fpbinject --port ... --direct`)
with Client.direct("/dev/ttyACM0", baudrate=115200) as dev:
    print(dev.info())

# 4. Offline — ELF analysis only, no server or device
off = Client.offline(toolchain_path="/opt/toolchain/bin")
```

**Direct mode** opens the serial port in-process and drives the device
through the same core code the CLI's `--direct` path uses — handy for
headless scripts and CI where you'd rather not run a separate server. It
locks the port for the client's lifetime, so use it as a context manager (or
call `close()`) to release the port. The one thing it cannot do is the
virtual serial passthrough (see [below](#connection--virtual-serial)).

**Token** resolution matches the CLI: explicit `token=` wins, otherwise the
`FPB_TOKEN` environment variable is used. Tokens are never sent over mDNS;
obtain one from the WebServer startup log. (Tokens apply to proxy mode only;
direct mode talks straight to the device.)

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

**Context manager** for cleanup (required for direct mode to release the
serial port; harmless for the others):

```python
with Client.discover() as client:
    client.info()

with Client.direct("/dev/ttyACM0") as dev:
    dev.info()          # port is released automatically on exit
```

## Modes at a glance

| Capability | Proxy (`Client` / `discover`) | Direct (`Client.direct`) | Offline (`Client.offline`) |
|------------|:---:|:---:|:---:|
| ELF analysis (analyze/disasm/decompile/signature/search/get_symbols/compile) | ✓ | ✓ | ✓ |
| Device info / test_serial | ✓ | ✓ | — |
| inject / unpatch | ✓ | ✓ | — |
| Memory (mem_read/write/dump) | ✓ | ✓ | — |
| Serial (serial_send/read) | ✓ | ✓ | — |
| Files (file_*) | ✓ | ✓ | — |
| Virtual serial (vserial_*) | ✓ | — ¹ | — |
| connect / disconnect | ✓ ² | — ³ | — |
| ensure_server / status | ✓ | — | — |
| stop_server (static) | ✓ | ✓ | ✓ |

¹ A PTY must be hosted by a long-lived process; a transient direct client
cannot keep the device node alive. Use proxy mode for virtual serial.
² Proxy mode asks the server to open/close the physical port.
³ Direct mode owns the port for its whole lifetime — pass the port to
`Client.direct(...)` and release it with `close()` / the context manager.

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

# Context-safe windowed read (proxy mode): never returns more than max_bytes,
# so a large backlog cannot blow up memory. Page with the returned cursor,
# skip the backlog with drop=True, or grab only the newest bytes with tail.
win = client.serial_read_window(since=0, max_bytes=4096)
# {"data": "...", "next": <cursor>, "pending_bytes": N, "buffer_overflowed": bool}
client.serial_read_window(drop=True)          # skip backlog, advance cursor
client.serial_read_window(tail=2048)          # newest 2 KB only
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

# Optional progress callback (direct mode): callback(done_bytes, total_bytes).
# Serial throughput depends on baudrate + link quality; use this callback to
# drive your own progress UI/logging (compute speed/ETA from timestamps).
client.file_upload(
    "app.bin", "/data/app.bin",
    progress=lambda done, total: print(f"{done}/{total}", end="\r"),
)
```

## Connection & virtual serial

```python
# Proxy mode: ask the server to open/close a physical port.
client.connect("/dev/ttyACM0", baudrate=921600)
client.disconnect()

# Direct mode owns the port for the client's whole lifetime instead —
# pass the port to Client.direct() and release it with close()/`with`.

# Virtual serial passthrough (Linux/macOS, proxy mode only): exposes a PTY
# device file that external tools (minicom, pyserial) can open while the
# server keeps the physical port. Direct mode cannot host this (see
# "Modes at a glance").
client.vserial_start()                 # symlink derived from the port name
client.vserial_start(symlink="/tmp/mytty")
client.vserial_status()                # {"slave": "/dev/pts/N", "symlink": ...}
client.vserial_stop()
```

## Server administration

```python
# Stop a WebServer that the CLI auto-launched in the background
# (equivalent to `fpbinject server-stop`). Static — no client needed.
Client.stop_server(5500)               # {"success": True, "message": "..."}
```

## Cookbook: multi-step workflows

These are the cases where the SDK beats chaining the CLI: real return values,
in-process loops, retries and orchestration — no JSON re-parsing between steps.

### Batch-inject many functions

```python
from fpbinject import Client

patches = {
    "digitalWrite": "patches/digitalWrite.c",
    "digitalRead": "patches/digitalRead.c",
    "analogWrite": "patches/analogWrite.c",
}
results = {}
with Client.direct("/dev/ttyACM0") as dev:
    for func, src in patches.items():
        try:
            dev.inject(func, src, elf="firmware.elf")
            results[func] = "ok"
        except Exception as e:               # keep going on a single failure
            results[func] = f"failed: {e}"
print(results)
```

### Download then verify (byte-for-byte)

```python
import hashlib
from fpbinject import Client

with Client.direct("/dev/ttyACM0") as dev:
    dev.file_download("/data/blob.bin", "blob.bin")
    st = dev.file_stat("/data/blob.bin")["stat"]
local = open("blob.bin", "rb").read()
assert len(local) == st["size"], "size mismatch"
print("sha256", hashlib.sha256(local).hexdigest())
```

### Probe the link, then transfer

```python
from fpbinject import Client

with Client.direct("/dev/ttyACM0") as dev:
    probe = dev.test_serial()               # reliability-sampled throughput probe
    print("recommended upload chunk:", probe.get("recommended_upload_chunk_size"))
    print("fragmentation needed:", probe.get("fragment_needed"))
    # Transfers already retry on CRC/loss (see transfer_max_retries); the probe
    # tells you whether to lower chunk sizes or enable TX fragmentation. Apply
    # those as connection args (CLI flags / server config) for the session.
    dev.file_upload("app.bin", "/data/app.bin")
```

### Drive several devices in parallel

```python
from concurrent.futures import ThreadPoolExecutor
from fpbinject import Client

ports = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2"]

def flash(port):
    with Client.direct(port) as dev:
        dev.file_upload("app.bin", "/data/app.bin")
        return port, "done"

with ThreadPoolExecutor(max_workers=len(ports)) as pool:
    for port, status in pool.map(flash, ports):
        print(port, status)
```

### Context-safe serial capture (won't blow up memory)

```python
from fpbinject import Client

# Proxy mode exposes the windowed reader; page with the returned cursor.
client = Client.discover(token="...")
cursor, captured = 0, []
for _ in range(50):                          # bounded loop
    win = client.serial_read_window(since=cursor, max_bytes=4096)
    if not win.get("data"):
        break
    captured.append(win["data"])
    cursor = win["next"]
    if win.get("pending_bytes", 0) == 0:
        break
```

## Full method reference

"Mode" is the mode(s) each method works in: **proxy** (`Client`/`discover`),
**direct** (`Client.direct`), **offline** (`Client.offline`).

| Method | Mode | Purpose |
|--------|------|---------|
| `Client(base_url, token=None, timeout=30)` | — | Explicit-URL proxy client |
| `Client.discover(token=None, timeout=3.0, handle=None)` | — | mDNS auto-discovery |
| `Client.direct(port, baudrate=115200, toolchain_path=None)` | — | Open serial port directly |
| `Client.offline(toolchain_path=None)` | — | Offline (no server/device) |
| `Client.list_servers(timeout=3.0)` | — | List servers via mDNS |
| `Client.stop_server(port=5500)` | static | Stop a CLI-launched server |
| `close()` / `with` | all | Release resources (frees the port in direct mode) |
| `ensure_server()` | proxy | Auto-launch local server |
| `connected` (property) | proxy, direct | Device connected? |
| `status()` | proxy | Full server status |
| `analyze(elf, func)` | proxy·direct·offline | Address + signature + asm size |
| `disasm(elf, func)` | proxy·direct·offline | Disassembly |
| `decompile(elf, func)` | proxy·direct·offline | Ghidra decompile |
| `signature(elf, func)` | proxy·direct·offline | Function signature |
| `search(elf, pattern, limit=20)` | proxy·direct·offline | Symbols matching pattern |
| `get_symbols(elf, filter=None, limit=0)` | proxy·direct·offline | All symbols |
| `compile(source, elf=None, base_addr=..., compile_commands=None)` | proxy·direct·offline | Compile a patch |
| `info()` | proxy, direct | Device FPB info |
| `test_serial(start_size=16, max_size=4096, timeout=2.0)` | proxy, direct | Serial throughput |
| `inject(target_func, source, elf=None, compile_commands=None, patch_mode="trampoline", comp=-1)` | proxy, direct | Inject a patch |
| `unpatch(comp=0, all=False)` | proxy, direct | Remove patch(es) |
| `mem_read(addr, length, fmt="hex")` | proxy, direct | Read memory |
| `mem_write(addr, hexdata)` | proxy, direct | Write memory |
| `mem_dump(addr, length, out_path)` | proxy, direct | Dump region to file |
| `serial_send(data)` | proxy, direct | Send serial data |
| `serial_read(since=0)` | proxy, direct | Read serial log |
| `wake()` | proxy, direct | Wake a sleeping device |
| `file_list(path="/")` | proxy, direct | List directory |
| `file_stat(path)` | proxy, direct | File info |
| `file_download(remote, local)` | proxy, direct | Download file |
| `file_upload(local, remote)` | proxy, direct | Upload file |
| `file_remove(path)` | proxy, direct | Delete file |
| `file_mkdir(path)` | proxy, direct | Create directory |
| `file_rename(old, new)` | proxy, direct | Rename |
| `connect(port, baudrate=115200)` | proxy | Open a serial port |
| `disconnect()` | proxy | Close the serial port |
| `vserial_start(symlink=None)` | proxy | Start virtual serial |
| `vserial_status()` | proxy | Virtual serial status |
| `vserial_stop()` | proxy | Stop virtual serial |

See also: [CLI Reference](CLI.md) · [Architecture](Architecture.md) · [WebServer Guide](WebServer.md)
