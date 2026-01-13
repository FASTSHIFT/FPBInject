# FPBInject - Cortex-M Runtime Code Injection Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-STM32F103-blue.svg)](https://www.st.com/en/microcontrollers-microprocessors/stm32f103.html)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/FASTSHIFT/FPBInject)

Runtime code injection tool for ARM Cortex-M3/M4 using the Flash Patch and Breakpoint (FPB) unit.

## Overview

FPBInject enables runtime function hooking and code injection on Cortex-M microcontrollers without modifying Flash memory. It leverages the FPB hardware unit to redirect function calls to custom code loaded in RAM.

### Key Features

- ✅ **Zero Flash Modification** - Inject code at runtime without erasing/writing Flash
- ✅ **Hardware-Level Redirection** - Uses Cortex-M FPB unit for zero-overhead patching
- ✅ **Multiple Hooks** - Supports up to 6 simultaneous code patches (STM32F103)
- ✅ **Transparent Hijacking** - Completely transparent to calling code
- ✅ **Reversible** - Easily disable patches to restore original behavior
- ✅ **Trampoline Architecture** - Pre-placed Flash trampolines jump to RAM code

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FPBInject Injection Flow                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. Original Call           2. FPB Intercept         3. Trampoline     │
│   ┌──────────────┐          ┌──────────────┐         ┌──────────────┐   │
│   │ caller()     │          │   FPB Unit   │         │ trampoline_0 │   │
│   │ calls        │────────> │ addr match   │───────> │ in Flash     │   │
│   │ digitalWrite │          │ 0x08008308   │         │ loads target │   │
│   └──────────────┘          └──────────────┘         └──────────────┘   │
│                                                             │           │
│   4. RAM Code Execution                                     ▼           │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  inject_digitalWrite() @ 0x20000278 (RAM)                        │  │
│   │  - Custom hook logic executes                                    │  │
│   │  - Can call original function or replace entirely                │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Architecture

The injection uses a two-stage approach:

1. **FPB REMAP**: Redirects original function address to a trampoline function in Flash
2. **Trampoline**: Pre-placed code in Flash that reads target address from RAM and jumps to it

This design allows dynamic target changes without runtime Flash modification.

## Hardware Requirements

- **MCU**: STM32F103C8T6 (Blue Pill) or other Cortex-M3/M4 device
- **Debugger**: ST-Link V2 (for flashing)
- **Serial**: USB-to-Serial adapter or USB CDC
- **LED**: PC13 (onboard Blue Pill LED)

## Software Requirements

- ARM GNU Toolchain (`arm-none-eabi-gcc`)
- CMake (>= 3.16)
- Python 3.x with `pyserial`
- ST-Link Tools or OpenOCD

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/FASTSHIFT/FPBInject.git
cd FPBInject
```

### 2. Build

```bash
# Configure
cmake -B build -DAPP_SELECT=3 -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake

# Build
cmake --build build
```

### 3. Flash

```bash
st-flash write build/FPBInject.bin 0x08000000
```

### 4. Inject Code

```bash
# Inject custom code to hook digitalWrite function
python3 Tools/fpb_loader.py -p /dev/ttyACM0 \
    --inject App/inject/inject.cpp \
    --target digitalWrite
```

## Usage

### Command Line Options

```bash
fpb_loader.py [options]

Options:
  -p, --port PORT      Serial port (e.g., /dev/ttyACM0)
  -b, --baudrate BAUD  Baud rate (default: 115200)
  --inject FILE        Source file to inject (.c or .cpp)
  --target FUNC        Target function to hook
  --func NAME          Inject function name (default: first inject_*)
  --comp N             FPB comparator index 0-5 (default: 0)
  -i, --interactive    Interactive mode
  --ping               Test connection
  --info               Show device info
```

### Examples

```bash
# Hook digitalWrite with custom logging
python3 Tools/fpb_loader.py -p /dev/ttyACM0 \
    --inject App/inject/inject.cpp \
    --target digitalWrite

# Hook blink_led with no-args injector
python3 Tools/fpb_loader.py -p /dev/ttyACM0 \
    --inject App/inject/inject.cpp \
    --target 'blink_led()' \
    --func inject_no_args

# Use different comparator for multiple hooks
python3 Tools/fpb_loader.py -p /dev/ttyACM0 \
    --inject App/inject/inject.cpp \
    --target pinMode \
    --comp 1
```

### Writing Injection Code

Create a source file with an `inject_*` function:

```cpp
// App/inject/inject.cpp
#include <Arduino.h>

