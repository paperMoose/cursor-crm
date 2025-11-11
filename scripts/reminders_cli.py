#!/usr/bin/env python3
"""
reminders_cli.py

Scan a weekly markdown file for @reminder(...) tags and create Apple Reminders
on macOS via AppleScript. Designed to be idempotent by embedding a stable
@source marker in the reminder body, so re-running won't duplicate existing
reminders.

Tag format (comma-separated key=value pairs; strings in double quotes):

  @reminder(message="Draft LinkedIn post", at="2025-08-16 09:30", list="Work", note="weeks/week of 2025-08-11.md", priority=1, flagged=true)
  @reminder("Draft LinkedIn post", at="2025-08-16 09:30", list="Work")
  @reminder(message="Draft LinkedIn post", at="today 17:30", id="draft-li-post")

Supported fields:
- message (required): string
- at (required): one of
  - YYYY-MM-DD HH:MM (24h, local time)
  - today HH:MM
  - tomorrow HH:MM
  - +<N>m (minutes), +<N>h (hours), +<N>d (days)
- list (optional): Reminders list name
- note (optional): string; appended to body
- priority (optional): 1 (high), 5 (medium), 9 (low)
- flagged (optional): true|false
 - id (optional): stable identifier for idempotency. If provided, it is included
   in the @source marker so edits or line shifts won't create duplicates. If not
   provided, a stable hash is derived from the absolute file path and message.

Examples inside weekly file:
- "Follow up with Sean" on a specific time: @reminder(message="Follow up with Sean", at="2025-08-16 09:30", list="Work")
- In 30 minutes: @reminder(message="Take a break", at="+30m")
- Today at 5:30 PM: @reminder(message="Engage on Twitter 15m", at="today 17:30")

Usage:
  python3 scripts/reminders_cli.py --file "weeks/week of 2025-08-11.md" [--dry-run] [--verbose]

Exit codes:
  0 on success, non-zero on errors.
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
import hashlib
import json


REMINDER_TAG_PATTERN = re.compile(r"@reminder\(([^)]*)\)")
def infer_smallest_step(task_name: str, note: Optional[str]) -> str:
    """Infer a smallest concrete step based on the task name and optional note.

    Heuristic rules prefer minimal activation energy actions.
    """
    t = task_name.lower()
    # Writing or planning tasks
    if any(k in t for k in ["focus block", "draft", "write", "outline", "edit"]):
        return "Open the task file and write the first sentence."
    # Social posts
    if ("linkedin" in t or "twitter" in t or "x.com" in t) and any(k in t for k in ["post", "publish", "tweet"]):
        return "Open LinkedIn compose and paste your draft text."
    # Sign-up / register
    if any(k in t for k in ["sign up", "signup", "register", "rsvp"]):
        return "Open the signup link (or message the coordinator for it) and pick the first available slot."
    # Follow-ups
    if "follow up" in t or "follow-up" in t:
        return "Open the thread and type a one-sentence nudge; send."
    # Scheduling
    if any(k in t for k in ["schedule", "book", "set up meeting", "calendar"]):
        return "Open your calendar and propose two times."
    # Payments
    if any(k in t for k in ["pay", "invoice", "send payment", "venmo", "wire", "transfer"]):
        return "Open your payment app and search the recipient."
    # Reviews
    if any(k in t for k in ["review", "proofread", "skim"]):
        return "Open the doc and read the first screen; add one comment."
    # Default: open context if we have it, otherwise start a 2-minute timer
    if note and ("/" in note or note.endswith((".md", ".txt", ".docx", ".rtf"))):
        return f"Open {note}."
    return "Start a 2-minute timer and take the tiniest next step."


def generate_descriptive_note(name: str, note: Optional[str], list_name: Optional[str]) -> str:
    """Return a concise, human-readable prompt with an inferred first step."""
    first_step = infer_smallest_step(name, note)
    if first_step.endswith("."):
        joiner = " "
    else:
        joiner = ". "
    return f"{first_step}{joiner}Then: {name}."



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Apple Reminders from @reminder tags in a weekly file")
    parser.add_argument("--file", required=False, help="Path to weekly markdown file (absolute or relative)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print actions without creating reminders")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--timeout", type=int, default=12, help="Timeout in seconds for AppleScript execution (default: 12)")
    parser.add_argument("--report-day", type=str, help="Report reminders for a given day: 'today' or YYYY-MM-DD; lists and counts reminders")
    parser.add_argument("--reset-log", action="store_true", help="Delete the sent reminders log before processing")
    parser.add_argument("--ignore-sent-log", action="store_true", help="Do not consult .cursor/sent_reminders.json; always attempt to send/update")
    return parser.parse_args()


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_kvlist(s: str) -> List[str]:
    """Split a comma-separated key=value list respecting quoted strings."""
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
        # Unescape simple sequences \" and \\
        inner = s[1:-1]
        inner = inner.replace("\\\"", '"')
        inner = inner.replace("\\n", "\n").replace("\\t", "\t")
        inner = inner.replace("\\\\", "\\")
        return inner
    return s


def parse_bool(s: str) -> bool:
    s_lower = s.strip().lower()
    if s_lower in {"true", "yes", "1"}:
        return True
    if s_lower in {"false", "no", "0"}:
        return False
    raise ValueError(f"Invalid boolean value: {s}")


def parse_tag_params(params_text: str) -> Dict[str, str]:
    pairs = split_kvlist(params_text)
    data: Dict[str, str] = {}
    if not pairs:
        return data
    # Human-friendly shorthand: first positional quoted string as message
    first = pairs[0]
    start_index = 0
    if "=" not in first and first.strip().startswith('"') and first.strip().endswith('"'):
        data["message"] = unquote(first)
        start_index = 1
    for pair in pairs[start_index:]:
        if "=" not in pair:
            raise ValueError(f"Invalid parameter segment (expected key=value): {pair}")
        key, val = pair.split("=", 1)
        key = key.strip()
        val = unquote(val.strip())
        data[key] = val
    return data


def parse_at_expression(expr: str, now: dt.datetime) -> dt.datetime:
    expr = expr.strip()
    # Relative: +30m, +2h, +1d
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
    # today HH:MM
    m = re.match(r"^today\s+(\d{1,2}):(\d{2})$", expr, re.IGNORECASE)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    # tomorrow HH:MM
    m = re.match(r"^tomorrow\s+(\d{1,2}):(\d{2})$", expr, re.IGNORECASE)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        tmr = (now + dt.timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        return tmr
    # Absolute: YYYY-MM-DD HH:MM
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(expr, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized 'at' expression: {expr}")



def build_applescript_for_reminder(
    name: str,
    due: dt.datetime,
    body: str,
    list_name: Optional[str],
    priority: Optional[int],
    flagged: Optional[bool],
    marker: str,
) -> str:
    # Format date in AppleScript-friendly format
    due_str = due.strftime("%A, %B %d, %Y at %I:%M:%S %p")

    # Build properties for the reminder
    props_parts = [
        f'name:"{name}"',
        f'remind me date:date "{due_str}"',
    ]
    
    # Add body with marker
    full_body = f"{body}\\n{marker}" if body else marker
    props_parts.append(f'body:"{full_body}"')
    
    if isinstance(priority, int):
        props_parts.append(f"priority:{priority}")
    if isinstance(flagged, bool):
        props_parts.append(f"flagged:{str(flagged).lower()}")
    
    props = ", ".join(props_parts)

    # Use simple, direct AppleScript approach
    if list_name:
        script = f'''tell application "Reminders"
    try
        tell list "{list_name}"
            make new reminder with properties {{{props}}}
        end tell
    on error
        -- Create list if it doesn't exist
        make new list with properties {{name:"{list_name}"}}
        tell list "{list_name}"
            make new reminder with properties {{{props}}}
        end tell
    end try
end tell'''
    else:
        script = f'''tell application "Reminders"
    make new reminder with properties {{{props}}}
end tell'''
    
    return script


def escape_for_applescript_string(s: str) -> str:
    # Escape backslashes and quotes for inclusion in AppleScript string literal
    return s.replace("\\", "\\\\").replace('"', '\\"')


def report_day(day_expr: str, timeout_seconds: int = 12) -> None:
    """List reminders for 'today' or a specific date (YYYY-MM-DD), detect overload, and print suggestions."""
    now = dt.datetime.now()
    if day_expr.lower() == "today":
        target = now.date()
    else:
        target = dt.datetime.strptime(day_expr, "%Y-%m-%d").date()

    # AppleScript to fetch reminders with remind me date on target day
    # We collect name and remind me date as text for simple parsing.
    target_dt = dt.datetime.combine(target, dt.time())
    start_str = target_dt.strftime("%A, %B %d, %Y at 12:00:00 AM")
    script = f'''
set startDate to date "{start_str}"
set endDate to (startDate + 1 * days)

set outLines to {{}}
tell application "Reminders"
    try
        repeat with r in (reminders whose remind me date is not missing value and remind me date ≥ startDate and remind me date < endDate)
            try
                set end of outLines to (name of r & "\t" & (remind me date of r as text))
            on error
                -- skip any items with odd/missing dates
            end try
        end repeat
    on error
        -- if any issue, return empty list
    end try
end tell
set AppleScript's text item delimiters to linefeed
return outLines as text
'''
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as tf:
        tf.write(script)
        tmp_path = tf.name
    try:
        result = subprocess.run(["osascript", tmp_path], capture_output=True, text=True, timeout=timeout_seconds)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "osascript failed")
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        count = len(lines)
        print(f"Reminders for {target.isoformat()}: {count}")
        for ln in lines:
            print(f"- {ln}")
        # Heuristic: more than 6 items is overloaded
        if count >= 7:
            print("\nSuggestion: You have a heavy reminder load today. Consider moving lower-priority items to tomorrow or batching them in a single block.")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

def create_reminder(
    name: str,
    due: dt.datetime,
    note: str,
    list_name: Optional[str],
    priority: Optional[int],
    flagged: Optional[bool],
    marker: str,
    dry_run: bool,
    verbose: bool,
    timeout_seconds: int = 12,
) -> None:
    body = note if note else ""
    script = build_applescript_for_reminder(
        name=escape_for_applescript_string(name),
        due=due,
        body=escape_for_applescript_string(body),
        list_name=escape_for_applescript_string(list_name) if list_name else None,
        priority=priority,
        flagged=flagged,
        marker=escape_for_applescript_string(marker),
    )

    if verbose or dry_run:
        print(f"[reminder] {name} @ {due.isoformat(timespec='minutes')}" + (f" list={list_name}" if list_name else ""))
        if note:
            print(f"  note: {note}")
        if priority is not None or flagged is not None:
            print(f"  priority={priority} flagged={flagged}")
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


def _extract_tag_params_from_line(line: str) -> List[str]:
    """Extract all @reminder(...) parameter strings from a single line.

    This parser is aware of quotes and parentheses inside quoted strings, so
    a message like: message="Follow up (Battery)" will be parsed correctly.
    """
    results: List[str] = []
    i = 0
    n = len(line)
    while i < n:
        start = line.find("@reminder(", i)
        if start == -1:
            break
        j = start + len("@reminder(")
        depth = 1
        in_quotes = False
        escape = False
        buf_chars: List[str] = []
        while j < n:
            ch = line[j]
            if escape:
                buf_chars.append(ch)
                escape = False
                j += 1
                continue
            if ch == "\\":
                escape = True
                buf_chars.append(ch)
                j += 1
                continue
            if ch == '"':
                in_quotes = not in_quotes
                buf_chars.append(ch)
                j += 1
                continue
            if ch == '(' and not in_quotes:
                depth += 1
                buf_chars.append(ch)
                j += 1
                continue
            if ch == ')' and not in_quotes:
                depth -= 1
                if depth == 0:
                    # finished this tag
                    results.append(''.join(buf_chars))
                    i = j + 1
                    break
            buf_chars.append(ch)
            j += 1
        else:
            # No closing paren found; stop
            i = n
    return results


def find_tags_in_text(text: str) -> List[Tuple[int, str]]:
    tags: List[Tuple[int, str]] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        for params_text in _extract_tag_params_from_line(line):
            tags.append((idx, params_text))
    return tags


def _compute_stable_marker(abs_path: str, params: Dict[str, str]) -> str:
    """Return a stable @source marker that survives line shifts.

    Priority:
    - If the tag provides an explicit id=..., use that directly (best for stability).
    - Else, derive a short hash from the absolute file path and message text.

    We intentionally avoid including the line number or relative 'at' expressions,
    so edits above the tag or rescheduling won't create a new identity.
    """
    explicit_id = params.get("id")
    if explicit_id:
        # Id-based markers do not include file path so tags can be moved to a
        # central file without changing identity.
        return f"@source:id:{explicit_id}"
    # Fallback: stable hash of path + message
    message = params.get("message", "")
    h = hashlib.sha1()
    h.update(abs_path.encode("utf-8"))
    h.update(b"\n")
    h.update(message.encode("utf-8"))
    digest = h.hexdigest()[:12]
    return f"@source:{abs_path}#{digest}"


def _get_repo_root() -> str:
    # repo root assumed as parent of scripts/ directory (where this file lives)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _sent_log_path() -> str:
    return os.path.join(_get_repo_root(), ".cursor", "sent_reminders.json")


def _load_sent_log() -> List[Dict[str, str]]:
    path = _sent_log_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def _save_sent_log(entries: List[Dict[str, str]]) -> None:
    path = _sent_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def _append_sent_log(entry: Dict[str, str]) -> None:
    entries = _load_sent_log()
    entries.append(entry)
    _save_sent_log(entries)


def process_file(path: str, dry_run: bool, verbose: bool, timeout_seconds: int, ignore_sent_log: bool, reset_log: bool) -> None:
    abs_path = os.path.abspath(path)
    text = read_text_file(abs_path)
    tags = find_tags_in_text(text)
    if verbose:
        print(f"Scanning {abs_path}")
    if not tags:
        if verbose:
            print("No @reminder tags found.")
        return
    # Reset sent log if requested
    if reset_log and not dry_run:
        try:
            os.remove(_sent_log_path())
            if verbose:
                print("[log] Reset .cursor/sent_reminders.json")
        except FileNotFoundError:
            pass
    sent_log = [] if reset_log else _load_sent_log()
    sent_ids = {e.get("id") for e in sent_log if e.get("id")}
    now = dt.datetime.now()
    for line_no, params_text in tags:
        try:
            params = parse_tag_params(params_text)
            name = params.get("message")
            at_expr = params.get("at")
            if not name or not at_expr:
                raise ValueError("Both message and at are required")
            due = parse_at_expression(at_expr, now)
            list_name = params.get("list")
            note = params.get("note")
            priority = None
            if "priority" in params:
                priority = int(params["priority"])  # may raise ValueError
            flagged = None
            if "flagged" in params:
                flagged = parse_bool(params["flagged"])  # may raise ValueError
            # Use a stable marker so re-running after file edits does not duplicate
            marker = _compute_stable_marker(abs_path, params)
            explicit_id = params.get("id")
            # Idempotency via external sent log: if an id exists and was sent, skip
            if explicit_id and not ignore_sent_log and explicit_id in sent_ids:
                if verbose:
                    print(f"[skip] Reminder with id={explicit_id} already sent (logged). Skipping send/update.")
                continue
            create_reminder(
                name=name,
                due=due,
                note=generate_descriptive_note(name=name, note=note, list_name=list_name),
                list_name=list_name,
                priority=priority,
                flagged=flagged,
                marker=marker,
                dry_run=dry_run,
                verbose=verbose,
                timeout_seconds=timeout_seconds,
            )
            # Append to sent log when actually sent (non-dry-run)
            if not dry_run:
                entry = {
                    "id": explicit_id or "",
                    "message": name,
                    "at": due.isoformat(timespec="minutes"),
                    "list": list_name or "",
                    "note": note or "",
                    "priority": str(priority) if priority is not None else "",
                    "flagged": str(flagged) if flagged is not None else "",
                    "source": marker,
                    "file": abs_path,
                    "line": str(line_no),
                    "logged_at": dt.datetime.now().isoformat(timespec="seconds"),
                }
                _append_sent_log(entry)
        except Exception as e:
            sys.stderr.write(f"Error on line {line_no}: {e}\n")
            continue


def main() -> None:
    args = parse_args()
    # Support report mode first
    if args.report_day:
        try:
            report_day(args.report_day, timeout_seconds=args.timeout)
        except Exception as e:
            sys.stderr.write(f"Report error: {e}\n")
            sys.exit(2)
        return
    try:
        if not args.file:
            raise FileNotFoundError("--file is required unless using --report-day")
        process_file(
            path=args.file,
            dry_run=args.dry_run,
            verbose=args.verbose,
            timeout_seconds=args.timeout,
            ignore_sent_log=args.ignore_sent_log,
            reset_log=args.reset_log,
        )
    except FileNotFoundError:
        sys.stderr.write(f"File not found: {args.file}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()


