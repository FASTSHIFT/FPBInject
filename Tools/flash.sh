#!/bin/bash
#
# flash.sh - Flash firmware to STM32 via ST-Link or DAPLink
#
# Usage:
#   ./flash.sh [options] <file.hex|file.bin|file.elf>
#
# Options:
#   -p, --probe <type>   Probe type: stlink (default) or daplink
#   -a, --addr <addr>    Flash address for .bin files (default: 0x08000000)
#   -r, --reset          Reset after flash
#   -e, --erase          Erase before flash
#   -v, --verify         Verify after flash
#   -h, --help           Show help
#
# Examples:
#   ./flash.sh build/FPBInject.hex
#   ./flash.sh -p daplink build/FPBInject.bin
#   ./flash.sh -p stlink -e -v build/FPBInject.elf

set -e

PROBE="stlink"
ADDR="0x08000000"
RESET=0
ERASE=0
VERIFY=0
FILE=""

show_help() {
    cat << EOF
Usage: $0 [options] <file.hex|file.bin|file.elf>

Options:
  -p, --probe <type>   Probe type: stlink (default) or daplink
  -a, --addr <addr>    Flash address for .bin files (default: 0x08000000)
  -r, --reset          Reset after flash
  -e, --erase          Erase before flash
  -v, --verify         Verify after flash
  -h, --help           Show help

Supported probes:
  stlink   - ST-Link V2/V2.1/V3 (using st-flash/st-link)
  daplink  - DAPLink/CMSIS-DAP (using openocd or pyocd)

Examples:
  $0 build/FPBInject.hex
  $0 -p daplink build/FPBInject.bin
  $0 -p stlink -e -v build/FPBInject.elf
EOF
}

check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 not found. Please install it."
        return 1
    fi
    return 0
}

flash_stlink() {
    local file="$1"
    local ext="${file##*.}"

    # Check for st-flash
    if ! check_tool "st-flash"; then
        echo "Install with: sudo apt install stlink-tools"
        exit 1
    fi

    local cmd="st-flash"

    if [ $ERASE -eq 1 ]; then
        echo "Erasing flash..."
        st-flash erase
    fi

    echo "Flashing with ST-Link: $file"

    case "$ext" in
        hex)
            $cmd --format ihex write "$file"
            ;;
        bin)
            $cmd write "$file" "$ADDR"
            ;;
        elf)
            # Convert ELF to bin first
            local binfile="${file%.elf}.bin"
            if check_tool "arm-none-eabi-objcopy"; then
                arm-none-eabi-objcopy -O binary "$file" "$binfile"
                $cmd write "$binfile" "$ADDR"
            else
                echo "Error: arm-none-eabi-objcopy not found for ELF conversion"
                exit 1
            fi
            ;;
        *)
            echo "Error: Unknown file format: $ext"
            exit 1
            ;;
    esac

    if [ $VERIFY -eq 1 ]; then
        echo "Verifying..."
        # st-flash doesn't have direct verify, re-read and compare would be needed
        echo "Note: st-flash verify not directly supported, skipping"
    fi

    if [ $RESET -eq 1 ]; then
        echo "Resetting target..."
        st-flash reset
    fi

    echo "Done!"
}

flash_daplink() {
    local file="$1"
    local ext="${file##*.}"

    # Try pyocd first, then openocd
    if check_tool "pyocd" 2>/dev/null; then
        flash_daplink_pyocd "$file" "$ext"
    elif check_tool "openocd" 2>/dev/null; then
        flash_daplink_openocd "$file" "$ext"
    else
        echo "Error: Neither pyocd nor openocd found."
        echo "Install pyocd: pip install pyocd"
        echo "Install openocd: sudo apt install openocd"
        exit 1
    fi
}

flash_daplink_pyocd() {
    local file="$1"
    local ext="$2"

    echo "Flashing with pyOCD (DAPLink): $file"

    local cmd="pyocd flash"

    if [ $ERASE -eq 1 ]; then
        cmd="$cmd --erase chip"
    fi

    case "$ext" in
        hex|elf)
            $cmd "$file"
            ;;
        bin)
            $cmd --base-address "$ADDR" "$file"
            ;;
        *)
            echo "Error: Unknown file format: $ext"
            exit 1
            ;;
    esac

    if [ $RESET -eq 1 ]; then
        echo "Resetting target..."
        pyocd reset
    fi

    echo "Done!"
}

flash_daplink_openocd() {
    local file="$1"
    local ext="$2"

    echo "Flashing with OpenOCD (DAPLink): $file"

    local cmds=""

    if [ $ERASE -eq 1 ]; then
        cmds="$cmds -c 'flash erase_sector 0 0 last'"
    fi

    case "$ext" in
        hex)
            cmds="$cmds -c 'program $file verify'"
            ;;
        bin)
            cmds="$cmds -c 'program $file $ADDR verify'"
            ;;
        elf)
            cmds="$cmds -c 'program $file verify'"
            ;;
        *)
            echo "Error: Unknown file format: $ext"
            exit 1
            ;;
    esac

    if [ $RESET -eq 1 ]; then
        cmds="$cmds -c 'reset run'"
    fi

    cmds="$cmds -c 'exit'"

    openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
        -c "adapter speed 4000" \
        -c "init" \
        $cmds

    echo "Done!"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--probe)
            PROBE="$2"
            shift 2
            ;;
        -a|--addr)
            ADDR="$2"
            shift 2
            ;;
        -r|--reset)
            RESET=1
            shift
            ;;
        -e|--erase)
            ERASE=1
            shift
            ;;
        -v|--verify)
            VERIFY=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            FILE="$1"
            shift
            ;;
    esac
done

# Check file
if [ -z "$FILE" ]; then
    echo "Error: No file specified"
    show_help
    exit 1
fi

if [ ! -f "$FILE" ]; then
    echo "Error: File not found: $FILE"
    exit 1
fi

# Flash
case "$PROBE" in
    stlink|st-link)
        flash_stlink "$FILE"
        ;;
    daplink|dap|cmsis-dap)
        flash_daplink "$FILE"
        ;;
    *)
        echo "Error: Unknown probe type: $PROBE"
        echo "Supported: stlink, daplink"
        exit 1
        ;;
esac
