#!/bin/bash
# Build test ELF files for symbol pipeline testing.
# Run from any directory — paths are relative to this script.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for ARM toolchain
if ! command -v arm-none-eabi-gcc &>/dev/null; then
    echo "Warning: arm-none-eabi-gcc not found, skipping ELF build"
    exit 0
fi

# ── Build test_func.elf (legacy, simple) ──────────────────
echo "Building test_func.elf..."
arm-none-eabi-gcc -c -o test_func.o test_func.c \
    -mcpu=cortex-m4 -mthumb -Os -g \
    -ffunction-sections -fdata-sections

arm-none-eabi-gcc -o test_func.elf test_func.o \
    -nostartfiles \
    -Wl,-Ttext=0x08000000 \
    -Wl,--gc-sections \
    -mcpu=cortex-m4 -mthumb

rm -f test_func.o
echo "  Created test_func.elf"

# ── Build test_symbols.elf (comprehensive symbol types) ───
echo "Building test_symbols.elf..."
arm-none-eabi-gcc -c -o test_symbols.o test_symbols.c \
    -mcpu=cortex-m4 -mthumb -O1 -g -gdwarf-4 \
    -ffunction-sections -fdata-sections \
    -Wno-incompatible-pointer-types

arm-none-eabi-gcc -o test_symbols.elf test_symbols.o \
    -nostartfiles \
    -Wl,-Ttext=0x08000000 \
    -Wl,-Tdata=0x20000000 \
    -Wl,--no-gc-sections \
    -mcpu=cortex-m4 -mthumb

rm -f test_symbols.o
echo "  Created test_symbols.elf"

# ── Build test_symbols_cpp.elf (C++ symbol types) ────────
if [ -f test_symbols_cpp.cpp ]; then
    echo "Building test_symbols_cpp.elf..."

    if ! command -v arm-none-eabi-g++ &>/dev/null; then
        echo "Warning: arm-none-eabi-g++ not found, skipping C++ ELF build"
    else
        arm-none-eabi-g++ -c -o test_symbols_cpp.o test_symbols_cpp.cpp \
            -mcpu=cortex-m4 -mthumb -O1 -g -gdwarf-4 \
            -ffunction-sections -fdata-sections \
            -fno-exceptions -fno-rtti \
            -std=c++17

        arm-none-eabi-g++ -o test_symbols_cpp.elf test_symbols_cpp.o \
            -nostartfiles -nostdlib -lgcc \
            -Wl,-Ttext=0x08000000 \
            -Wl,-Tdata=0x20000000 \
            -Wl,--no-gc-sections \
            -mcpu=cortex-m4 -mthumb \
            -fno-exceptions -fno-rtti

        rm -f test_symbols_cpp.o
        echo "  Created test_symbols_cpp.elf"
    fi
fi

# ── Summary ───────────────────────────────────────────────
for elf in test_symbols.elf test_symbols_cpp.elf; do
    if [ -f "$elf" ]; then
        echo ""
        echo "=== $elf symbol summary ==="
        echo "Functions (T/t/W):"
        arm-none-eabi-nm "$elf" | grep -E "^[0-9a-f]+ [TtW] " | wc -l
        echo "Variables (D/d/B/b):"
        arm-none-eabi-nm "$elf" | grep -E "^[0-9a-f]+ [DdBb] " | wc -l
        echo "Constants (R/r):"
        arm-none-eabi-nm "$elf" | grep -E "^[0-9a-f]+ [Rr] " | wc -l
        echo ""
        echo "All symbols:"
        arm-none-eabi-nm "$elf" | sort -k3
    fi
done
