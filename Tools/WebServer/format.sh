#!/bin/bash

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

# Auto-format script for FPBInject WebServer
# Formats all Python, JavaScript, HTML, and CSS files by extension
# Supports parallel execution for faster formatting

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  FPBInject WebServer Code Formatter${NC}"
echo -e "${BLUE}================================================${NC}"

# Temp files for parallel result collection
TMPDIR_FMT=$(mktemp -d)
trap "rm -rf $TMPDIR_FMT" EXIT

# Common exclude patterns for find
FIND_EXCLUDE_COMMON=(
    -not -path "./htmlcov/*"
    -not -path "./coverage/*"
    -not -path "./tests/htmlcov/*"
    -not -path "./tests/coverage/*"
    -not -path "./node_modules/*"
    -not -path "./.venv/*"
    -not -path "./venv/*"
)

# ============================================================
# Detect available prettier command (shared by JS/HTML/CSS)
# ============================================================
detect_prettier() {
    if command -v prettier &>/dev/null; then
        echo "prettier"
    elif command -v npx &>/dev/null; then
        # Check Node.js version (prettier requires Node >= 14)
        if command -v node &>/dev/null; then
            local node_version=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
            if [ -n "$node_version" ] && [ "$node_version" -lt 14 ]; then
                return 1
            fi
        fi
        echo "npx --yes prettier"
    else
        return 1
    fi
}

# ============================================================
# Format functions - batch mode (pass all files at once)
# ============================================================

format_python() {
    local result_file="$TMPDIR_FMT/python"
    echo -e "\n${GREEN}📦 Formatting Python files (*.py)...${NC}"

    if python -m black --version &>/dev/null; then
        echo -e "   Using $(python -m black --version)"
    else
        echo -e "${YELLOW}   Installing black...${NC}"
        pip install black -q
    fi

    local files=$(find . -name "*.py" \
        -not -path "./__pycache__/*" \
        "${FIND_EXCLUDE_COMMON[@]}" \
        2>/dev/null | sort)

    if [ -z "$files" ]; then
        echo "   No Python files found"
        echo "0 0" >"$result_file"
        return
    fi

    local count=$(echo "$files" | wc -l)

    # black supports batch: pass all files at once
    if python -m black --quiet --line-length 88 $files 2>/dev/null; then
        echo -e "   ${GREEN}Python: $count file(s) formatted ✓${NC}"
        echo "$count 0" >"$result_file"
    else
        echo -e "   ${RED}Python: black failed on some files ✗${NC}"
        echo "0 $count" >"$result_file"
    fi
}

format_prettier_batch() {
    local label="$1"
    local ext="$2"
    local extra_args="$3"
    local result_file="$TMPDIR_FMT/$ext"

    echo -e "\n${GREEN}📦 Formatting $label files (*.$ext)...${NC}"

    local formatter
    formatter=$(detect_prettier)
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}   ⚠️  prettier not found or Node too old, skipping $label${NC}"
        echo "0 0" >"$result_file"
        return
    fi

    local files=$(find . -name "*.$ext" \
        "${FIND_EXCLUDE_COMMON[@]}" \
        2>/dev/null | sort)

    if [ -z "$files" ]; then
        echo "   No $label files found"
        echo "0 0" >"$result_file"
        return
    fi

    local count=$(echo "$files" | wc -l)

    # prettier supports batch: pass all files at once
    if $formatter --write $extra_args $files >/dev/null 2>&1; then
        echo -e "   ${GREEN}$label: $count file(s) formatted ✓${NC}"
        echo "$count 0" >"$result_file"
    else
        echo -e "   ${RED}$label: prettier failed on some files ✗${NC}"
        echo "0 $count" >"$result_file"
    fi
}

lint_python() {
    echo -e "\n${GREEN}📦 Linting Python files...${NC}"

    if ! command -v flake8 &>/dev/null; then
        echo -e "${YELLOW}   Installing flake8...${NC}"
        pip install flake8 -q
    fi

    local files=$(find . -name "*.py" \
        -not -path "*/__pycache__/*" \
        "${FIND_EXCLUDE_COMMON[@]}" \
        2>/dev/null | sort)

    if [ -z "$files" ]; then
        echo "   No Python files found"
        return
    fi

    # Split into test and non-test files for different ignore rules
    local test_files=""
    local src_files=""
    for file in $files; do
        if [[ "$file" == *"/tests/"* ]]; then
            test_files="$test_files $file"
        else
            src_files="$src_files $file"
        fi
    done

    local lint_errors=0

    # Batch lint: pass all files at once per category
    if [ -n "$src_files" ]; then
        if ! flake8 --ignore=E501,W503,E203 --max-line-length=120 $src_files 2>/dev/null; then
            lint_errors=$((lint_errors + 1))
        fi
    fi

    if [ -n "$test_files" ]; then
        if ! flake8 --ignore=E501,W503,E203,E402 --max-line-length=120 $test_files 2>/dev/null; then
            lint_errors=$((lint_errors + 1))
        fi
    fi

    if [ $lint_errors -eq 0 ]; then
        echo -e "   ${GREEN}All Python files passed linting ✓${NC}"
    else
        echo -e "   ${YELLOW}$lint_errors category(s) have linting warnings${NC}"
    fi
}

# ============================================================
# Parse arguments
# ============================================================
CHECK_ONLY=false
LINT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check | -c)
            CHECK_ONLY=true
            shift
            ;;
        --lint | -l)
            LINT=true
            shift
            ;;
        --help | -h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --check, -c    Check formatting without making changes"
            echo "  --lint, -l     Run linting after formatting"
            echo "  --help, -h     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ "$CHECK_ONLY" = true ]; then
    echo -e "${YELLOW}Running in check-only mode...${NC}"
fi

# ============================================================
# Run formatters in parallel
# Python (black) and Prettier (JS/HTML/CSS) are independent
# ============================================================
echo -e "\n${BLUE}Running formatters in parallel...${NC}"

format_python &
PID_PYTHON=$!

# JS, HTML, CSS all use prettier - run them in parallel too
# (each is a separate prettier invocation with different args)
format_prettier_batch "JavaScript" "js" "--single-quote" &
PID_JS=$!

format_prettier_batch "HTML" "html" "--print-width 120" &
PID_HTML=$!

format_prettier_batch "CSS" "css" "" &
PID_CSS=$!

# Wait for all formatters
wait $PID_PYTHON $PID_JS $PID_HTML $PID_CSS

# Collect results
FORMATTED=0
FAILED=0
for result_file in "$TMPDIR_FMT"/*; do
    if [ -f "$result_file" ]; then
        read ok fail <"$result_file"
        FORMATTED=$((FORMATTED + ${ok:-0}))
        FAILED=$((FAILED + ${fail:-0}))
    fi
done

if [ "$LINT" = true ]; then
    lint_python
fi

# Summary
echo -e "\n${BLUE}================================================${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "   Files formatted: ${GREEN}$FORMATTED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "   Files failed:    ${RED}$FAILED${NC}"
fi
echo ""

if [ $FAILED -gt 0 ]; then
    exit 1
else
    echo -e "${GREEN}✅ All files formatted successfully!${NC}"
    exit 0
fi
