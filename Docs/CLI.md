# FPBInject CLI Tool

A lightweight command-line interface for ARM binary patching designed for AI agent integration.

## Overview

`fpb_cli.py` is a pure CLI tool located at `Tools/WebServer/fpb_cli.py`. All commands output JSON for easy parsing by AI assistants or scripts.

## Installation

```bash
cd Tools/WebServer
pip install pyserial  # Required for device communication
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

**Note:** Requires `angr` library (`pip install angr`)

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
  "symbols": {"inject_digitalWrite": "0x20001000"}
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
fpb_cli.py --port /dev/ttyACM0 --elf build/firmware.elf \
    --compile-commands build/compile_commands.json \
    inject digitalWrite patch_digitalWrite.c
```

**Output:**
```json
{
  "success": true,
  "result": {
    "slot": 0,
    "orig_addr": "0x08001234",
    "target_addr": "0x20001000",
    "code_size": 55
  }
}
```

#### 9. `unpatch` - Remove patch

```bash
fpb_cli.py --port /dev/ttyACM0 unpatch --comp <slot>
fpb_cli.py --port /dev/ttyACM0 unpatch --all
```

## AI Integration

### Example: Cursor/Copilot Integration

The CLI is designed for AI assistant integration. Example workflow:

```bash
# 1. Search for target function
fpb_cli.py search firmware.elf "write"

# 2. Analyze the function
fpb_cli.py analyze firmware.elf digitalWrite

# 3. Get disassembly for understanding
fpb_cli.py disasm firmware.elf digitalWrite

# 4. Compile and validate patch offline
fpb_cli.py compile patch.c --elf firmware.elf --compile-commands build/compile_commands.json

# 5. Inject to device
fpb_cli.py --port /dev/ttyACM0 --elf firmware.elf --compile-commands build/compile_commands.json \
    inject digitalWrite patch.c
```

### Skills File

See [SKILLS.md](../Tools/WebServer/SKILLS.md) for detailed AI integration documentation including prompts and workflows.

## Writing Patch Code

Create a source file with an `inject_*` function:

```cpp
// patch_digitalWrite.c
#include <Arduino.h>

__attribute__((used, section(".text.inject")))
void inject_digitalWrite(uint8_t pin, uint8_t value) {
    Serial.printf("Hooked: pin=%d val=%d\n", pin, value);
    // Call original or custom implementation
    value ? digitalWrite_HIGH(pin) : digitalWrite_LOW(pin);
}
```

## Error Handling

All errors return JSON with `"success": false`:

```json
{
  "success": false,
  "error": "Function 'nonexistent' not found"
}
```

## Related Documentation

- [WebServer Guide](WebServer.md) - Web-based injection interface
- [Architecture](Architecture.md) - Technical implementation details
