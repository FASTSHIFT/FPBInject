#!/bin/bash
# MIT License
# Copyright (c) 2026 VIFEX
#
# Build and run FPBInject firmware unit tests with coverage
#
# Usage:
#   ./run_tests.sh              - Build and run tests
#   ./run_tests.sh coverage     - Build, run, and generate coverage report
#   ./run_tests.sh clean        - Clean build artifacts
#   ./run_tests.sh --threshold <N> - Set coverage threshold (default: 85%)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

# Coverage threshold (default 80%)
LINE_THRESHOLD=80
FUNC_THRESHOLD=80

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Clean build
clean_build() {
    print_header "Cleaning build artifacts"
    rm -rf "${BUILD_DIR}"
    print_success "Build directory cleaned"
}

# Build tests
build_tests() {
    print_header "Building tests"
    
    mkdir -p "${BUILD_DIR}"
    cd "${BUILD_DIR}"
    
    print_info "Configuring CMake..."
    cmake -DCOVERAGE=ON ..
    
    print_info "Building..."
    make -j$(nproc)
    
    print_success "Build complete"
}

# Run tests
run_tests() {
    print_header "Running tests"
    
    cd "${BUILD_DIR}"
    
    # Run main test runner
    print_info "Running main tests..."
    ./test_runner
    MAIN_EXIT_CODE=$?
    
    # Run NuttX debugmon tests
    print_info "Running NuttX debugmon tests..."
    ./test_runner_nuttx
    NUTTX_EXIT_CODE=$?
    
    # Check results
    if [ $MAIN_EXIT_CODE -eq 0 ] && [ $NUTTX_EXIT_CODE -eq 0 ]; then
        print_success "All tests passed"
    else
        if [ $MAIN_EXIT_CODE -ne 0 ]; then
            print_error "Main tests failed (exit code: $MAIN_EXIT_CODE)"
        fi
        if [ $NUTTX_EXIT_CODE -ne 0 ]; then
            print_error "NuttX tests failed (exit code: $NUTTX_EXIT_CODE)"
        fi
        exit 1
    fi
}

# Generate coverage report and check threshold
generate_coverage() {
    print_header "Generating coverage report"
    
    cd "${BUILD_DIR}"
    
    # Check for lcov
    if ! command -v lcov &> /dev/null; then
        print_error "lcov not found. Install with: sudo apt-get install lcov"
        exit 1
    fi
    
    # Create coverage directory
    mkdir -p coverage
    
    # Detect gcov version to match compiler
    # gcc-12 needs gcov-12, etc.
    GCOV_TOOL="gcov"
    CC_VERSION=$(cc --version | head -1 | grep -oP '\d+' | head -1)
    if command -v gcov-${CC_VERSION} &> /dev/null; then
        GCOV_TOOL="gcov-${CC_VERSION}"
    fi
    print_info "Using ${GCOV_TOOL}"
    
    # Capture coverage data
    print_info "Capturing coverage data..."
    lcov --capture --directory . --output-file coverage/coverage.info --gcov-tool ${GCOV_TOOL} 2>/dev/null || true
    
    # Remove test files and argparse library from coverage
    print_info "Filtering coverage data..."
    lcov --remove coverage/coverage.info \
        '/usr/*' \
        '*/test_*' \
        '*/mock_*' \
        '*/argparse/*' \
        --output-file coverage/coverage.info --gcov-tool ${GCOV_TOOL} 2>/dev/null || true
    
    # Check for genhtml
    if command -v genhtml &> /dev/null; then
        print_info "Generating HTML report..."
        genhtml coverage/coverage.info --output-directory coverage/html 2>/dev/null || true
        
        print_success "Coverage report generated: ${BUILD_DIR}/coverage/html/index.html"
    fi
    
    # Extract coverage percentages
    print_info "Coverage summary:"
    COVERAGE_OUTPUT=$(lcov --summary coverage/coverage.info 2>&1)
    echo "$COVERAGE_OUTPUT"
    
    # Parse line and function coverage
    LINE_COV=$(echo "$COVERAGE_OUTPUT" | grep "lines" | sed 's/.*: \([0-9.]*\)%.*/\1/' | head -1)
    FUNC_COV=$(echo "$COVERAGE_OUTPUT" | grep "functions" | sed 's/.*: \([0-9.]*\)%.*/\1/' | head -1)
    
    # Default to 0 if parsing failed
    LINE_COV=${LINE_COV:-0}
    FUNC_COV=${FUNC_COV:-0}
    
    echo ""
    print_info "Line coverage: ${LINE_COV}% (threshold: ${LINE_THRESHOLD}%)"
    print_info "Function coverage: ${FUNC_COV}% (threshold: ${FUNC_THRESHOLD}%)"
    echo ""
    
    # Check thresholds (using bc for float comparison)
    LINE_OK=$(echo "$LINE_COV >= $LINE_THRESHOLD" | bc -l 2>/dev/null || echo "1")
    FUNC_OK=$(echo "$FUNC_COV >= $FUNC_THRESHOLD" | bc -l 2>/dev/null || echo "1")
    
    if [ "$LINE_OK" = "1" ] && [ "$FUNC_OK" = "1" ]; then
        print_success "Coverage thresholds met!"
        return 0
    else
        print_error "Coverage below threshold!"
        if [ "$LINE_OK" = "0" ]; then
            print_error "Line coverage ${LINE_COV}% < ${LINE_THRESHOLD}%"
        fi
        if [ "$FUNC_OK" = "0" ]; then
            print_error "Function coverage ${FUNC_COV}% < ${FUNC_THRESHOLD}%"
        fi
        return 1
    fi
}

# Parse arguments
ACTION=""
while [[ $# -gt 0 ]]; do
    case $1 in
        clean)
            ACTION="clean"
            shift
            ;;
        coverage)
            ACTION="coverage"
            shift
            ;;
        build)
            ACTION="build"
            shift
            ;;
        --threshold)
            LINE_THRESHOLD="$2"
            FUNC_THRESHOLD="$2"
            shift 2
            ;;
        --line-threshold)
            LINE_THRESHOLD="$2"
            shift 2
            ;;
        --func-threshold)
            FUNC_THRESHOLD="$2"
            shift 2
            ;;
        --ci)
            # CI mode - stricter output
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [action] [options]"
            echo ""
            echo "Actions:"
            echo "  (none)     Build and run tests"
            echo "  coverage   Build, run, and generate coverage report"
            echo "  build      Only build tests"
            echo "  clean      Clean build artifacts"
            echo ""
            echo "Options:"
            echo "  --threshold <N>       Set both coverage thresholds (default: 85%)"
            echo "  --line-threshold <N>  Set line coverage threshold"
            echo "  --func-threshold <N>  Set function coverage threshold"
            echo "  --ci                  CI mode (stricter output)"
            echo "  -h, --help            Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main
case "${ACTION}" in
    clean)
        clean_build
        ;;
    coverage)
        clean_build
        build_tests
        run_tests
        generate_coverage
        ;;
    build)
        build_tests
        ;;
    *)
        build_tests
        run_tests
        ;;
esac
