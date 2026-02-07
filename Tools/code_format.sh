#!/bin/bash
#
# Auto format script for FPBInject project
# Only formats files in Source/ and App/ directories
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if clang-format is installed

# Prefer clang-format-14 if available
if command -v clang-format-14 &>/dev/null; then
    CLANG_FORMAT=clang-format-14
elif command -v clang-format &>/dev/null; then
    CLANG_FORMAT=clang-format
else
    echo "Error: clang-format is not installed"
    echo "Install it with: sudo apt install clang-format-14"
    exit 1
fi

# Check if cmake-format is installed
CMAKE_FORMAT=""
# Also check ~/.local/bin (pip user install location)
export PATH="$PATH:$HOME/.local/bin"
if command -v cmake-format &>/dev/null; then
    CMAKE_FORMAT=cmake-format
elif command -v gersemi &>/dev/null; then
    CMAKE_FORMAT=gersemi
fi

# Check if shfmt is installed (for shell scripts)
SHFMT=""
if command -v shfmt &>/dev/null; then
    SHFMT=shfmt
fi

# Print clang-format version for debug
echo "Using clang-format: $CLANG_FORMAT"
echo "Version: $($CLANG_FORMAT --version)"
if [[ -n "$CMAKE_FORMAT" ]]; then
    echo "Using cmake-format: $CMAKE_FORMAT"
    if [[ "$CMAKE_FORMAT" == "cmake-format" ]]; then
        echo "Version: $($CMAKE_FORMAT --version 2>&1 | head -1)"
    else
        echo "Version: $($CMAKE_FORMAT --version 2>&1 | head -1)"
    fi
else
    echo "Warning: cmake-format/gersemi not installed, CMake files will be skipped"
    echo "Install with: pip install cmake-format  OR  pip install gersemi"
fi

if [[ -n "$SHFMT" ]]; then
    echo "Using shfmt: $SHFMT"
    echo "Version: $($SHFMT --version 2>&1 | head -1)"
else
    echo "Warning: shfmt not installed, shell scripts will be skipped"
    echo "Install with: sudo apt install shfmt  OR  go install mvdan.cc/sh/v3/cmd/shfmt@latest"
fi

# Directories to format (C/C++ files)
FORMAT_DIRS=(
    "$PROJECT_ROOT/Source"
    "$PROJECT_ROOT/App"
)

# Additional directories for CMake files only
CMAKE_EXTRA_DIRS=(
    "$PROJECT_ROOT/cmake"
    "$PROJECT_ROOT/Tools/nuttx_mock"
)

# Directories containing shell scripts
SHELL_DIRS=(
    "$PROJECT_ROOT/Tools"
)

# Root CMakeLists.txt
ROOT_CMAKE="$PROJECT_ROOT/CMakeLists.txt"

# File extensions to format
EXTENSIONS=("*.c" "*.cpp" "*.h" "*.hpp")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "FPBInject Code Formatter"
echo "========================================="
echo ""

# Check if --check flag is passed (dry run mode)
CHECK_MODE=false
if [[ "$1" == "--check" ]]; then
    CHECK_MODE=true
    echo -e "${YELLOW}Running in check mode (no changes will be made)${NC}"
    echo ""
fi

# Count files
TOTAL_FILES=0
FORMATTED_FILES=0
FAILED_FILES=0

for dir in "${FORMAT_DIRS[@]}"; do
    if [[ ! -d "$dir" ]]; then
        echo -e "${YELLOW}Warning: Directory not found: $dir${NC}"
        continue
    fi

    echo "Processing: $dir"

    for ext in "${EXTENSIONS[@]}"; do
        while IFS= read -r -d '' file; do
            TOTAL_FILES=$((TOTAL_FILES + 1))

            if $CHECK_MODE; then
                # Check if file needs formatting
                if ! $CLANG_FORMAT --dry-run --Werror "$file" 2>/dev/null; then
                    echo -e "  ${RED}[NEEDS FORMAT]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                else
                    echo -e "  ${GREEN}[OK]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                fi
            else
                # Format file in place
                if $CLANG_FORMAT -i "$file" 2>/dev/null; then
                    echo -e "  ${GREEN}[FORMATTED]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                else
                    echo -e "  ${RED}[FAILED]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                fi
            fi
        done < <(find "$dir" -type f -name "$ext" -print0 2>/dev/null)
    done
done