// Hook function - replaces digitalWrite
__attribute__((used, section(".text.inject")))
void inject_digitalWrite(uint8_t pin, uint8_t value) {
    Serial.printf("Hooked: pin=%d val=%d\n", pin, value);
    // Call original or custom implementation
    value ? digitalWrite_HIGH(pin) : digitalWrite_LOW(pin);
}

// Simple hook without arguments
__attribute__((used, section(".text.inject")))
void inject_no_args(void) {
    Serial.printf("Function called at %dms\n", (int)millis());
}
```

## Configuration

### CMake Options

| Option | Default | Description |
|--------|---------|-------------|
| `APP_SELECT` | 1 | Application (1=blink, 2=test, 3=func_loader) |
| `FL_ALLOC_MODE` | STATIC | Memory allocation mode (STATIC/LIBC/UMM) |
| `FPB_NO_TRAMPOLINE` | OFF | Disable trampoline (for cores that can REMAP to RAM) |
| `FPB_TRAMPOLINE_NO_ASM` | OFF | Use C instead of assembly (no argument preservation) |
| `HSE_VALUE` | 8000000 | External oscillator frequency |
| `STM32_DEVICE` | STM32F10X_MD | Target device variant |

### Memory Allocation Modes

| Mode | CMake Value | Description |
|------|-------------|-------------|
| **Static** | `STATIC` | Fixed-size static buffer (4KB, default) |
| **LIBC** | `LIBC` | Standard libc malloc/free (dynamic) |
| **UMM** | `UMM` | umm_malloc embedded allocator (8KB heap) |

Example:

```bash
# Static allocation (default, 4KB fixed buffer)
cmake -B build -DAPP_SELECT=3 -DFL_ALLOC_MODE=STATIC \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake

# LIBC malloc/free (dynamic allocation)
cmake -B build -DAPP_SELECT=3 -DFL_ALLOC_MODE=LIBC \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake

# UMM_MALLOC (embedded allocator with 8KB heap)
cmake -B build -DAPP_SELECT=3 -DFL_ALLOC_MODE=UMM \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake
```

#### Dynamic Allocation Address Alignment

> ⚠️ **Important Technical Note**
>
> When using dynamic allocation modes (LIBC or UMM), the injection code must be placed at an **8-byte aligned address**. ARM Cortex-M functions require proper alignment for correct execution.
>
> **The Problem:**
> - `malloc()` may return addresses that are only 4-byte aligned (e.g., `0x20001544`)
> - GCC aligns functions to 8-byte boundaries, causing a 4-byte offset in the compiled binary
> - If code is uploaded without accounting for this offset, all address references (strings, function calls) will be incorrect
>
> **The Solution (handled automatically by `fpb_loader.py`):**
> 1. Allocate extra space: `size + 8` bytes
> 2. Calculate aligned address: `aligned = (raw + 7) & ~7`
> 3. Upload code starting at the alignment offset
>
> ```
> Example:
>   malloc returns:  0x20001544 (4-byte aligned)
>   aligned address: 0x20001548 (8-byte aligned)
>   offset:          4 bytes
>   
>   Upload: data written to offset 4 in buffer
>   Result: code starts at 0x20001548, addresses match
> ```
>
> This is why static allocation (`FL_ALLOC_MODE=STATIC`) uses a buffer with `__attribute__((aligned(4), section(".ram_code")))` - ensuring proper alignment from the start.

### Trampoline Modes

| Mode | CMake Option | Description |
|------|--------------|-------------|
| **ASM (default)** | - | Uses inline assembly to preserve R0-R3 registers |
| **No ASM** | `-DFPB_TRAMPOLINE_NO_ASM=ON` | Simple C function call, no argument preservation |
| **Disabled** | `-DFPB_NO_TRAMPOLINE=ON` | No trampoline, for cores that support direct RAM REMAP |

Example:

```bash
# Build with C-based trampoline (no assembly)
cmake -B build -DAPP_SELECT=3 -DFPB_TRAMPOLINE_NO_ASM=ON \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake

# Build without trampoline (for Cortex-M4/M7 with RAM REMAP support)
cmake -B build -DAPP_SELECT=3 -DFPB_NO_TRAMPOLINE=ON \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake
```

### Patch Modes

FPBInject supports three different patch modes for function redirection:

| Mode | Option | Best For | Description |
|------|--------|----------|-------------|
| **Trampoline** | `--patch-mode trampoline` | Cortex-M3/M4 | FPB REMAP to Flash trampoline → RAM (default) |
| **DebugMonitor** | `--patch-mode debugmon` | ARMv8-M | FPB breakpoint → DebugMonitor exception → PC redirect |
| **Direct** | `--patch-mode direct` | Special cases | Direct FPB REMAP (limited use) |

Example:

```bash
# Default trampoline mode (Cortex-M3/M4)
python3 Tools/fpb_loader.py -p /dev/ttyACM0 \
    --inject App/inject/inject.cpp \
    --target digitalWrite

