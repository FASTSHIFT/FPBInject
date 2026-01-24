#!/bin/bash
# Build test ELF file for decompilation testing
# This script should be run from the fixtures directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for ARM toolchain
if ! command -v arm-none-eabi-gcc &> /dev/null; then
    echo "Warning: arm-none-eabi-gcc not found, skipping ELF build"
    exit 0
fi

echo "Building test ELF file..."

# Compile
arm-none-eabi-gcc -c -o test_func.o test_func.c \
    -mcpu=cortex-m3 -mthumb -Os -g \
    -ffunction-sections -fdata-sections

# Link
arm-none-eabi-gcc -o test_func.elf test_func.o \
    -nostartfiles \
    -Wl,-Ttext=0x08000000 \
    -Wl,--gc-sections \
    -mcpu=cortex-m3 -mthumb

# Clean up intermediate files
rm -f test_func.o

echo "Created test_func.elf"

# Show symbols
echo ""
echo "Symbols in test_func.elf:"
arm-none-eabi-nm test_func.elf | grep -E "^[0-9a-f]+ T"