# Process CMake files if cmake-format is available
if [[ -n "$CMAKE_FORMAT" ]]; then
    echo ""
    echo "Processing CMake files..."

    # Function to format a single cmake file
    format_cmake_file() {
        local file="$1"
        TOTAL_FILES=$((TOTAL_FILES + 1))

        if $CHECK_MODE; then
            # Check if file needs formatting
            if [[ "$CMAKE_FORMAT" == "cmake-format" ]]; then
                FORMATTED_CONTENT=$($CMAKE_FORMAT "$file" 2>/dev/null)
                ORIGINAL_CONTENT=$(cat "$file")
                if [[ "$FORMATTED_CONTENT" != "$ORIGINAL_CONTENT" ]]; then
                    echo -e "  ${RED}[NEEDS FORMAT]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                else
                    echo -e "  ${GREEN}[OK]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                fi
            else
                # gersemi has --check flag
                if ! $CMAKE_FORMAT --check "$file" 2>/dev/null; then
                    echo -e "  ${RED}[NEEDS FORMAT]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                else
                    echo -e "  ${GREEN}[OK]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                fi
            fi
        else
            # Format file in place
            if [[ "$CMAKE_FORMAT" == "cmake-format" ]]; then
                if $CMAKE_FORMAT -i "$file" 2>/dev/null; then
                    echo -e "  ${GREEN}[FORMATTED]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                else
                    echo -e "  ${RED}[FAILED]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                fi
            else
                # gersemi uses --in-place
                if $CMAKE_FORMAT --in-place "$file" 2>/dev/null; then
                    echo -e "  ${GREEN}[FORMATTED]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                else
                    echo -e "  ${RED}[FAILED]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                fi
            fi
        fi
    }

    # Process root CMakeLists.txt
    if [[ -f "$ROOT_CMAKE" ]]; then
        format_cmake_file "$ROOT_CMAKE"
    fi

    # Process CMake files in FORMAT_DIRS (App, Source)
    for dir in "${FORMAT_DIRS[@]}"; do
        if [[ ! -d "$dir" ]]; then
            continue
        fi

        while IFS= read -r -d '' file; do
            format_cmake_file "$file"
        done < <(find "$dir" -type f \( -name "CMakeLists.txt" -o -name "*.cmake" \) -not -path "*/build/*" -print0 2>/dev/null)
    done

    # Process CMake files in CMAKE_EXTRA_DIRS (cmake, Tools/nuttx_mock)
    for dir in "${CMAKE_EXTRA_DIRS[@]}"; do
        if [[ ! -d "$dir" ]]; then
            continue
        fi

        while IFS= read -r -d '' file; do
            format_cmake_file "$file"
        done < <(find "$dir" -type f \( -name "CMakeLists.txt" -o -name "*.cmake" \) -not -path "*/build/*" -print0 2>/dev/null)
    done
fi

# Process shell scripts if shfmt is available
if [[ -n "$SHFMT" ]]; then
    echo ""
    echo "Processing shell scripts..."

    for dir in "${SHELL_DIRS[@]}"; do
        if [[ ! -d "$dir" ]]; then
            continue
        fi

        while IFS= read -r -d '' file; do
            # Skip non-shell files (check shebang or extension)
            if [[ ! "$file" =~ \.sh$ ]] && ! head -1 "$file" 2>/dev/null | grep -q '^#!.*\(bash\|sh\|zsh\)'; then
                continue
            fi

            TOTAL_FILES=$((TOTAL_FILES + 1))

            if $CHECK_MODE; then
                # Check if file needs formatting (-d flag for diff, returns non-zero if changes needed)
                if ! $SHFMT -d -i 4 -ci -bn "$file" >/dev/null 2>&1; then
                    echo -e "  ${RED}[NEEDS FORMAT]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                else
                    echo -e "  ${GREEN}[OK]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                fi
            else
                # Format file in place
                if $SHFMT -w -i 4 -ci -bn "$file" 2>/dev/null; then
                    echo -e "  ${GREEN}[FORMATTED]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                else
                    echo -e "  ${RED}[FAILED]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                fi
            fi
        done < <(find "$dir" -type f \( -name "*.sh" -o -executable \) -not -path "*/build/*" -not -name "*.py" -print0 2>/dev/null)
    done
fi

echo ""
echo "========================================="
echo "Summary:"
echo "  Total files:     $TOTAL_FILES"
if $CHECK_MODE; then
    echo "  Properly formatted: $FORMATTED_FILES"
    echo "  Need formatting:    $FAILED_FILES"
else
    echo "  Formatted:       $FORMATTED_FILES"
    echo "  Failed:          $FAILED_FILES"
fi
echo "========================================="

# Exit with error if any files need formatting (in check mode)
if $CHECK_MODE && [[ $FAILED_FILES -gt 0 ]]; then
    exit 1
fi

exit 0