# DebugMonitor mode (for ARMv8-M or as alternative)
python3 Tools/fpb_loader.py -p /dev/ttyACM0 \
    --inject App/inject/inject.cpp \
    --target digitalWrite \
    --patch-mode debugmon
```

## DebugMonitor Mode

### Why DebugMonitor Mode?

**ARMv8-M Architecture Limitation**: Starting with ARMv8-M (Cortex-M23/M33/M55), ARM removed the FPB REMAP functionality. The FPB unit can only generate breakpoints, not redirect code execution. This means the traditional trampoline approach doesn't work on newer cores.

DebugMonitor mode provides a software-based alternative that works on both legacy (Cortex-M3/M4) and modern (ARMv8-M) architectures.

### How DebugMonitor Mode Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DebugMonitor Redirection Flow                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. Function Call           2. FPB Breakpoint       3. DebugMonitor    │
│   ┌──────────────┐          ┌──────────────┐         ┌──────────────┐   │
│   │ caller()     │          │   FPB Unit   │         │DebugMon_     │   │
│   │ calls        │────────> │ BKPT trigger │───────> │Handler()     │   │
│   │ digitalWrite │          │ @ 0x08008308 │         │ (exception)  │   │
│   └──────────────┘          └──────────────┘         └──────────────┘   │
│                                                             │           │
│   4. Stack Frame Modification                               ▼           │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  Exception Stack Frame:                                          │  │
│   │  [SP+0]  R0      - preserved                                     │  │
│   │  [SP+4]  R1      - preserved                                     │  │
│   │  [SP+8]  R2      - preserved                                     │  │
│   │  [SP+12] R3      - preserved                                     │  │
│   │  [SP+16] R12     - preserved                                     │  │
│   │  [SP+20] LR      - preserved                                     │  │
│   │  [SP+24] PC  ◄── MODIFIED to inject_digitalWrite (0x20000278)    │  │
│   │  [SP+28] xPSR    - preserved                                     │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│   5. Exception Return → Execution continues at inject_digitalWrite()   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Technical Implementation

1. **FPB Configuration**: Comparator is set with REPLACE=0b11 (breakpoint on both halfwords)
2. **DebugMonitor Enable**: DEMCR.MON_EN is set to enable DebugMonitor exception
3. **VTOR Relocation**: Vector table is copied to RAM to install custom DebugMon_Handler
4. **PC Modification**: When breakpoint triggers, handler modifies stacked PC to redirect execution

### Key Registers

| Register | Address | Purpose |
|----------|---------|---------|
| DEMCR | 0xE000EDFC | Debug Exception and Monitor Control |
| DFSR | 0xE000ED30 | Debug Fault Status Register |
| SCB_VTOR | 0xE000ED08 | Vector Table Offset Register |

### DEMCR Configuration

```
DEMCR bits used:
  [24] TRCENA  - Trace enable (required for debug features)
  [16] MON_EN  - DebugMonitor exception enable
```

### FPB Comparator Configuration (Breakpoint Mode)

```
FP_COMPn bits:
  [31:30] REPLACE = 0b11  - Breakpoint on both halfwords
  [28:2]  COMP           - Address to match (bits [28:2])
  [0]     ENABLE = 1     - Comparator enable
```

### Advantages of DebugMonitor Mode

| Advantage | Description |
|-----------|-------------|
| ✅ **ARMv8-M Compatible** | Works on Cortex-M23/M33/M55 where REMAP is removed |
| ✅ **No Flash Trampolines** | Doesn't require pre-placed code in Flash |
| ✅ **Full Register Preservation** | All registers preserved via exception frame |
| ✅ **Dynamic Configuration** | Can add/remove hooks at runtime |

### Limitations and Considerations

| Limitation | Description |
|------------|-------------|
| ⚠️ **Higher Latency** | Exception entry/exit adds ~12-24 cycles overhead |
| ⚠️ **Debugger Conflict** | External debugger may interfere with DebugMonitor |
| ⚠️ **Priority Constraints** | DebugMonitor has fixed high priority (-1) |
| ⚠️ **Vector Table RAM** | Requires ~256 bytes RAM for relocated vector table |

### Build Configuration

```bash
# Enable DebugMonitor support (default: enabled)
cmake -B build -DAPP_SELECT=3 \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake

