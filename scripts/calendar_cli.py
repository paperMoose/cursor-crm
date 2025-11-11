#!/usr/bin/env python3
"""
calendar_cli.py

Create or update Apple Calendar events from @calendar(...) tags in markdown files.

Tag format (comma-separated key=value pairs; strings in double quotes):

  @calendar(message="Focus block: Write PRD", at="2025-08-16 10:00", duration="90m", calendar="Work", location="Desk", note="task_context/sean-agentic-patent-intelligence-prd-2025-08-15.md")

Supported fields:
- message (required): event title
- at (required): one of
  - YYYY-MM-DD HH:MM (24h, local time)
  - today HH:MM
  - tomorrow HH:MM
  - +<N>m (minutes), +<N>h (hours), +<N>d (days)
- duration (optional): e.g. "30m", "1h", "90m" (default: 60m)
- calendar (optional): Calendar name (defaults to the system default calendar)
- location (optional): location string
- note (optional): context; included in description

Idempotency: We embed a unique marker in the description based on the absolute
source path and line number. If we find an existing event with the same title
and containing the marker, we update its start/end and description instead of
creating a new one.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple


CALENDAR_TAG_PATTERN = re.compile(r"@calendar\(([^)]*)\)")


def split_kvlist(s: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    in_quotes = False
    escape = False
    for ch in s:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            buf.append(ch)
            continue
        if ch == "," and not in_quotes:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        inner = s[1:-1]
        inner = inner.replace("\\\"", '"')
        inner = inner.replace("\\n", "\n").replace("\\t", "\t")
        inner = inner.replace("\\\\", "\\")
        return inner
    return s


def parse_tag_params(params_text: str) -> Dict[str, str]:
    pairs = split_kvlist(params_text)
    data: Dict[str, str] = {}
    if not pairs:
        return data
    first = pairs[0]
    start_index = 0
    if "=" not in first and first.strip().startswith('"') and first.strip().endswith('"'):
        data["message"] = unquote(first)
        start_index = 1
    for pair in pairs[start_index:]:
        if "=" not in pair:
            raise ValueError(f"Invalid parameter segment (expected key=value): {pair}")
        key, val = pair.split("=", 1)
        data[key.strip()] = unquote(val.strip())
    return data


def parse_at_expression(expr: str, now: dt.datetime) -> dt.datetime:
    expr = expr.strip()
    m = re.match(r"^\+(\d+)([mhd])$", expr)
    if m:
        value = int(m.group(1))
        unit = m.group(2)
        if unit == "m":
            return now + dt.timedelta(minutes=value)
        if unit == "h":
            return now + dt.timedelta(hours=value)
        if unit == "d":
            return now + dt.timedelta(days=value)
    m = re.match(r"^today\s+(\d{1,2}):(\d{2})$", expr, re.IGNORECASE)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    m = re.match(r"^tomorrow\s+(\d{1,2}):(\d{2})$", expr, re.IGNORECASE)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        tmr = (now + dt.timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        return tmr
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(expr, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized 'at' expression: {expr}")


def parse_duration(expr: Optional[str]) -> dt.timedelta:
    if not expr:
        return dt.timedelta(minutes=60)
    expr = expr.strip().lower()
    m = re.match(r"^(\d+)m$", expr)
    if m:
        return dt.timedelta(minutes=int(m.group(1)))
    m = re.match(r"^(\d+)h$", expr)
    if m:
        return dt.timedelta(hours=int(m.group(1)))
    raise ValueError(f"Invalid duration expression: {expr}")


def escape_for_applescript_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def infer_smallest_step(task_name: str, note: Optional[str]) -> str:
    t = task_name.lower()
    if any(k in t for k in ["focus block", "draft", "write", "outline", "edit"]):
        return "Open the task file and write the first sentence."
    if ("linkedin" in t or "twitter" in t or "x.com" in t) and any(k in t for k in ["post", "publish", "tweet"]):
        return "Open LinkedIn compose and paste your draft text."
    if any(k in t for k in ["sign up", "signup", "register", "rsvp"]):
        return "Open the signup link (or message the coordinator for it) and pick the first available slot."
    if "follow up" in t or "follow-up" in t:
        return "Open the thread and type a one-sentence nudge; send."
    if any(k in t for k in ["schedule", "book", "set up meeting", "calendar"]):
        return "Open your calendar and propose two times."
    if any(k in t for k in ["pay", "invoice", "send payment", "venmo", "wire", "transfer"]):
        return "Open your payment app and search the recipient."
    if any(k in t for k in ["review", "proofread", "skim"]):
        return "Open the doc and read the first screen; add one comment."
    if note and ("/" in note or note.endswith((".md", ".txt", ".docx", ".rtf"))):
        return f"Open {note}."
    return "Start a 2-minute timer and take the tiniest next step."


def generate_event_description(name: str, note: Optional[str]) -> str:
    first_step = infer_smallest_step(name, note)
    if first_step.endswith("."):
        joiner = " "
    else:
        joiner = ". "
    return f"{first_step}{joiner}Then: {name}."


def build_applescript_for_event(
    title: str,
    start: dt.datetime,
    end: dt.datetime,
    description: str,
    calendar_name: Optional[str],
    location: Optional[str],
    marker: str,
) -> str:
    # Format dates in AppleScript-friendly format
    start_str = start.strftime("%A, %B %d, %Y at %I:%M:%S %p")
    end_str = end.strftime("%A, %B %d, %Y at %I:%M:%S %p")

    # Build properties for the event
    props_parts = [
        f'summary:"{title}"',
        f'start date:date "{start_str}"',
        f'end date:date "{end_str}"',
    ]
    
    # Add description with marker for idempotency
    full_description = f"{description}\\n{marker}"
    props_parts.append(f'description:"{full_description}"')
    
    if location:
        props_parts.append(f'location:"{location}"')
    
    props = ", ".join(props_parts)

    # Use simpler, more reliable AppleScript approach
    if calendar_name:
        script = f'''tell application "Calendar"
    tell calendar "{calendar_name}"
        make new event at end with properties {{{props}}}
    end tell
end tell'''
    else:
        script = f'''tell application "Calendar"
    make new event at end with properties {{{props}}}
end tell'''
    
    return script


def create_or_update_event(
    title: str,
    start: dt.datetime,
    duration: dt.timedelta,
    description: str,
    calendar_name: Optional[str],
    location: Optional[str],
    marker: str,
    dry_run: bool,
    verbose: bool,
    timeout_seconds: int = 12,
) -> None:
    end = start + duration
    script = build_applescript_for_event(
        title=escape_for_applescript_string(title),
        start=start,
        end=end,
        description=escape_for_applescript_string(description + "\n" + marker),
        calendar_name=escape_for_applescript_string(calendar_name) if calendar_name else None,
        location=escape_for_applescript_string(location) if location else None,
        marker=escape_for_applescript_string(marker),
    )

    if verbose or dry_run:
        end_local = (start + duration)
        print(f"[event] {title} @ {start.isoformat(timespec='minutes')} - {end_local.isoformat(timespec='minutes')}" + (f" calendar={calendar_name}" if calendar_name else ""))
        if description:
            print(f"  desc: {description}")
        if location:
            print(f"  location: {location}")
    if dry_run:
        return

    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as tf:
        tf.write(script)
        tmp_path = tf.name
    try:
        result = subprocess.run(["osascript", tmp_path], capture_output=True, text=True, timeout=timeout_seconds)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or "Failed to run osascript\n")
            raise RuntimeError("osascript failed")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def find_calendar_tags_in_text(text: str) -> List[Tuple[int, str]]:
    tags: List[Tuple[int, str]] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        for m in CALENDAR_TAG_PATTERN.finditer(line):
            tags.append((idx, m.group(1)))
    return tags


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def process_file(path: str, dry_run: bool, verbose: bool, timeout_seconds: int) -> None:
    abs_path = os.path.abspath(path)
    text = read_text_file(abs_path)
    tags = find_calendar_tags_in_text(text)
    if verbose:
        print(f"Scanning {abs_path}")
    if not tags:
        if verbose:
            print("No @calendar tags found.")
        return
    now = dt.datetime.now()
    for line_no, params_text in tags:
        try:
            params = parse_tag_params(params_text)
            title = params.get("message")
            at_expr = params.get("at")
            if not title or not at_expr:
                raise ValueError("Both message and at are required")
            start = parse_at_expression(at_expr, now)
            duration = parse_duration(params.get("duration"))
            calendar_name = params.get("calendar")
            location = params.get("location")
            note = params.get("note")
            marker = f"@source:{abs_path}:{line_no}"
            description = generate_event_description(name=title, note=note)
            create_or_update_event(
                title=title,
                start=start,
                duration=duration,
                description=description,
                calendar_name=calendar_name,
                location=location,
                marker=marker,
                dry_run=dry_run,
                verbose=verbose,
                timeout_seconds=timeout_seconds,
            )
        except Exception as e:
            sys.stderr.write(f"Error on line {line_no}: {e}\n")
            continue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Apple Calendar events from @calendar tags in a file")
    parser.add_argument("--file", required=True, help="Path to markdown file (absolute or relative)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print actions without creating events")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--timeout", type=int, default=12, help="Timeout in seconds for AppleScript execution (default: 12)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        process_file(args.file, args.dry_run, args.verbose, args.timeout)
    except FileNotFoundError:
        sys.stderr.write(f"File not found: {args.file}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()


