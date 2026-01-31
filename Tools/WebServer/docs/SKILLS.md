# FPBInject CLI Skills

> A lightweight command-line tool for ARM binary patching. Designed for AI agent integration.

## Overview

`fpb_cli.py` is a pure CLI tool that enables AI assistants to analyze, modify, and patch ARM ELF binaries. All commands output JSON for easy parsing.

## Global Options

```bash
fpb_cli.py [OPTIONS] <command> [args...]

Options:
  -v, --verbose              Enable verbose output
  --port, -p <device>        Serial port (e.g., /dev/ttyACM0, COM3)
  --baudrate, -b <rate>      Serial baudrate (default: 115200)
  --elf <path>               Path to ELF file
  --compile-commands <path>  Path to compile_commands.json
```

## Commands

### Offline Commands (No Device Required)

### 1. `analyze` - Analyze a function
```bash
fpb_cli.py analyze <elf_path> <func_name>
```

**Example:**
```bash
$ fpb_cli.py analyze firmware.elf digitalWrite
{
  "success": true,
  "analysis": {
    "func_name": "digitalWrite",
    "addr": "0x08001234",
    "signature": "void digitalWrite(uint8_t pin, uint8_t val)",
    "asm_lines": 12
  }
}
```

### 2. `disasm` - Get disassembly
```bash
fpb_cli.py disasm <elf_path> <func_name>
```

**Example:**
```bash
$ fpb_cli.py disasm firmware.elf digitalWrite
{
  "success": true,
  "func_name": "digitalWrite",
  "disasm": "push {r7, lr}\nmov r7, sp\n...",
  "language": "arm_asm"
}
```

### 3. `decompile` - Decompile to pseudo-C
```bash
fpb_cli.py decompile <elf_path> <func_name>
```

**Note:** Requires `angr` library (`pip install angr`)

### 4. `signature` - Get function signature
```bash
fpb_cli.py signature <elf_path> <func_name>
```

### 5. `search` - Search for functions
```bash
fpb_cli.py search <elf_path> <pattern>
```

**Example:**
```bash
$ fpb_cli.py search firmware.elf "gpio"
{
  "success": true,
  "pattern": "gpio",
  "count": 5,
  "symbols": [
    {"name": "gpio_init", "addr": "0x08001000"},
    {"name": "gpio_write", "addr": "0x08001020"},
    ...
  ]
}
```

### 6. `compile` - Compile patch source (offline validation)
```bash
fpb_cli.py compile <source_file> --elf <elf> --compile-commands <path> [--addr <base_addr>]
```

**Example:**
```bash
$ fpb_cli.py compile patch.c --elf firmware.elf --compile-commands build/compile_commands.json
{
  "success": true,
  "binary_size": 55,
  "base_addr": "0x20001000",
  "symbols": {"inject_digitalWrite": "0x20001000", "__printf_veneer": "0x20001010"}
}
```

### Online Commands (Device Required)

### 7. `info` - Get device FPB info
```bash
fpb_cli.py --port /dev/ttyACM0 info
```

**Example:**
```bash
$ fpb_cli.py --port /dev/ttyACM0 info
{
  "success": true,
  "info": {
    "slots": [...],
    "is_dynamic": false,
    "base": 536871504,
    "size": 1024,
    "used": 0,
    "active_slots": 0,
    "total_slots": 6
  }
}
```

### 8. `inject` - Inject patch to device
```bash
fpb_cli.py --port <device> --elf <elf> --compile-commands <path> inject <target_func> <source_file> [options]

Options:
  --mode <mode>   Patch mode: trampoline|debugmon|direct (default: trampoline)
  --comp <num>    FPB slot number (-1 for auto, default: -1)
  --verify        Verify patch after injection
```

**Example:**
```bash
$ fpb_cli.py --port /dev/ttyACM0 --elf firmware.elf --compile-commands build/compile_commands.json \
    inject digitalWrite patch_digitalWrite.c
{
  "success": true,
  "result": {
    "compile_time": 0.03,
    "upload_time": 0.02,
    "total_time": 0.13,
    "code_size": 55,
    "inject_func": "inject_digitalWrite",
    "target_addr": "0x08008608",
    "inject_addr": "0x20000250",
    "slot": 0,
    "patch_mode": "trampoline"
  }
}
```

### 9. `unpatch` - Remove patch from device
```bash
fpb_cli.py --port <device> unpatch [--comp <num>] [--all]
```

**Example:**
```bash
# Remove patch from slot 0
$ fpb_cli.py --port /dev/ttyACM0 unpatch --comp 0

# Remove all patches
$ fpb_cli.py --port /dev/ttyACM0 unpatch --all
```

## Typical Workflow

### Step 1: Explore the binary (offline)
```bash
# Search for target functions
fpb_cli.py search firmware.elf "write"

# Analyze the target function
fpb_cli.py analyze firmware.elf digitalWrite

# Get disassembly
fpb_cli.py disasm firmware.elf digitalWrite
```

### Step 2: Create patch
Create a C file (e.g., `patch_digitalWrite.c`):
```c
#include <stdint.h>
#include <stdio.h>

// Patched function - must be named inject_<target_func>
void inject_digitalWrite(uint8_t pin, uint8_t val) {
    // Add your custom logic here
    printf("digitalWrite: pin=%d, val=%d\r\n", (int)pin, (int)val);
    
    // Note: Call to original function not shown here
    // Use trampoline mode to auto-redirect to original after your code
}
```

### Step 3: Test compile (offline)
```bash
fpb_cli.py compile patch_digitalWrite.c \
    --elf firmware.elf \
    --compile-commands build/compile_commands.json
```

### Step 4: Inject to device (online)
```bash
fpb_cli.py --port /dev/ttyACM0 \
    --elf firmware.elf \
    --compile-commands build/compile_commands.json \
    inject digitalWrite patch_digitalWrite.c
```

### Step 5: Verify or rollback
```bash
# Check device status
fpb_cli.py --port /dev/ttyACM0 info

# If something goes wrong, remove the patch
fpb_cli.py --port /dev/ttyACM0 unpatch --comp 0
```

## Output Format

### Success Response
```json
{
  "success": true,
  "data": { ... }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message"
}
```

## Tips for AI Agents

1. **Always check `success` field** before processing results
2. **Use `jq` for parsing** complex JSON outputs:
   ```bash
   fpb_cli.py search firmware.elf gpio | jq '.symbols[].name'
   ```
3. **Verbose mode** for debugging:
   ```bash
   fpb_cli.py -v --port /dev/ttyACM0 inject digitalWrite patch.c
   ```
4. **FPB Slots** range from 0-5 (6 slots total)
5. **inject_<funcName>** - patch functions MUST use this naming convention
6. **\r\n line endings** - use for proper serial output display

## Common Patch Patterns

### Print parameters (replaces original)
```c
void inject_myFunc(int a, int b) {
    printf("myFunc: a=%d, b=%d\r\n", a, b);
    // Original function is NOT called in this simple example
}
```

### Log and continue (with trampoline)
```c
// In trampoline mode, after your inject function returns,
// the original function is automatically called
void inject_myFunc(int a, int b) {
    printf("myFunc called\r\n");
    // Trampoline will redirect to original automatically
}
```

### Skip original function
```c
void inject_myFunc(void) {
    // Return without calling original - effectively disables the function
    return;
}
```

## Requirements

- Python 3.8+
- ARM GCC toolchain (arm-none-eabi-gcc)
- pyserial (`pip install pyserial`) for device communication
- Optional: `angr` for decompilation

## Version

1.0.0
