# FPBInject Architecture

Technical documentation for the FPB-based code injection system.

## Overview

FPBInject enables runtime function hooking on ARM Cortex-M microcontrollers using the Flash Patch and Breakpoint (FPB) hardware unit. It redirects function calls to custom code in RAM without modifying Flash memory.

The system consists of four major components: **Lower Machine** (embedded firmware), **Upper Machine** (WebServer), **Compiler** (cross-compilation toolchain), and **GDB** (symbol resolution engine). They work together to achieve a complete injection workflow.

## System Architecture

### High-Level Overview

```mermaid
graph LR
    Browser["🌐 Browser<br/>Web UI / Terminal / Editor"]

    subgraph Upper["Upper Machine (Python · Flask)"]
        FPI["FPBInject<br/>Orchestrator"]
    end

    subgraph Tools["Host Tools"]
        CC["Compiler<br/>arm-none-eabi-gcc"]
        GDB["GDB<br/>DWARF Engine"]
    end

    subgraph Lower["Lower Machine (ARM Cortex-M)"]
        FW_CORE["Firmware<br/>fl_exec_cmd"]
        FPB_HW["FPB Hardware"]
    end

    Browser -->|"HTTP REST + SSE"| FPI
    FPI -->|"Invoke"| CC
    FPI -->|"GDB/MI"| GDB
    FPI ==>|"UART · Text Protocol<br/>Base64 + CRC-16"| FW_CORE
    GDB -.->|"RSP m/M → Serial"| FW_CORE
    FW_CORE --> FPB_HW
```

### Upper Machine (WebServer)

```mermaid
graph TB
    subgraph Routes["Flask Blueprints (REST API)"]
        R_CONN["connection.py<br/>/connect /status"]
        R_FPB["fpb.py<br/>/fpb/inject /unpatch"]
        R_PATCH["patch.py<br/>/patch/source"]
        R_SYM["symbols.py"]
        R_TRANS["transfer.py"]
        R_GDB["gdb.py"]
        R_WATCH["watch.py"]
    end

    subgraph Core["Core Modules"]
        FPI["FPBInject<br/>fpb_inject.py"]
        PROTO["FPBProtocol<br/>serial_protocol.py"]
        COMP["compile_inject<br/>compiler.py"]
        PGEN["PatchGenerator<br/>patch_generator.py"]
        ELF["elf_utils.py"]
        FT["FileTransfer<br/>file_transfer.py"]
    end

    subgraph GDBStack["GDB Stack"]
        GM["GDBManager"]
        GS["GDBSession"]
        GB["GDBRSPBridge"]
    end

    subgraph Services["Services"]
        DW["DeviceWorker<br/>Serial I/O Thread"]
        FW["FileWatcher<br/>Auto Inject"]
        STATE["AppState<br/>DeviceState"]
    end

    R_FPB --> FPI
    R_PATCH --> PGEN
    R_SYM --> GS
    R_TRANS --> FT
    R_GDB --> GM

    FPI --> PROTO
    FPI --> COMP
    FPI --> GS
    FPI --> PGEN
    GM --> GS
    GM --> GB
    GB -->|"RSP m/M"| PROTO

    FPI --> DW
    PROTO --> DW
    FW -->|"File Change"| FPI
    DW --> STATE
```

### Compiler Pipeline

```mermaid
graph LR
    CCJSON["compile_commands.json"] --> FLAGS["Extract Flags<br/>-I -D -mcpu ..."]
    FLAGS --> GCC["gcc -c<br/>→ patch.o"]
    GCC --> LD["ld -Tscript.ld<br/>--just-symbols=firmware.elf<br/>→ patch.elf"]
    LD --> OBJCOPY["objcopy -O binary<br/>→ patch.bin"]
    LD --> NM["nm<br/>→ symbols"]
    OBJCOPY --> BIN["Binary + Symbols"]
    NM --> BIN

    style BIN fill:#dfd,stroke:#0a0
```

> **Two-pass compilation**: First compile at placeholder address `0x20000000` to determine code size, then `alloc` on device, then recompile at the actual RAM address.

### Lower Machine (Firmware)

