#!/usr/bin/env python3
"""
imessage_ingest.py

Read-only iMessage ingestion that scans recent messages for lightweight
task cues (e.g., "todo:", "task:") and emits @reminder/@calendar tags.

Safety first:
- We NEVER write to the live Messages database.
- On every run, we copy the database to a temporary file and query the copy.
- Alternatively, we open with SQLite URI mode=ro when possible.

Usage examples:
  # Dry-run: print inferred reminders from today 00:00
  python3 scripts/imessage_ingest.py --since "today" --dry-run

  # Append results to a weekly file and generate calendar blocks for focus items
  python3 scripts/imessage_ingest.py --since "2025-08-15" \
    --output-file "weeks/week of 2025-08-18.md" \
    --add-calendar --default-at "today 10:00" --calendar "Work"

Requires: macOS with Full Disk Access granted to your terminal for
"~/Library/Messages/chat.db".
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from typing import Iterable, List, Optional, Tuple


APPLE_EPOCH_UNIX = 978307200  # seconds from 1970-01-01 to 2001-01-01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest iMessage tasks and emit @reminder/@calendar tags (read-only)")
    parser.add_argument("--db", default=os.path.expanduser("~/Library/Messages/chat.db"), help="Path to Messages chat.db")
    parser.add_argument("--since", required=True, help="'today'|'yesterday'|YYYY-MM-DD|YYYY-MM-DD HH:MM")
    parser.add_argument("--contains", help="Only include messages containing this substring (case-insensitive)")
    parser.add_argument("--contacts", help="Comma-separated filter of contact/handle substrings (case-insensitive)")
    parser.add_argument("--default-at", default="today 10:00", help="Default @reminder at= expression if no time parsed")
    parser.add_argument("--list", dest="reminder_list", default="Work", help="Reminders list name")
    parser.add_argument("--add-calendar", action="store_true", help="Also emit @calendar blocks for items that look like focus blocks")
    parser.add_argument("--calendar", default="Work", help="Apple Calendar name when --add-calendar is set")
    parser.add_argument("--duration", default="30m", help="Default calendar duration (e.g., 30m, 1h)")
    parser.add_argument("--output-file", help="If set, append tags to this markdown file; otherwise, print to stdout")
    parser.add_argument("--dry-run", action="store_true", help="Print only; never write to output file")
    return parser.parse_args()


def ensure_copy_readonly(db_path: str) -> str:
    """Return a safe-to-read copy path for the Messages DB.

    We copy the DB to a secure temp file to avoid locks/corruption.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)
    tmp_dir = tempfile.mkdtemp(prefix="imsg_db_")
    dst = os.path.join(tmp_dir, "chat.copy.db")
    shutil.copy2(db_path, dst)
    # Also copy the write-ahead log if present to keep consistency
    wal = db_path + "-wal"
    shm = db_path + "-shm"
    try:
        if os.path.exists(wal):
            shutil.copy2(wal, dst + "-wal")
        if os.path.exists(shm):
            shutil.copy2(shm, dst + "-shm")
    except Exception:
        # Non-fatal; we can still try to read snapshot
        pass
    return dst


def parse_since(s: str) -> dt.datetime:
    now = dt.datetime.now()
    sl = s.strip().lower()
    if sl == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if sl == "yesterday":
        y = now - dt.timedelta(days=1)
        return y.replace(hour=0, minute=0, second=0, microsecond=0)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dtv = dt.datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                dtv = dtv.replace(hour=0, minute=0)
            return dtv
        except ValueError:
            continue
    raise ValueError("--since must be today|yesterday|YYYY-MM-DD[ HH:MM]")


def to_sqlite_since_value(dt_since: dt.datetime) -> str:
    # We'll filter using SQLite datetime string, built from Apple's epoch in the DB
    # We will use WHERE datetime(date/1e9 + 978307200, 'unixepoch') >= :since
    return dt_since.strftime("%Y-%m-%d %H:%M:%S")


