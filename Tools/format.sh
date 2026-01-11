#!/bin/bash
#
# Auto format script for FPBInject project
# Only formats files in Source/ and App/ directories
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if clang-format is installed
if ! command -v clang-format &> /dev/null; then
    echo "Error: clang-format is not installed"
    echo "Install it with: sudo apt install clang-format"
    exit 1
fi

# Directories to format
FORMAT_DIRS=(
    "$PROJECT_ROOT/Source"
    "$PROJECT_ROOT/App"
)

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
                if ! clang-format --dry-run --Werror "$file" 2>/dev/null; then
                    echo -e "  ${RED}[NEEDS FORMAT]${NC} $file"
                    FAILED_FILES=$((FAILED_FILES + 1))
                else
                    echo -e "  ${GREEN}[OK]${NC} $file"
                    FORMATTED_FILES=$((FORMATTED_FILES + 1))
                fi
            else
                # Format file in place
                if clang-format -i "$file" 2>/dev/null; then
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