```mermaid
graph TB
    UART["UART RX"] --> STREAM["fl_stream<br/>Line Buffer + Parse"]
    STREAM --> EXEC["fl_exec_cmd<br/>argparse → Command Dispatch"]

    EXEC --> ALLOC["fl_allocator<br/>Block Allocator"]
    EXEC --> FILE["fl_file<br/>POSIX / LIBC / FATFS"]
    EXEC --> FPB_DRV["fpb_inject<br/>FPB Register Ops"]
    EXEC --> TRAMP["fpb_trampoline<br/>Flash Trampoline"]
    EXEC --> DBGMON["fpb_debugmon<br/>DebugMonitor Exception"]

    FPB_DRV --> FPB_HW["FPB Unit · 0xE0002000"]
    TRAMP --> FLASH["Flash · Trampoline Code"]
    TRAMP --> SRAM["SRAM · Target Addr Table"]
    DBGMON --> DEMCR["DEMCR · DebugMonitor Control"]
    DBGMON --> FPB_HW
```

## Injection Workflow (End-to-End)

```mermaid
sequenceDiagram
    actor User
    participant FW as FileWatcher
    participant FPI as FPBInject
    participant PG as PatchGenerator
    participant GDB as GDBSession
    participant CC as Compiler
    participant Proto as FPBProtocol
    participant DW as DeviceWorker
    participant Dev as Device (Firmware)

    User->>FW: Save source file (with FPB_INJECT marker)
    FW->>PG: Detect marked functions
    PG-->>FW: target_func_name
    FW->>FPI: inject(target_func, source)

    Note over FPI: 1. Symbol Resolution
    FPI->>GDB: lookup_symbol(target_func)
    GDB-->>FPI: orig_addr = 0x08001234

    Note over FPI: 2. First Compile (placeholder addr)
    FPI->>CC: compile(base_addr=0x20000000)
    CC-->>FPI: code_size = 256 bytes

    Note over FPI: 3. Device Memory Allocation
    FPI->>Proto: send_cmd("alloc --size 264")
    Proto->>DW: Submit to worker thread
    DW->>Dev: fl --cmd alloc --size 264
    Dev-->>DW: [FLOK] Allocated 264 at 0x20001000
    DW-->>Proto: Parse response
    Proto-->>FPI: alloc_addr = 0x20001000

    Note over FPI: 4. Second Compile (actual addr)
    FPI->>CC: compile(base_addr=0x20001000)
    CC-->>FPI: binary + symbols

    Note over FPI: 5. Chunked Upload
    loop Every 512 bytes
        FPI->>Proto: upload(offset, chunk, crc)
        Proto->>DW: Submit to worker thread
        DW->>Dev: fl --cmd upload --addr OFFSET --data BASE64 --crc CRC
        Dev-->>DW: [FLOK] Uploaded N bytes
    end

    Note over FPI: 6. Activate Patch
    FPI->>Proto: send_cmd("tpatch --comp 0 --orig 0x08001234 --target 0x20001000")
    Proto->>DW: Submit to worker thread
    DW->>Dev: fl --cmd tpatch ...
    Dev->>Dev: FPB REMAP → Trampoline → RAM
    Dev-->>DW: [FLOK] Trampoline 0: 0x08001234 → 0x20001000

    FPI-->>User: ✅ Injection Successful
```

## Communication Protocol Stack

```mermaid
graph LR
    subgraph L5["Application Layer"]
        CMD["fl --cmd ping/info/alloc/upload/patch/..."]
    end

    subgraph L4["Encoding Layer"]
        B64["Base64 Encoding (binary data)"]
        CRC["CRC-16 Checksum"]
    end

    subgraph L3["Framing Layer"]
        REQ["Request: fl --cmd CMD --arg VAL\\n"]
        RSP_OK["Success: [FLOK] message"]
        RSP_ERR["Failure: [FLERR] message"]
        RSP_DATA["Data: [FLOK] ... data=BASE64\\n[FLEND]"]
    end

    subgraph L2["Transport Layer"]
        UART["UART (pyserial ↔ fl_stream)"]
        CHUNK["Chunked TX (tx_chunk_size)"]
        RETRY["Auto Retry (max_retries)"]
    end

    subgraph L1["Physical Layer"]
        USB["USB-Serial / JTAG-UART"]
    end

    CMD --> B64 --> REQ --> CHUNK --> USB
    USB --> RSP_OK
    USB --> RSP_ERR
    USB --> RSP_DATA
    CRC -.->|"Verify"| B64
    RETRY -.->|"Retry on Failure"| CHUNK
```

## GDB Integration Architecture

