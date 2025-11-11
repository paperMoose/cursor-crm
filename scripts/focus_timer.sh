#!/bin/bash

# Focus Timer for macOS
# Usage:
#   ./scripts/focus_timer.sh "Task description" <total_minutes> <interval_minutes>
# Example:
#   ./scripts/focus_timer.sh "Your task name" 90 15
# Requires: macOS with osascript (AppleScript) available

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 \"Task description\" <total_minutes> <interval_minutes>" >&2
  exit 1
fi

TASK="$1"
TOTAL_MINUTES="$2"
INTERVAL_MINUTES="$3"

# Basic validation
if ! [[ "$TOTAL_MINUTES" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! [[ "$INTERVAL_MINUTES" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Error: total_minutes and interval_minutes must be numbers (minutes)." >&2
  exit 1
fi
if (( INTERVAL_MINUTES <= 0 )); then
  echo "Error: interval_minutes must be > 0." >&2
  exit 1
fi

TITLE="Focus Timer"
SUBTITLE="No context switching — stay on task"

escape_applescript() {
  local s="$1"
  s="${s//\\/\\\\}"   # escape backslashes
  s="${s//\"/\\\"}"   # escape double quotes
  printf "%s" "$s"
}

play_sound() {
  # Plays an audible sound independent of Notification Center to ensure audibility under Focus modes.
  # Configurable via env vars:
  #   FOCUS_SOUND_FILE (default: Submarine)
  #   FOCUS_FORCE_SOUND=1 to temporarily unmute/raise volume, then restore
  #   FOCUS_MIN_VOLUME=50 (0-100)
  local sound_file="${FOCUS_SOUND_FILE:-/System/Library/Sounds/Submarine.aiff}"
  local force="${FOCUS_FORCE_SOUND:-0}"
  local min_volume="${FOCUS_MIN_VOLUME:-50}"

  local was_muted prev_volume
  was_muted="$(osascript -e 'output muted of (get volume settings)' 2>/dev/null || echo false)"
  prev_volume="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || echo 50)"

  if [[ "$force" == "1" ]]; then
    osascript -e "set volume output volume $min_volume without output muted" >/dev/null 2>&1 || true
  fi

  if command -v afplay >/dev/null 2>&1 && [[ -f "$sound_file" ]]; then
    afplay "$sound_file" >/dev/null 2>&1 &
  else
    say "Timer alert" >/dev/null 2>&1 &
  fi

  if [[ "$force" == "1" ]]; then
    if [[ "$was_muted" == "true" ]]; then
      osascript -e "set volume output volume $prev_volume with output muted" >/dev/null 2>&1 || true
    else
      osascript -e "set volume output volume $prev_volume without output muted" >/dev/null 2>&1 || true
    fi
  fi
}

notify() {
  local msg="$1"
  local title_esc subtitle_esc msg_esc
  title_esc=$(escape_applescript "$TITLE")
  subtitle_esc=$(escape_applescript "$SUBTITLE")
  msg_esc=$(escape_applescript "$msg")
  # Request Notification Center to play a named sound; may still be gated by Focus settings
  osascript -e "display notification \"$msg_esc\" with title \"$title_esc\" subtitle \"$subtitle_esc\" sound name \"Submarine\"" >/dev/null 2>&1 || true
  # Always play an independent sound that is not blocked by Focus
  play_sound
}

format_hhmm() {
  # Prints current time + N minutes in HH:MM format (24h)
  local add_min="$1"
  # macOS BSD date supports -v option
  date -v+"${add_min}"M +"%H:%M" 2>/dev/null || date -u -d "+${add_min} minutes" +"%H:%M" 2>/dev/null || echo ""
}

# Convert minutes (integer or decimal) to whole seconds
SECONDS_TOTAL=$(awk -v m="$TOTAL_MINUTES" 'BEGIN{printf "%.0f", m*60}')
SECONDS_INTERVAL=$(awk -v m="$INTERVAL_MINUTES" 'BEGIN{printf "%.0f", m*60}')

on_exit() {
  notify "Timer cancelled for: $TASK"
}
trap on_exit INT TERM

END_TIME_HHMM=$(format_hhmm "$TOTAL_MINUTES")

notify "Starting: $TASK  •  Ends ~ $END_TIME_HHMM"

elapsed=0
while (( elapsed < SECONDS_TOTAL )); do
  sleep "$SECONDS_INTERVAL" || true
  elapsed=$(( elapsed + SECONDS_INTERVAL ))
  if (( elapsed >= SECONDS_TOTAL )); then
    break
  fi
  remaining=$(( SECONDS_TOTAL - elapsed ))
  remaining_min=$(( (remaining + 59) / 60 ))
  notify "Check-in: $remaining_min min remaining  •  $TASK"
done

notify "Block complete: $TASK  •  Great job staying focused"
exit 0


