# FPBInject - Cortex-M Runtime Code Injection

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-STM32F103-blue.svg)](https://www.st.com/en/microcontrollers-microprocessors/stm32f103.html)
[![Platform](https://img.shields.io/badge/Platform-NuttX-blue.svg)](https://github.com/apache/nuttx)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/FASTSHIFT/FPBInject)
[![CI](https://github.com/FASTSHIFT/FPBInject/actions/workflows/ci.yml/badge.svg)](https://github.com/FASTSHIFT/FPBInject/actions/workflows/ci.yml)

Runtime function hooking for ARM Cortex-M3/M4 using the FPB hardware unit. Inject custom code without modifying Flash.

## Features

- ✅ **Zero Flash Modification** - Runtime injection to RAM
- ✅ **Hardware Redirection** - FPB unit for zero-overhead patching
- ✅ **Dual Modes** - REMAP (M3/M4) and DebugMonitor (ARMv8-M)
- ✅ **6-8 Simultaneous Hooks** - FPB v1: 6 slots, FPB v2: 8 slots
- ✅ **Reversible** - Restore original behavior instantly

## Quick Start

### Build

```bash
git clone https://github.com/FASTSHIFT/FPBInject.git
cd FPBInject

cmake -B build -DAPP_SELECT=3 -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake
cmake --build build
```

### Flash

```bash
st-flash write build/FPBInject.bin 0x08000000
```

### Inject via CLI

```bash
cd Tools/WebServer
pip install pyserial

# Analyze target function
python fpb_cli.py analyze build/FPBInject.elf digitalWrite

# Inject patch
python fpb_cli.py --port /dev/ttyACM0 --elf build/FPBInject.elf \
    --compile-commands build/compile_commands.json \
    inject digitalWrite patch.c
```

## Tools

| Tool | Description |
|------|-------------|
| [fpb_cli.py](Docs/CLI.md) | CLI for AI integration (JSON output) |
| [WebServer](Docs/WebServer.md) | Web UI with file monitoring |

## Writing Patches

```cpp
// patch_digitalWrite.c
#include <Arduino.h>

/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
void digitalWrite(uint8_t pin, uint8_t value) {
    // Completely replaces the original digitalWrite function
    Serial.printf("Patched: pin=%d val=%d\n", pin, value);
    value ? GPIO_SetBits(GPIOA, 1 << pin) : GPIO_ResetBits(GPIOA, 1 << pin);
}
```

> **Note**: Calling the original function from injected code is NOT supported due to FPB hardware limitations.

## CMake Options

| Option | Default | Description |
|--------|---------|-------------|
| `APP_SELECT` | 1 | Application (3=func_loader) |
| `FL_ALLOC_MODE` | STATIC | Memory: STATIC/LIBC/UMM |
| `FPB_NO_DEBUGMON` | OFF | Disable DebugMonitor |

## Hardware

- **MCU**: STM32F103C8T6 or other Cortex-M3/M4
- **Debugger**: ST-Link V2
- **Serial**: USB-to-Serial or USB CDC

## Documentation

- [CLI Tool Guide](Docs/CLI.md)
- [WebServer Guide](Docs/WebServer.md)
- [Architecture Details](Docs/Architecture.md)
- [AI Skills](Tools/WebServer/docs/SKILLS.md)

## Project Structure

```
FPBInject/
├── App/                    # Applications and inject examples
├── Source/                 # FPB driver and function loader
├── Project/                # Platform HAL and Arduino API
├── Tools/
│   └── WebServer/          # CLI and Web tools
└── Docs/                   # Documentation
```

## Limitations

- FPB patches Code region only (0x00000000 - 0x1FFFFFFF)
- FPB v1: 6 comparators (STM32F103, etc.), FPB v2: up to 8 comparators
- Thumb/Thumb-2 instructions only
- Debuggers may conflict with FPB

## License

MIT License - See [LICENSE](LICENSE)

## References

- [ARM Cortex-M3 TRM](https://developer.arm.com/documentation/ddi0337)
- [STM32F103 Reference Manual](https://www.st.com/resource/en/reference_manual/rm0008.pdf)
