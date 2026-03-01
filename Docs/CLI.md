# FPBInject CLI Tool

A lightweight command-line interface for ARM binary patching designed for AI agent integration.

## Overview

`fpb_cli.py` is a pure CLI tool located at `Tools/WebServer/fpb_cli.py`. All commands output JSON for easy parsing by AI assistants or scripts.

## Requirements

- Python 3.8+
- ARM GCC toolchain (`arm-none-eabi-gcc`)
- pyserial (`pip install pyserial`) for device communication
- Optional: [Ghidra](https://ghidra-sre.org/) for decompilation

## Installation

```bash
cd Tools/WebServer
pip install pyserial
```

## Global Options

```bash
fpb_cli.py [OPTIONS] <command> [args...]

Options:
  -v, --verbose              Enable verbose output
  --port, -p <device>        Serial port (e.g., /dev/ttyACM0, COM3)
  --baudrate, -b <rate>      Serial baudrate (default: 115200)
  --elf <path>               Path to ELF file (global default)
  --compile-commands <path>  Path to compile_commands.json
```

## Commands

### Offline Commands (No Device Required)

#### 1. `analyze` - Analyze a function

```bash
fpb_cli.py analyze <elf_path> <func_name>
```

**Output:**
```json
{
  "success": true,
  "analysis": {
    "func_name": "digitalWrite",
    "addr": "0x08001234",
    "signature": "void digitalWrite(uint8_t, uint8_t)",
    "asm_lines": 12
  }
}
```

#### 2. `disasm` - Get disassembly

```bash
fpb_cli.py disasm <elf_path> <func_name>
```

**Output:**
```json
{
  "success": true,
  "func_name": "digitalWrite",
  "disasm": "push {r7, lr}\nmov r7, sp\n...",
  "language": "arm_asm"
}
```

#### 3. `decompile` - Decompile to pseudo-C

```bash
fpb_cli.py decompile <elf_path> <func_name>
```

> Requires Ghidra. Set `ghidra_path` in config or ensure `analyzeHeadless` is in PATH.

#### 4. `signature` - Get function signature

```bash
fpb_cli.py signature <elf_path> <func_name>
```

#### 5. `search` - Search for functions

```bash
fpb_cli.py search <elf_path> <pattern>
```

**Output:**
```json
{
  "success": true,
  "pattern": "gpio",
  "count": 5,
  "symbols": [
    {"name": "gpio_init", "addr": "0x08001000"},
    {"name": "gpio_write", "addr": "0x08001020"}
  ]
}
```

#### 6. `compile` - Compile patch source (offline validation)

```bash
fpb_cli.py compile <source_file> --elf <elf> --compile-commands <path> [--addr <base_addr>]
```

**Output:**
```json
{
  "success": true,
  "binary_size": 55,
  "base_addr": "0x20001000",
  "symbols": {"digitalWrite": "0x20001000"}
}
```

### Online Commands (Device Required)

#### 7. `info` - Get device FPB info

```bash
fpb_cli.py --port /dev/ttyACM0 info
```

**Output:**
```json
{
  "success": true,
  "info": {
    "slots": [...],
    "total_slots": 6,
    "active_slots": 0
  }
}
```

#### 8. `inject` - Inject patch to device

```bash
fpb_cli.py --port <device> --elf <elf> --compile-commands <path> \
    inject <target_func> <source_file> [options]

Options:
  --mode <mode>   Patch mode: trampoline|debugmon|direct (default: trampoline)
  --comp <num>    FPB slot number (-1 for auto, default: -1)
  --verify        Verify patch after injection
```

**Example:**
```bash
fpb_cli.py --port /dev/ttyACM0 --elf firmware.elf \
    --compile-commands build/compile_commands.json \
    inject digitalWrite patch_digitalWrite.c
```

**Output:**
```json
{
  "success": true,
  "result": {
    "compile_time": 0.03,
    "upload_time": 0.02,
    "total_time": 0.13,
    "code_size": 55,
    "inject_func": "digitalWrite",
    "target_addr": "0x08008608",
    "inject_addr": "0x20000250",
    "slot": 0,
    "patch_mode": "trampoline"
  }
}
```

#### 9. `unpatch` - Remove patch

```bash
fpb_cli.py --port /dev/ttyACM0 unpatch --comp <slot>
fpb_cli.py --port /dev/ttyACM0 unpatch --all
```

## Typical Workflow

```bash
# Step 1: Search for target functions (offline)
fpb_cli.py search firmware.elf "write"

# Step 2: Analyze the target function
fpb_cli.py analyze firmware.elf digitalWrite

# Step 3: Get disassembly for understanding
fpb_cli.py disasm firmware.elf digitalWrite

# Step 4: Compile and validate patch offline
fpb_cli.py compile patch.c --elf firmware.elf --compile-commands build/compile_commands.json

# Step 5: Inject to device
fpb_cli.py --port /dev/ttyACM0 --elf firmware.elf \
    --compile-commands build/compile_commands.json \
    inject digitalWrite patch.c

# Step 6: Verify or rollback
fpb_cli.py --port /dev/ttyACM0 info
fpb_cli.py --port /dev/ttyACM0 unpatch --comp 0
```

## Writing Patch Code

Create a source file with `/* FPB_INJECT */` marker:

```c
// patch_digitalWrite.c
#include <stdint.h>
#include <stdio.h>

/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void digitalWrite(uint8_t pin, uint8_t val) {
    printf("Patched: pin=%d val=%d\r\n", (int)pin, (int)val);
}
```

> **Note**: Calling the original function from injected code is NOT supported due to FPB hardware limitations.

### Common Patch Patterns

**Replace and log parameters:**
```c
/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void myFunc(int a, int b) {
    printf("myFunc: a=%d, b=%d\r\n", a, b);
    // Original function is NOT called - this code replaces it entirely
}
```

**Log and continue (trampoline mode):**
```c
// In trampoline mode, after your inject function returns,
// the original function is automatically called
/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void myFunc(int a, int b) {
    printf("myFunc called\r\n");
    // Trampoline will redirect to original automatically
}
```

**Skip original function:**
```c
/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void myFunc(void) {
    // Return without doing anything - effectively disables the function
    return;
}
```

## Output Format

All commands return JSON:

```json
// Success
{"success": true, "data": {...}}

// Error
{"success": false, "error": "Error message"}
```

## Tips for AI Agents

1. Always check the `success` field before processing results
2. Use `jq` for parsing complex JSON outputs:
   ```bash
   fpb_cli.py search firmware.elf gpio | jq '.symbols[].name'
   ```
3. Use `-v` verbose mode for debugging
4. FPB slots range from 0-5 (6 slots typical)
5. Patch functions MUST include the `/* FPB_INJECT */` comment marker
6. Use `\r\n` line endings for proper serial output display

## Related Documentation

- [Architecture](Architecture.md) - Technical implementation details
- [WebServer Guide](../Tools/WebServer/docs/WebServer.md) - Web-based injection interface