```mermaid
graph TB
    subgraph IDE["External IDE (VS Code / CLion)"]
        CORTEX["Cortex-Debug<br/>target remote :3333"]
    end

    subgraph Upper["WebServer"]
        GM["GDBManager"]
        GS["GDBSession<br/>(pygdbmi)"]
        GB_INT["Internal RSP Bridge<br/>(Auto-assigned Port)"]
        GB_EXT["External RSP Bridge<br/>(Fixed Port 3333)"]
        PROTO2["FPBProtocol"]
        DW2["DeviceWorker"]
    end

    subgraph GDB_Proc2["GDB Process"]
        GDB2["arm-none-eabi-gdb<br/>Load firmware.elf"]
        DWARF2["DWARF Parser<br/>Symbol/Type/Addr"]
    end

    subgraph Device2["Device"]
        MEM["Device Memory"]
    end

    %% GDB as DWARF engine
    GM -->|"Start/Stop"| GS
    GM -->|"Start/Stop"| GB_INT
    GM -->|"Start/Stop"| GB_EXT
    GS -->|"GDB/MI<br/>file firmware.elf<br/>target remote :PORT"| GDB2
    GDB2 --> DWARF2
    GDB2 -->|"RSP m/M packets"| GB_INT
    GB_INT -->|"read_memory_fn<br/>write_memory_fn"| PROTO2
    PROTO2 --> DW2
    DW2 -->|"fl --cmd read/write"| MEM

    %% External IDE
    CORTEX -->|"RSP over TCP"| GB_EXT
    GB_EXT -->|"read_memory_fn<br/>write_memory_fn"| DW2

    style DWARF2 fill:#ffd,stroke:#aa0
```

The core value of GDB in FPBInject is not debugging, but serving as a **DWARF parsing engine**:

| Purpose | GDB Command | Caller |
|---------|-------------|--------|
| Symbol address resolution | `info address func_name` | `FPBInject._resolve_symbol_addr()` |
| Type information query | `ptype struct_name` | Frontend Watch expressions |
| Struct layout | `print sizeof(struct)` | Frontend symbol search |
| Function signature extraction | `whatis func_name` | CLI `signature` command |

The internal RSP Bridge forwards GDB memory read/write requests (`m`/`M` packets) to device serial commands (`fl --cmd read/write`), enabling GDB to transparently access device memory. The external RSP Bridge (port 3333) allows IDEs to connect directly.

## FPB Unit

### What is FPB?

The Flash Patch and Breakpoint unit is a Cortex-M debug component designed for:
1. Setting hardware breakpoints
2. Patching Flash bugs without reprogramming

FPBInject repurposes FPB's REMAP feature for code injection.

### FPB Versions

| Version | Architecture | REMAP | Breakpoint |
|---------|--------------|-------|------------|
| FPBv1 | Cortex-M3/M4 (ARMv7-M) | ✅ | ✅ |
| FPBv2 | Cortex-M23/M33/M55 (ARMv8-M) | ❌ | ✅ |

> **Note**: ARMv8-M removed REMAP, requiring DebugMonitor mode.

### FPB Resources (FPBv1, e.g. STM32F103)

| Resource | Count | Range |
|----------|-------|-------|
| Code Comparators | 6 | 0x00000000 - 0x1FFFFFFF |
| Literal Comparators | 2 | 0x00000000 - 0x1FFFFFFF |
| REMAP Table | 6 entries | SRAM (32-byte aligned) |

> FPBv2 (ARMv8-M) increases code comparators to 8 but removes REMAP support.

### FPB Registers

| Register | Address | Description |
|----------|---------|-------------|
| FP_CTRL | 0xE0002000 | Control register |
| FP_REMAP | 0xE0002004 | Remap table base |
| FP_COMP0-7 | 0xE0002008-24 | Code/Literal comparators |

## Patch Modes

### 1. Trampoline Mode (Default)

Best for: Cortex-M3/M4

```mermaid
flowchart TB
    subgraph Flash
        TF["target_func<br/>@ 0x08001234"]
        TR["trampoline_n<br/>LDR PC, [Rx]"]
    end
    
    subgraph SRAM
        TA["target_addr<br/>= 0x20001000"]
        IF["patched_func()<br/>@ 0x20001000"]
    end
    
    TF -->|"FPB REMAP"| TR
    TR -->|"load target"| TA
    TA -->|"jump"| IF
```

