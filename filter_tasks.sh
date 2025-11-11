#!/bin/bash

# This script filters task context files and displays their status.

# Directories
TASK_DIR="task_context"

# Colors for output
C_RESET='\033[0m'
C_RED='\033[0;31m'
C_GREEN='\033[0;32m'
C_YELLOW='\033[0;33m'
C_BLUE='\033[0;34m'

echo -e "${C_BLUE}--- Task Status Report ---${C_RESET}"

# Function to process files for a given status
process_status() {
    local status=$1
    local color=$2
    
    echo -e "\n${color}■ ${status}${C_RESET}"
    
    # Find files with the given status
    files=$(grep -l "\\*\\*Status:\\*\\* ${status}" ${TASK_DIR}/*.md)
    
    if [ -z "$files" ]; then
        echo "  No tasks with this status."
        return
    fi
    
    for file in $files; do
        title=$(head -n 1 "$file" | sed 's/# //')
        echo "  - ${title}"
    done
}

# Process each status
process_status "Complete" "${C_GREEN}"
process_status "In Progress" "${C_YELLOW}"
process_status "Not Started" "${C_RESET}"
process_status "Blocked" "${C_RED}"

echo -e "\n${C_BLUE}--- End of Report ---${C_RESET}" 