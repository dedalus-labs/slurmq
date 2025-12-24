#!/bin/bash

# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# MIT-style headers (2 lines, no box)
PYTHON_HEADER="# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT"

SHELL_HEADER="# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT"

# Counters
PROCESSED=0
UPDATED=0
SKIPPED=0

has_copyright() {
    head -n 5 "$1" | grep -q "Copyright (c) 2025 Dedalus Labs"
}

add_python_header() {
    local file="$1"
    local temp_file
    temp_file=$(mktemp)

    if [[ $(head -c 2 "$file") == "#!" ]]; then
        head -n 1 "$file" > "$temp_file"
        echo "" >> "$temp_file"
        echo "$PYTHON_HEADER" >> "$temp_file"
        echo "" >> "$temp_file"
        tail -n +2 "$file" >> "$temp_file"
    else
        echo "$PYTHON_HEADER" > "$temp_file"
        echo "" >> "$temp_file"
        cat "$file" >> "$temp_file"
    fi

    mv "$temp_file" "$file"
}

add_shell_header() {
    local file="$1"
    local temp_file
    temp_file=$(mktemp)

    if [[ $(head -c 2 "$file") == "#!" ]]; then
        head -n 1 "$file" > "$temp_file"
        echo "" >> "$temp_file"
        echo "$SHELL_HEADER" >> "$temp_file"
        echo "" >> "$temp_file"
        tail -n +2 "$file" >> "$temp_file"
    else
        echo "$SHELL_HEADER" > "$temp_file"
        echo "" >> "$temp_file"
        cat "$file" >> "$temp_file"
    fi

    mv "$temp_file" "$file"
}

process_file() {
    local file="$1"
    local type="$2"

    PROCESSED=$((PROCESSED + 1))

    # Skip empty files
    if [[ ! -s "$file" ]]; then
        echo -e "${YELLOW}SKIP${NC} $file (empty)"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    # Skip if already has copyright
    if has_copyright "$file"; then
        echo -e "${YELLOW}SKIP${NC} $file (has copyright)"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    case "$type" in
        py) add_python_header "$file" ;;
        sh) add_shell_header "$file" ;;
    esac

    echo -e "${GREEN}ADD${NC}  $file"
    UPDATED=$((UPDATED + 1))
}

echo "Adding copyright headers..."
echo "=========================="

# Process Python files (skip __pycache__, .venv, tests might be optional)
while IFS= read -r -d '' file; do
    if [[ ! "$file" =~ __pycache__|\.venv|\.egg-info ]]; then
        process_file "$file" "py"
    fi
done < <(find . -name "*.py" -type f -print0 2>/dev/null)

# Process shell scripts
while IFS= read -r -d '' file; do
    process_file "$file" "sh"
done < <(find ./scripts -name "*.sh" -type f -print0 2>/dev/null)

echo ""
echo "Summary"
echo "======="
echo -e "Processed: ${YELLOW}$PROCESSED${NC}"
echo -e "Updated:   ${GREEN}$UPDATED${NC}"
echo -e "Skipped:   ${YELLOW}$SKIPPED${NC}"

