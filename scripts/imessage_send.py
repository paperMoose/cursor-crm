#!/usr/bin/env python3
"""
imessage_send.py

Scan a markdown file for @imessage(...) tags and send iMessages via the
Messages app on macOS using AppleScript.

Safety & idempotency:
- Dry-run by default; requires --yes to actually send.
- Each tag embeds a unique @source: marker (abs path + line no). We
  persist markers we have sent in .meta/imessage_sent.log to avoid
  duplicate sends.

Tag format:
  @imessage(to="+14155551234|user@example.com|Contact Name", message="Short text to send")

Examples:
  python3 scripts/imessage_send.py --file "weeks/week of 2025-08-18.md" --dry-run
  python3 scripts/imessage_send.py --file "weeks/week of 2025-08-18.md" --yes --verbose

Notes:
- You may need to grant the terminal Accessibility permission to control
  Messages via AppleScript.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple


TAG_PATTERN = re.compile(r"@imessage\(([^)]*)\)")


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
        inner = inner.replace("\\\"", '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
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


def find_tags_in_text(text: str) -> List[Tuple[int, str]]:
    tags: List[Tuple[int, str]] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        for m in TAG_PATTERN.finditer(line):
            tags.append((idx, m.group(1)))
    return tags


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def ensure_meta_log() -> str:
    meta_dir = os.path.join(os.getcwd(), ".meta")
    os.makedirs(meta_dir, exist_ok=True)
    log_path = os.path.join(meta_dir, "imessage_sent.log")
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("")
    return log_path


def load_sent_markers(log_path: str) -> set:
    sent: set = set()
    with open(log_path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                sent.add(ln)
    return sent


def append_sent_marker(log_path: str, marker: str) -> None:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(marker + "\n")


def build_applescript_send(to_handle: str, message: str) -> str:
    # Use iMessage service when possible
    return f'''
set theText to "{message.replace("\\", "\\\\").replace('"', '\\"')}"
set theHandle to "{to_handle.replace("\\", "\\\\").replace('"', '\\"')}"
tell application "Messages"
    set theService to 1st service whose service type = iMessage
    try
        set theBuddy to buddy theHandle of theService
        send theText to theBuddy
    on error
        -- Fallback: try a new outgoing text chat
        set theChat to make new text chat with properties {{service:theService, participants:{{theHandle}}}}
        send theText to theChat
    end try
end tell
'''


def send_imessage(to_handle: str, message: str, timeout_seconds: int = 12) -> None:
    script = build_applescript_send(to_handle, message)
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as tf:
        tf.write(script)
        tmp_path = tf.name
    try:
        result = subprocess.run(["osascript", tmp_path], capture_output=True, text=True, timeout=timeout_seconds)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or "osascript failed\n")
            raise RuntimeError("osascript failed")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send iMessages from @imessage tags (safe, idempotent, dry-run by default)")
    p.add_argument("--file", required=True, help="Markdown file to scan")
    p.add_argument("--yes", action="store_true", help="Actually send messages (otherwise dry-run)")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    p.add_argument("--reset-log", action="store_true", help="Clear the sent markers log before running")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    abs_path = os.path.abspath(args.file)
    text = read_text_file(abs_path)
    tags = find_tags_in_text(text)
    if not tags:
        print("No @imessage tags found.")
        return
    log_path = ensure_meta_log()
    if args.reset_log:
        open(log_path, "w").close()
    sent_markers = load_sent_markers(log_path)

    to_send: List[Tuple[str, str, str]] = []  # (marker, to, message)
    for line_no, params_text in tags:
        params = parse_tag_params(params_text)
        to_handle = params.get("to")
        message = params.get("message")
        if not to_handle or not message:
            sys.stderr.write(f"Skipping line {line_no}: 'to' and 'message' are required\n")
            continue
        marker = f"@source:{abs_path}:{line_no}"
        if marker in sent_markers:
            if args.verbose:
                print(f"[skip] already sent ({marker})")
            continue
        to_send.append((marker, to_handle, message))

    if not to_send:
        print("Nothing to send.")
        return

    for marker, to_handle, message in to_send:
        if args.verbose or not args.yes:
            print(f"@imessage -> to={to_handle} message=\"{message}\"")
        if args.yes:
            send_imessage(to_handle, message)
            append_sent_marker(log_path, marker)
            if args.verbose:
                print(f"[sent] {marker}")


if __name__ == "__main__":
    main()