# Disable DebugMonitor (reduces code size if not needed)
cmake -B build -DAPP_SELECT=3 -DFPB_NO_DEBUGMON=ON \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake
```

### When to Use DebugMonitor Mode

| Use Case | Recommended Mode |
|----------|-----------------|
| Cortex-M3/M4 with Flash trampolines available | **Trampoline** (lower overhead) |
| ARMv8-M (Cortex-M23/M33/M55) | **DebugMonitor** (only option) |
| No Flash trampolines pre-placed | **DebugMonitor** |
| Lowest latency required | **Trampoline** |
| Maximum compatibility needed | **DebugMonitor** |

## FPB Technical Details

### Flash Patch and Breakpoint Unit

The FPB is a Cortex-M debug component originally designed for:
1. Setting hardware breakpoints
2. Patching Flash bugs without reprogramming

### FPB Versions

| Version | Architecture | REMAP Support | Breakpoint Support |
|---------|--------------|---------------|-------------------|
| **FPBv1** | Cortex-M3/M4 (ARMv7-M) | ✅ Yes | ✅ Yes |
| **FPBv2** | Cortex-M23/M33/M55 (ARMv8-M) | ❌ Removed | ✅ Yes |

> ⚠️ **Important**: ARMv8-M removed the REMAP functionality from FPB. On these cores, FPB can only generate breakpoints, requiring the DebugMonitor approach for function redirection.

### STM32F103 FPB Resources (FPBv1)

| Resource | Count | Address Range |
|----------|-------|---------------|
| Code Comparators | 6 | 0x00000000 - 0x1FFFFFFF |
| Literal Comparators | 2 | 0x00000000 - 0x1FFFFFFF |
| REMAP Table | 8 entries | SRAM (configurable) |

### Registers

| Register | Address | Description |
|----------|---------|-------------|
| FP_CTRL | 0xE0002000 | Control register |
| FP_REMAP | 0xE0002004 | Remap table base address |
| FP_COMP0-5 | 0xE0002008-1C | Code comparators |
| FP_COMP6-7 | 0xE0002020-24 | Literal comparators |

## Project Structure

```
FPBInject/
├── CMakeLists.txt              # Build configuration
├── README.md                   # This file
├── LICENSE                     # MIT License
├── cmake/
│   └── arm-none-eabi-gcc.cmake # Toolchain file
├── App/
│   ├── func_loader/            # Function loader application
│   ├── inject/                 # Example injection code
│   └── ...                     # Other app modules
├── Project/
│   ├── Application/            # Main application (entry)
│   ├── ArduinoAPI/             # Arduino compatibility layer
│   └── Platform/
│       └── STM32F10x/          # Platform HAL (drivers, startup, config)
├── Source/
│   ├── fpb_inject.c/h          # FPB driver
│   ├── fpb_trampoline.c/h      # Trampoline functions
│   └── func_loader.c/h         # Command processor
└── Tools/
    ├── fpb_loader.py           # Host injection tool
    └── setup_env.py            # Environment setup
```

## Limitations

1. **Address Range**: FPB can only patch Code region (0x00000000 - 0x1FFFFFFF)
2. **Comparator Count**: Limited to 6 simultaneous hooks (STM32F103)
3. **Instruction Set**: Thumb/Thumb-2 only (not ARM mode)
4. **Debugger Conflict**: Some debuggers use FPB for breakpoints

## Use Cases

- **Hot Patching**: Fix bugs on deployed devices
- **Feature Toggle**: Enable/disable features at runtime  
- **A/B Testing**: Switch between implementations
- **Security Research**: Dynamic analysis and hooking
- **Debugging**: Temporarily modify program behavior
- **Instrumentation**: Add logging/tracing without recompilation

## API Reference

### FPB Functions

```c
void fpb_init(void);                              // Initialize FPB unit
void fpb_set_patch(uint8_t comp, uint32_t orig, uint32_t target);
void fpb_clear_patch(uint8_t comp);               // Clear patch
fpb_state_t fpb_get_state(void);                  // Get FPB state
```

### Trampoline Functions

```c
void fbp_trampoline_set_target(uint32_t comp, uint32_t target);
void fbp_trampoline_clear_target(uint32_t comp);
uint32_t fbp_trampoline_get_address(uint32_t comp);
```

## License

MIT License - See [LICENSE](LICENSE) file.

## References

- [ARM Cortex-M3 Technical Reference Manual](https://developer.arm.com/documentation/ddi0337)
- [ARM Debug Interface Architecture Specification](https://developer.arm.com/documentation/ihi0031)
- [STM32F103 Reference Manual (RM0008)](https://www.st.com/resource/en/reference_manual/rm0008.pdf)
- [HERA-FPB](https://github.com/akrishnaams/HERA-FPB)
