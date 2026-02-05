#!/bin/bash
#
# FPBInject Build Test Script
# Tests all configuration combinations to ensure they compile successfully
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_test"
TOOLCHAIN_FILE="$PROJECT_ROOT/cmake/arm-none-eabi-gcc.cmake"
NUTTX_MOCK_DIR="$SCRIPT_DIR/nuttx_mock"

# ARM toolchain path (can be set via --toolchain argument)
ARM_TOOLCHAIN_PATH=""

# Configuration options
APP_SELECTS=(1 2 3)
APP_NAMES=("BLINK" "TEST" "FUNC_LOADER")

# FL_ALLOC_MODE only applies to APP_SELECT=3 (FUNC_LOADER)
ALLOC_MODES=("STATIC" "LIBC" "UMM")

# Trampoline options (only test a subset for now)
TRAMPOLINE_CONFIGS=(
    "OFF;OFF"    # Default: trampoline enabled, ASM
    "OFF;ON"     # Trampoline enabled, C implementation
    "ON;OFF"     # No trampoline (direct remap)
)

# DebugMonitor options
DEBUGMON_CONFIGS=(
    "OFF"    # DebugMonitor enabled (default)
    "ON"     # DebugMonitor disabled
)

# Statistics
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Failed configurations
declare -a FAILED_CONFIGS