**How it works:**
1. FPB redirects original function to pre-placed trampoline in Flash
2. Trampoline reads target address from RAM table
3. Trampoline jumps to injection code in RAM

### 2. DebugMonitor Mode

Best for: ARMv8-M or when trampolines unavailable

```mermaid
flowchart LR
    A["Function<br/>Call"] --> B["DebugMonitor<br/>Exception"]
    B --> C["Stack PC<br/>Modified"]
    C --> D["patched_func()"]
```

**How it works:**
1. FPB generates breakpoint (not REMAP)
2. DebugMonitor exception triggers
3. Handler modifies stacked PC to redirect execution
4. Exception return continues at inject function

**Exception Stack Frame:**

| Offset | Register | Description |
|--------|----------|-------------|
| SP+0 | R0 | preserved |
| SP+4 | R1 | preserved |
| SP+8 | R2 | preserved |
| SP+12 | R3 | preserved |
| SP+16 | R12 | preserved |
| SP+20 | LR | preserved |
| SP+24 | PC | ← MODIFIED to patched_func |
| SP+28 | xPSR | preserved |

### 3. Direct Mode

For special cases with direct RAM REMAP support.

## Memory Allocation

FPBInject supports two allocation modes, selected at build time via `FL_ALLOC_MODE`.

### Static Mode (Default, `FL_ALLOC_STATIC`)

Uses a fixed buffer managed by `fl_alloc_t` — a bitmap-based fixed-block allocator. The buffer is placed in a dedicated RAM section:

```c
static uint8_t s_code_buf[1024] __attribute__((aligned(4), section(".ram_code")));
static fl_alloc_t s_alloc;

fl_alloc_init(&s_alloc, s_code_buf, sizeof(s_code_buf));
```

Buffer layout:

```
[ bitmap (ceil(n/8) bytes) ][ size_table (n bytes) ][ block0 ][ block1 ] ... [ blockN-1 ]
```

Each block is `FL_ALLOC_BLOCK_SIZE` bytes (default 64). Allocations are contiguous runs of blocks tracked via bitmap. Supports `fl_malloc` / `fl_free` with O(n) first-fit search.

### Dynamic Mode (`FL_ALLOC_LIBC`)

Delegates directly to the platform's `malloc` / `free`:

```c
ctx.malloc_cb = malloc;
ctx.free_cb = free;
```

No additional alignment handling — the platform allocator is expected to return suitably aligned memory.

## Compilation Process

### 1. Extract Compiler Flags

Parse `compile_commands.json` to get:
- Include paths (`-I`)
- Defines (`-D`)
- CPU/arch flags (`-mcpu`, `-mthumb`, etc.)

If a `.d` dependency file is available, the raw compiler command is used directly (passthrough mode) for maximum accuracy.

### 2. Compile Injection Code

```bash
arm-none-eabi-gcc <cflags> -c \
    -ffunction-sections -fdata-sections \
    -Wno-error \
    -o inject.o patch.c
```

For C++ sources, `gcc` is automatically replaced with `g++`.

### 3. Link at Target Address

```bash
arm-none-eabi-gcc <cflags> -nostartfiles -nostdlib \
    -T inject.ld \
    -Wl,--gc-sections \
    -Wl,--allow-multiple-definition \
    -Wl,-u,<inject_func> \
    -o inject.elf inject.o \
    -Wl,--just-symbols=firmware.elf
```

The linker script places `.text` at the target RAM address. `--just-symbols` provides firmware symbol addresses without pulling in firmware code. `inject.o` must come before `--just-symbols` so the patch definition wins over the firmware's symbol.

### 4. Extract Binary

```bash
arm-none-eabi-objcopy -O binary inject.elf inject.bin
```

BSS is included in the binary (zeroed) via a sentinel `.fpb_end` section, ensuring static/global variables are properly initialized after upload.

> **Two-pass compilation**: First compile at placeholder address `0x20000000` to determine code size, then `alloc` on device, then recompile at the actual RAM address.

## Protocol

### Serial Commands

