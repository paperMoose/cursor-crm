#!/bin/bash

# This script audits all weekly plan files and reports incomplete tasks,
# highlighting tasks that have been moved multiple times.

# Colors for output
C_RESET='\033[0m'
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_YELLOW='\033[0;33m'          # Moved once
C_ORANGE='\033[38;5;208m'       # Moved multiple times

echo -e "${C_BLUE}--- Incomplete Task Audit ---${C_RESET}"

# Find all weekly plan files and process them safely
find . -name "week of *.md" -print0 | sort -z | while IFS= read -r -d '' file; do
    # Get incomplete tasks, excluding lines that are just headers or separators
    incomplete_tasks=$(grep -E "\[ \]" "$file" | grep -v "\[X\]" | sed 's/^[[:space:]]*//' | grep -v -E "^(##|---|###)")
    
    if [ ! -z "$incomplete_tasks" ]; then
        echo -e "\n${C_BLUE}■ $(basename "$file" .md)${C_RESET}"
        while IFS= read -r task; do
            # Check for moved tasks and count them
            if [[ "$task" == *"(moved from"* ]]; then
                # Count commas to determine move count. 0 commas = 1 move.
                commas=$(echo "$task" | tr -cd ',' | wc -c)
                move_count=$((commas + 1))

                if [ "$move_count" -gt 1 ]; then
                    color=$C_ORANGE
                    icon="🔁"
                else
                    color=$C_YELLOW
                    icon="➡️"
                fi
                echo -e "  ${color}${icon}${C_RESET} ${task}"
            else
                echo -e "  ${C_RED}☐${C_RESET} ${task}"
            fi
        done <<< "$incomplete_tasks"
    fi
done

echo -e "\n${C_BLUE}--- End of Audit ---${C_RESET}" 