def open_ro_connection(copy_db_path: str) -> sqlite3.Connection:
    # Open with read-only URI to the copied database
    uri = f"file:{copy_db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def fetch_messages(conn: sqlite3.Connection, since_iso: str) -> Iterable[Tuple[int, str, str, str, str]]:
    """Yield rows: (message_id, sent_iso, sender, chat_identifier, text)"""
    conn.row_factory = sqlite3.Row
    sql = (
        """
        SELECT
            m.ROWID as message_id,
            datetime(m.date/1000000000 + ?, 'unixepoch') as sent_ts,
            COALESCE(h.id, h.uncanonicalized_id, 'unknown') as sender,
            COALESCE(c.chat_identifier, 'unknown') as chat_identifier,
            m.text as text
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.text IS NOT NULL AND LENGTH(m.text) > 0
          AND datetime(m.date/1000000000 + ?, 'unixepoch') >= ?
        ORDER BY m.date DESC
        """
    )
    cursor = conn.execute(sql, (APPLE_EPOCH_UNIX, APPLE_EPOCH_UNIX, since_iso))
    for row in cursor:
        yield (
            int(row["message_id"]),
            str(row["sent_ts"]),
            str(row["sender"]),
            str(row["chat_identifier"]),
            str(row["text"]),
        )


TRIGGER_PATTERNS = [
    re.compile(r"^\s*(todo|to-do|task)[:\-]\s*(.+)$", re.IGNORECASE),
]


def extract_task_from_text(text: str) -> Optional[str]:
    for pat in TRIGGER_PATTERNS:
        m = pat.match(text.strip())
        if m:
            body = m.group(2).strip()
            return body if body else None
    # Fallback: single-line 'todo pick up ...'
    m2 = re.match(r"^\s*todo\s+(.+)$", text, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None


def looks_like_focus_block(task: str) -> bool:
    t = task.lower()
    return any(k in t for k in ["focus", "draft", "write", "outline", "deep work", "plan "])


def format_tags(task: str, meta_note: str, default_at: str, list_name: str, add_calendar: bool, cal_name: str, duration: str) -> List[str]:
    tags: List[str] = []
    # Always add reminder
    tags.append(f"@reminder(message=\"{task}\", at=\"{default_at}\", list=\"{list_name}\", note=\"{meta_note}\", priority=5)")
    # Optionally add calendar block
    if add_calendar and looks_like_focus_block(task):
        tags.append(f"@calendar(message=\"Focus block: {task}\", at=\"{default_at}\", duration=\"{duration}\", calendar=\"{cal_name}\", location=\"Desk\", note=\"{meta_note}\")")
    return tags


def append_to_file(path: str, lines: List[str]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")


def main() -> None:
    args = parse_args()
    since_dt = parse_since(args.since)
    since_iso = to_sqlite_since_value(since_dt)

    copy_path = ensure_copy_readonly(args.db)
    try:
        conn = open_ro_connection(copy_path)
    except sqlite3.Error as e:
        sys.stderr.write(f"SQLite error: {e}\n")
        sys.stderr.write("Tip: Ensure Terminal has Full Disk Access in System Settings > Privacy & Security.\n")
        sys.exit(2)

    contact_filters: List[str] = []
    if args.contacts:
        contact_filters = [c.strip().lower() for c in args.contacts.split(",") if c.strip()]

    contains_filter = args.contains.lower() if args.contains else None

    emitted: List[str] = []
    for msg_id, sent_iso, sender, chat_identifier, text in fetch_messages(conn, since_iso):
        if contact_filters and not any(f in (sender.lower() + " " + chat_identifier.lower()) for f in contact_filters):
            continue
        if contains_filter and contains_filter not in text.lower():
            continue
        task = extract_task_from_text(text)
        if not task:
            continue
        meta_note = f"iMessage {sender} ({chat_identifier}) • {sent_iso} • msg:{msg_id}"
        tags = format_tags(
            task=task,
            meta_note=meta_note,
            default_at=args.default_at,
            list_name=args.reminder_list,
            add_calendar=args.add_calendar,
            cal_name=args.calendar,
            duration=args.duration,
        )
        emitted.extend(tags)

    if not emitted:
        print("No candidate tasks found.")
        return

    if args.output_file and not args.dry_run:
        append_to_file(args.output_file, emitted)
        print(f"Appended {len(emitted)} tag line(s) to {args.output_file}")
    else:
        for ln in emitted:
            print(ln)


if __name__ == "__main__":
    main()