| Command | Key Arguments | Description |
|---------|---------------|-------------|
| `ping` | — | Connection test, responds `PONG` |
| `info` | — | Query FPB status, slot states, version |
| `alloc` | `--size N` | Allocate RAM buffer, returns address |
| `upload` | `--addr OFFSET --data BASE64 [--crc CRC]` | Write binary chunk to last allocation |
| `read` | `--addr ADDR --len N [--crc CRC] [--force]` | Read device memory, returns Base64 |
| `write` | `--addr ADDR --data BASE64 [--crc CRC] [--force]` | Write to arbitrary address |
| `patch` | `--comp N --orig ADDR --target ADDR [--crc CRC]` | Set FPB patch directly (no trampoline) |
| `tpatch` | `--comp N --orig ADDR --target ADDR [--crc CRC]` | Set patch via Flash trampoline (Cortex-M3/M4) |
| `dpatch` | `--comp N --orig ADDR --target ADDR [--crc CRC]` | Set patch via DebugMonitor (ARMv8-M) |
| `unpatch` | `--comp N` / `--all` | Clear one or all patches, frees memory |
| `enable` | `--comp N --enable 0\|1` / `--all` | Enable or disable patch slot(s) |
| `echo` | `--data HEX` | Throughput test: echoes length and CRC |
| `echoback` | `--len N` | Throughput test: sends N bytes back as Base64 |
| `hello` | — | Call `fl_hello()` to verify injection |
| `fopen` | `--path PATH [--mode r\|w\|a]` | Open file on device filesystem |
| `fwrite` | `--data BASE64 [--crc CRC]` | Write to open file |
| `fread` | `--len N` | Read from open file, returns Base64 |
| `fclose` | — | Close open file |
| `fcrc` | `--len N` | CRC-16 of open file |
| `fseek` | `--addr OFFSET` | Seek open file |
| `fstat` | `--path PATH` | File metadata |
| `flist` | `--path PATH` | List directory |
| `fremove` | `--path PATH` | Delete file |
| `fmkdir` | `--path PATH` | Create directory |
| `frename` | `--path SRC --newpath DST` | Rename file |

### Response Format

```
[FLOK] <message>          # Success (single line)
[FLERR] <message>         # Failure

[FLOK] ... data=BASE64    # Success with binary payload
[FLEND]                   # End of multi-line response
```

CRC-16 covers `addr(4B) + len(4B) + payload` for upload/read/write commands, and `comp(4B) + orig(4B) + target(4B)` for patch commands.

## API Reference

### FPB Functions

```c
fpb_result_t fpb_init(void);
void         fpb_deinit(void);
fpb_result_t fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr);
fpb_result_t fpb_clear_patch(uint8_t comp_id);
fpb_result_t fpb_enable_patch(uint8_t comp_id, bool enable);
const fpb_state_t* fpb_get_state(void);
fpb_result_t fpb_get_info(fpb_info_t* info);
```

### Trampoline Functions

```c
void     fpb_trampoline_set_target(uint32_t comp, uint32_t target);
void     fpb_trampoline_clear_target(uint32_t comp);
uint32_t fpb_trampoline_get_address(uint32_t comp);
```

### DebugMonitor Functions

```c
int      fpb_debugmon_init(void);
void     fpb_debugmon_deinit(void);
int      fpb_debugmon_set_redirect(uint8_t comp_id, uint32_t original_addr, uint32_t redirect_addr);
int      fpb_debugmon_clear_redirect(uint8_t comp_id);
uint32_t fpb_debugmon_get_redirect(uint32_t original_addr);
bool     fpb_debugmon_is_active(void);
void     fpb_debugmon_handler(uint32_t* stack_frame);
```

## Limitations

1. **Address Range**: Code region only (0x00000000 - 0x1FFFFFFF)
2. **Hook Count**: 6-8 simultaneous patches (FPB v1: 6, FPB v2: 8)
3. **Instruction Set**: Thumb/Thumb-2 only
4. **Debugger Conflict**: Debuggers may use FPB for breakpoints

## NuttX Integration

On NuttX, DebugMonitor uses native `up_debugpoint_add()` API:

```c
up_debugpoint_add(DEBUGPOINT_BREAKPOINT, addr, size, callback, &info);
```

Replace vendor's PANIC handler with NuttX's handler:

```c
irq_attach(NVIC_IRQ_DBGMONITOR, arm_dbgmonitor, NULL);
```

## References

- [ARM Cortex-M3 TRM](https://developer.arm.com/documentation/ddi0337)
- [ARM Debug Interface Spec](https://developer.arm.com/documentation/ihi0031)
- [STM32F103 Reference Manual](https://www.st.com/resource/en/reference_manual/rm0008.pdf)