# Print header
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  FPBInject Build Test${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Print test result
print_result() {
    local config="$1"
    local result="$2"
    local time="$3"
    
    if [ "$result" == "PASS" ]; then
        echo -e "  ${GREEN}✓ PASS${NC} - $config (${time}s)"
    elif [ "$result" == "FAIL" ]; then
        echo -e "  ${RED}✗ FAIL${NC} - $config"
    else
        echo -e "  ${YELLOW}○ SKIP${NC} - $config"
    fi
}

# Build a configuration
build_config() {
    local app_select="$1"
    local alloc_mode="$2"
    local no_trampoline="$3"
    local no_asm="$4"
    local config_name="$5"
    local no_debugmon="${6:-OFF}"
    
    local build_subdir="$BUILD_DIR/$config_name"
    
    # Create build directory
    mkdir -p "$build_subdir"
    
    # Run cmake
    local cmake_args=(
        -B "$build_subdir"
        -S "$PROJECT_ROOT"
        -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_FILE"
        -DAPP_SELECT="$app_select"
        -DFPB_NO_TRAMPOLINE="$no_trampoline"
        -DFPB_TRAMPOLINE_NO_ASM="$no_asm"
        -DFPB_NO_DEBUGMON="$no_debugmon"
    )
    
    # Add alloc mode for func_loader
    if [ "$app_select" == "3" ]; then
        cmake_args+=(-DFL_ALLOC_MODE="$alloc_mode")
    fi
    
    # Configure
    if ! cmake "${cmake_args[@]}" > "$build_subdir/cmake.log" 2>&1; then
        return 1
    fi
    
    # Build
    if ! cmake --build "$build_subdir" --parallel > "$build_subdir/build.log" 2>&1; then
        return 1
    fi
    
    # Check if ELF file exists
    if [ ! -f "$build_subdir/FPBInject.elf" ]; then
        return 1
    fi
    
    return 0
}

# Build NuttX configuration (using mock API)
build_nuttx_config() {
    local alloc_mode="$1"
    local no_trampoline="$2"
    local no_asm="$3"
    local config_name="$4"
    local no_debugmon="${5:-OFF}"
    local nuttx_buf_size="${6:-1024}"
    local use_file="${7:-OFF}"
    local file_backend="${8:-POSIX}"
    
    local build_subdir="$BUILD_DIR/$config_name"
    
    # Create build directory
    mkdir -p "$build_subdir"
    
    # Set ARM toolchain path if found
    if [ -n "$ARM_TOOLCHAIN_PATH" ]; then
        export ARM_TOOLCHAIN_PATH
    fi
    
    # Run cmake with ARM cross-compiler
    local cmake_args=(
        -B "$build_subdir"
        -S "$NUTTX_MOCK_DIR"
        -DFPB_NO_TRAMPOLINE="$no_trampoline"
        -DFPB_TRAMPOLINE_NO_ASM="$no_asm"
        -DFPB_NO_DEBUGMON="$no_debugmon"
        -DFL_ALLOC_MODE="$alloc_mode"
        -DFL_NUTTX_BUF_SIZE="$nuttx_buf_size"
        -DFL_USE_FILE="$use_file"
        -DFL_FILE_BACKEND="$file_backend"
    )
    
    # Configure
    if ! cmake "${cmake_args[@]}" > "$build_subdir/cmake.log" 2>&1; then
        return 1
    fi
    
    # Build
    if ! cmake --build "$build_subdir" --parallel > "$build_subdir/build.log" 2>&1; then
        return 1
    fi
    
    # Check if library file exists
    if [ ! -f "$build_subdir/libfpbinject_nuttx.a" ]; then
        return 1
    fi
    
    return 0
}

# Run all tests
run_tests() {
    echo "Toolchain: $TOOLCHAIN_FILE"
    echo "Build Dir: $BUILD_DIR"
    if [ -n "$ARM_TOOLCHAIN_PATH" ]; then
        echo "ARM Toolchain: $ARM_TOOLCHAIN_PATH"
    fi
    echo ""
    
    # Clean build directory
    if [ -d "$BUILD_DIR" ]; then
        echo "Cleaning previous build test directory..."
        rm -rf "$BUILD_DIR"
    fi
    mkdir -p "$BUILD_DIR"
    
    echo ""
    echo -e "${YELLOW}Testing APP_SELECT configurations...${NC}"
    echo ""
    
    # Test each APP_SELECT
    for i in "${!APP_SELECTS[@]}"; do
        local app="${APP_SELECTS[$i]}"
        local app_name="${APP_NAMES[$i]}"
        
        echo -e "${BLUE}--- APP_SELECT=$app ($app_name) ---${NC}"
        
        if [ "$app" == "3" ]; then
            # For FUNC_LOADER, test all allocation modes
            for alloc in "${ALLOC_MODES[@]}"; do
                # Test with default trampoline config
                local config_name="APP${app}_${alloc}"
                local config_desc="APP=$app($app_name) ALLOC=$alloc"
                
                TOTAL_TESTS=$((TOTAL_TESTS + 1))
                
                local start_time=$(date +%s)
                
                if build_config "$app" "$alloc" "OFF" "OFF" "$config_name"; then
                    local end_time=$(date +%s)
                    local elapsed=$((end_time - start_time))
                    
                    print_result "$config_desc" "PASS" "$elapsed"
                    PASSED_TESTS=$((PASSED_TESTS + 1))
                else
                    print_result "$config_desc" "FAIL" ""
                    FAILED_TESTS=$((FAILED_TESTS + 1))
                    FAILED_CONFIGS+=("$config_desc")
                fi
            done
        else
            # For other apps, just test default config
            local config_name="APP${app}"
            local config_desc="APP=$app($app_name)"
            
            TOTAL_TESTS=$((TOTAL_TESTS + 1))
            
            local start_time=$(date +%s)
            
            if build_config "$app" "STATIC" "OFF" "OFF" "$config_name"; then
                local end_time=$(date +%s)
                local elapsed=$((end_time - start_time))
                
                print_result "$config_desc" "PASS" "$elapsed"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                print_result "$config_desc" "FAIL" ""
                FAILED_TESTS=$((FAILED_TESTS + 1))
                FAILED_CONFIGS+=("$config_desc")
            fi
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Testing Trampoline configurations (with FUNC_LOADER)...${NC}"
    echo ""
    
    # Test trampoline configurations with FUNC_LOADER + STATIC
    for tramp_config in "${TRAMPOLINE_CONFIGS[@]}"; do
        IFS=';' read -r no_tramp no_asm <<< "$tramp_config"
        
        local config_name="TRAMP_${no_tramp}_${no_asm}"
        local config_desc="NO_TRAMPOLINE=$no_tramp NO_ASM=$no_asm"
        
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
        
        local start_time=$(date +%s)
        
        if build_config "3" "STATIC" "$no_tramp" "$no_asm" "$config_name"; then
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            
            print_result "$config_desc" "PASS" "$elapsed"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            print_result "$config_desc" "FAIL" ""
            FAILED_TESTS=$((FAILED_TESTS + 1))
            FAILED_CONFIGS+=("$config_desc")
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Testing DebugMonitor configurations (with FUNC_LOADER)...${NC}"
    echo ""
    
    # Test DebugMonitor configurations with FUNC_LOADER + STATIC
    for debugmon_config in "${DEBUGMON_CONFIGS[@]}"; do
        local config_name="DEBUGMON_${debugmon_config}"
        local config_desc="NO_DEBUGMON=$debugmon_config"
        
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
        
        local start_time=$(date +%s)
        
        if build_config "3" "STATIC" "OFF" "OFF" "$config_name" "$debugmon_config"; then
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            
            print_result "$config_desc" "PASS" "$elapsed"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            print_result "$config_desc" "FAIL" ""
            FAILED_TESTS=$((FAILED_TESTS + 1))
            FAILED_CONFIGS+=("$config_desc")
        fi
    done

    echo ""
    echo -e "${YELLOW}Testing NuttX platform (mock API)...${NC}"
    echo ""
    
    # Test NuttX platform with FL_NUTTX_BUF_SIZE=1024 (static allocation)
    local config_name="NUTTX_STATIC"
    local config_desc="NuttX BUF_SIZE=1024"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    local start_time=$(date +%s)
    
    if build_nuttx_config "STATIC" "OFF" "ON" "$config_name" "OFF" "1024"; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))
        
        print_result "$config_desc" "PASS" "$elapsed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_result "$config_desc" "FAIL" ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_CONFIGS+=("$config_desc")
    fi
    
    # Test NuttX platform with FL_NUTTX_BUF_SIZE=0 (dynamic allocation)
    config_name="NUTTX_DYNAMIC"
    config_desc="NuttX BUF_SIZE=0"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    start_time=$(date +%s)
    
    if build_nuttx_config "STATIC" "OFF" "ON" "$config_name" "OFF" "0"; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))
        
        print_result "$config_desc" "PASS" "$elapsed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_result "$config_desc" "FAIL" ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_CONFIGS+=("$config_desc")
    fi
    
    # Test NuttX with DebugMonitor disabled (static allocation)
    config_name="NUTTX_NO_DEBUGMON"
    config_desc="NuttX NO_DEBUGMON=ON"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    start_time=$(date +%s)
    
    if build_nuttx_config "STATIC" "OFF" "ON" "$config_name" "ON" "1024"; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))
        
        print_result "$config_desc" "PASS" "$elapsed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_result "$config_desc" "FAIL" ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_CONFIGS+=("$config_desc")
    fi

    echo ""
    echo -e "${YELLOW}Testing File Transfer configurations (NuttX)...${NC}"
    echo ""

    # Test NuttX without file transfer (FL_USE_FILE=OFF)
    config_name="NUTTX_NO_FILE"
    config_desc="NuttX FL_USE_FILE=OFF"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    start_time=$(date +%s)
    
    if build_nuttx_config "STATIC" "OFF" "ON" "$config_name" "OFF" "1024" "OFF"; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))
        
        print_result "$config_desc" "PASS" "$elapsed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_result "$config_desc" "FAIL" ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_CONFIGS+=("$config_desc")
    fi

    # Test NuttX with file transfer using POSIX backend
    config_name="NUTTX_FILE_POSIX"
    config_desc="NuttX FL_USE_FILE=ON FL_FILE_BACKEND=POSIX"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    start_time=$(date +%s)
    
    if build_nuttx_config "STATIC" "OFF" "ON" "$config_name" "OFF" "1024" "ON" "POSIX"; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))
        
        print_result "$config_desc" "PASS" "$elapsed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_result "$config_desc" "FAIL" ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_CONFIGS+=("$config_desc")
    fi

    # Test NuttX with file transfer using LIBC backend
    config_name="NUTTX_FILE_LIBC"
    config_desc="NuttX FL_USE_FILE=ON FL_FILE_BACKEND=LIBC"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    start_time=$(date +%s)
    
    if build_nuttx_config "STATIC" "OFF" "ON" "$config_name" "OFF" "1024" "ON" "LIBC"; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))
        
        print_result "$config_desc" "PASS" "$elapsed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_result "$config_desc" "FAIL" ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_CONFIGS+=("$config_desc")
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Test Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "  Total:   $TOTAL_TESTS"
    echo -e "  ${GREEN}Passed:  $PASSED_TESTS${NC}"
    echo -e "  ${RED}Failed:  $FAILED_TESTS${NC}"
    echo -e "  ${YELLOW}Skipped: $SKIPPED_TESTS${NC}"
    echo ""
    
    if [ ${#FAILED_CONFIGS[@]} -gt 0 ]; then
        echo -e "${RED}Failed configurations:${NC}"
        for config in "${FAILED_CONFIGS[@]}"; do
            echo "  - $config"
        done
        echo ""
    fi
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}All tests passed! ✓${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed! ✗${NC}"
        return 1
    fi
}

# Cleanup option
cleanup() {
    if [ -d "$BUILD_DIR" ]; then
        echo "Cleaning up build test directory..."
        rm -rf "$BUILD_DIR"
    fi
}

# Parse arguments
CLEAN_AFTER=false
CLEAN_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_AFTER=true
            shift
            ;;
        --clean-only)
            CLEAN_ONLY=true
            shift
            ;;
        --toolchain)
            ARM_TOOLCHAIN_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --clean            Clean build_test directory after testing"
            echo "  --clean-only       Only clean build_test directory, don't run tests"
            echo "  --toolchain <path> Path to ARM toolchain bin directory"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main
if [ "$CLEAN_ONLY" == true ]; then
    cleanup
    exit 0
fi

# Set ARM toolchain path if provided
if [ -n "$ARM_TOOLCHAIN_PATH" ]; then
    export PATH="$ARM_TOOLCHAIN_PATH:$PATH"
fi

print_header
run_tests
print_summary
result=$?

if [ "$CLEAN_AFTER" == true ]; then
    cleanup
fi

# Run allocator unit tests if main tests passed
if [ $result -eq 0 ]; then
    echo ""
    echo -e "${YELLOW}Running func_allocator unit tests...${NC}"
    echo ""
    
    ALLOCATOR_TEST_DIR="$BUILD_DIR/allocator_test"
    mkdir -p "$ALLOCATOR_TEST_DIR"
    
    # Compile allocator test with host compiler
    ALLOCATOR_SRC="$PROJECT_ROOT/App/func_loader/func_allocator_test.c"
    ALLOCATOR_IMPL="$PROJECT_ROOT/App/func_loader/func_allocator.c"
    ALLOCATOR_BIN="$ALLOCATOR_TEST_DIR/func_allocator_test"
    
    if gcc -DFL_USE_ALLOCATOR_TEST -Wall -Wextra -O2 \
           -I"$PROJECT_ROOT/App/func_loader" \
           -o "$ALLOCATOR_BIN" "$ALLOCATOR_SRC" "$ALLOCATOR_IMPL" 2>"$ALLOCATOR_TEST_DIR/compile.log"; then
        echo -e "  ${GREEN}✓ Compilation successful${NC}"
        
        # Run the test
        if "$ALLOCATOR_BIN" > "$ALLOCATOR_TEST_DIR/test.log" 2>&1; then
            echo -e "  ${GREEN}✓ All allocator tests passed${NC}"
            cat "$ALLOCATOR_TEST_DIR/test.log"
        else
            echo -e "  ${RED}✗ Allocator tests failed${NC}"
            cat "$ALLOCATOR_TEST_DIR/test.log"
            result=1
        fi
    else
        echo -e "  ${RED}✗ Compilation failed${NC}"
        cat "$ALLOCATOR_TEST_DIR/compile.log"
        result=1
    fi
fi

exit $result
