#!/usr/bin/env python3
"""
Apple Mail CLI helper

Features:
- List unread emails (default) from Apple Mail via JXA (osascript -l JavaScript)
- Filter by date (today, --since, --until), subject, sender
- Blocklist senders/domains via a file
- Output as table (default), JSON, or count

Notes:
- Requires Apple Mail configured on this Mac.
- Uses JXA to return message metadata as JSON with ISO timestamps for reliable parsing.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, date, timedelta
from email.utils import parseaddr
from typing import Iterable, List, Optional, Tuple


JXA_TEMPLATE = r"""
const UNREAD_ONLY = %UNREAD_ONLY%;
const LIMIT = %LIMIT%;
const INCLUDE_BODY = %INCLUDE_BODY%;

const Mail = Application('Mail');
const inbox = Mail.inbox;

function fetchMessages() {
  let msgs = inbox.messages();
  if (UNREAD_ONLY) {
    try {
      msgs = inbox.messages.whose({ readStatus: false })();
    } catch (e) {
      // Fall back to all messages if 'whose' fails
      msgs = inbox.messages();
    }
  }
  const out = [];
  const n = Math.min(msgs.length, LIMIT);
  for (let i = 0; i < n; i++) {
    const m = msgs[i];
    let dateISO = null;
    try {
      const d = m.dateReceived();
      if (d) { dateISO = d.toISOString(); }
    } catch (e) { dateISO = null; }

    let mailboxName = null;
    try { mailboxName = m.mailbox().name(); } catch (e) { mailboxName = null; }

    let sender = null;
    try { sender = m.sender(); } catch (e) { sender = null; }

    let subject = null;
    try { subject = m.subject(); } catch (e) { subject = null; }

    let read = null;
    try { read = m.readStatus(); } catch (e) { read = null; }

    let flagged = null;
    try { flagged = m.flaggedStatus(); } catch (e) { flagged = null; }

    let id = null;
    try { id = m.id(); } catch (e) { id = null; }

    let body = null;
    if (INCLUDE_BODY) {
      try { body = m.content(); } catch (e) { body = null; }
    }

    out.push({
      id: id,
      subject: subject,
      sender: sender,
      dateISO: dateISO,
      read: read,
      flagged: flagged,
      mailbox: mailboxName,
      body: body
    });
  }
  return out;
}

JSON.stringify(fetchMessages());
"""


@dataclass
class MailItem:
    id: Optional[int]
    subject: str
    sender: str
    sender_email: str
    date: Optional[datetime]
    read: Optional[bool]
    flagged: Optional[bool]
    mailbox: Optional[str]
    body: Optional[str]


def run_jxa(unread_only: bool, limit: int, include_body: bool) -> List[dict]:
    code = (
        JXA_TEMPLATE
        .replace("%UNREAD_ONLY%", "true" if unread_only else "false")
        .replace("%LIMIT%", str(max(1, limit)))
        .replace("%INCLUDE_BODY%", "true" if include_body else "false")
    )
    try:
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", code],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("osascript not found. This script requires macOS.", file=sys.stderr)
        sys.exit(2)

    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to run osascript.", file=sys.stderr)
        sys.exit(proc.returncode)

    try:
        data = json.loads(proc.stdout)
        if not isinstance(data, list):
            raise ValueError("Unexpected JXA output shape")
        return data
    except json.JSONDecodeError as e:
        print("Failed to parse JXA JSON output:", file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        sys.exit(3)


def parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        # Expecting ISO 8601 with Z or timezone, e.g., 2025-08-21T12:34:56.789Z
        value = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return value
    except Exception:
        return None


def normalize_sender_email(sender_field: str) -> str:
    name, addr = parseaddr(sender_field or "")
    return addr.lower()


def load_blocklist(path: Optional[str]) -> List[str]:
    if not path:
        return []
    try:
        entries = [ln.strip().lower() for ln in open(path, "r", encoding="utf-8").read().splitlines()]
        return [e for e in entries if e and not e.startswith("#")]
    except FileNotFoundError:
        print(f"Blocklist file not found: {path}", file=sys.stderr)
        return []


def is_blocked(sender_email: str, blocklist: List[str]) -> bool:
    if not sender_email:
        return False
    for item in blocklist:
        if item.startswith("@"):
            # Domain match
            if sender_email.endswith(item):
                return True
        elif "@" in item:
            if sender_email == item:
                return True
        else:
            # Substring match fallback (e.g., domain without @)
            if item in sender_email:
                return True
    return False


def coerce_items(raw: List[dict]) -> List[MailItem]:
    items: List[MailItem] = []
    for it in raw:
        sender = it.get("sender") or ""
        items.append(
            MailItem(
                id=it.get("id"),
                subject=(it.get("subject") or ""),
                sender=sender,
                sender_email=normalize_sender_email(sender),
                date=parse_iso(it.get("dateISO")),
                read=it.get("read"),
                flagged=it.get("flagged"),
                mailbox=it.get("mailbox"),
                body=it.get("body") if isinstance(it.get("body"), str) else None,
            )
        )
    return items


def apply_filters(
    items: List[MailItem],
    today_only: bool,
    since_date: Optional[date],
    until_date: Optional[date],
    subject_contains: Optional[str],
    from_contains: Optional[str],
    blocklist: List[str],
    include_blocked: bool,
) -> List[Tuple[MailItem, bool]]:
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(date.today(), datetime.min.time()).astimezone(timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)

    subject_pat = subject_contains.lower() if subject_contains else None
    from_pat = from_contains.lower() if from_contains else None

    filtered: List[Tuple[MailItem, bool]] = []
    for item in items:
        # Date filters
        if item.date is not None:
            dt = item.date.astimezone(timezone.utc)
            if today_only and not (today_start <= dt < tomorrow_start):
                continue
            if since_date is not None:
                since_dt = datetime.combine(since_date, datetime.min.time()).astimezone(timezone.utc)
                if dt < since_dt:
                    continue
            if until_date is not None:
                until_dt = datetime.combine(until_date, datetime.max.time()).astimezone(timezone.utc)
                if dt > until_dt:
                    continue
        else:
            # If no date, exclude when date filtering is used
            if today_only or since_date is not None or until_date is not None:
                continue

        # Subject filter
        if subject_pat and subject_pat not in item.subject.lower():
            continue

        # From filter (in either display string or parsed email)
        if from_pat and (from_pat not in item.sender.lower() and from_pat not in item.sender_email.lower()):
            continue

        blocked = is_blocked(item.sender_email, blocklist)
        if blocked and not include_blocked:
            continue

        filtered.append((item, blocked))

    # Sort newest first by date (None last)
    filtered.sort(key=lambda t: (t[0].date is None, t[0].date), reverse=True)
    return filtered


def format_table(items: List[Tuple[MailItem, bool]], columns: List[str]) -> str:
    # Build rows
    rows: List[List[str]] = []
    header = [col.capitalize() for col in columns]
    for item, blocked in items:
        row: List[str] = []
        for col in columns:
            if col == "date":
                value = item.date.astimezone().strftime("%Y-%m-%d %H:%M") if item.date else ""
            elif col in ("from", "sender"):
                value = item.sender
            elif col == "email":
                value = item.sender_email
            elif col == "subject":
                value = item.subject
            elif col == "body":
                value = item.body or ""
            elif col == "mailbox":
                value = item.mailbox or ""
            elif col == "blocked":
                value = "yes" if blocked else "no"
            else:
                value = getattr(item, col, "") or ""
            if isinstance(value, str):
                # Normalize whitespace/newlines for compact table display
                value = re.sub(r"\s+", " ", value).strip()
            row.append(value)
        rows.append(row)

    # Compute column widths
    widths = [len(h) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = min(max(widths[i], len(cell)), 120)

    # Build table string
    def fmt_row(vals: List[str]) -> str:
        return "  ".join(v[:widths[i]].ljust(widths[i]) for i, v in enumerate(vals))

    lines = [fmt_row(header), fmt_row(["-" * w for w in widths])]
    lines.extend(fmt_row(r) for r in rows)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Query Apple Mail for messages.")
    filters = parser.add_argument_group("filters")
    output = parser.add_argument_group("output")

    parser.add_argument("--limit", type=int, default=200, help="Max messages to pull from Mail (default 200)")
    parser.add_argument("--all", action="store_true", help="Include read messages (default is unread only)")
    parser.add_argument("--body", action="store_true", help="Include full plain text body (may be slow)")
    parser.add_argument("--body-limit", type=int, default=None, help="Truncate body to N characters (applies to table/JSON)")

    filters.add_argument("--today", action="store_true", help="Only messages from today")
    filters.add_argument("--since", type=str, help="Only messages on/after YYYY-MM-DD")
    filters.add_argument("--until", type=str, help="Only messages on/before YYYY-MM-DD")
    filters.add_argument("--subject-contains", type=str, help="Filter by subject substring (case-insensitive)")
    filters.add_argument("--from-contains", type=str, help="Filter by sender substring or email (case-insensitive)")
    filters.add_argument("--blocked-senders", type=str, help="Path to newline-separated blocked senders/domains")
    filters.add_argument("--include-blocked", action="store_true", help="Include blocked senders in output, mark with blocked=yes")

    output.add_argument("--json", action="store_true", help="Output raw JSON records")
    output.add_argument("--count", action="store_true", help="Only print count")
    output.add_argument(
        "--columns",
        type=str,
        default="date,from,subject",
        help="Comma-separated columns for table output (date,from,email,subject,mailbox,blocked)",
    )

    args = parser.parse_args(argv)

    # Parse dates
    since_d: Optional[date] = None
    until_d: Optional[date] = None
    if args.since:
        since_d = datetime.strptime(args.since, "%Y-%m-%d").date()
    if args.until:
        until_d = datetime.strptime(args.until, "%Y-%m-%d").date()

    unread_only = not args.all
    raw = run_jxa(unread_only=unread_only, limit=args.limit, include_body=args.body)
    items = coerce_items(raw)

    blocklist = load_blocklist(args.blocked_senders)
    filtered = apply_filters(
        items,
        today_only=args.today,
        since_date=since_d,
        until_date=until_d,
        subject_contains=args.subject_contains,
        from_contains=args.from_contains,
        blocklist=blocklist,
        include_blocked=args.include_blocked,
    )

    if args.count:
        print(len(filtered))
        return 0

    # Optional truncation
    if args.body_limit is not None:
        lim = max(0, int(args.body_limit))
        for it, _blocked in filtered:
            if it.body is not None and len(it.body) > lim:
                it.body = it.body[:lim]

    if args.json:
        # Emit normalized JSON with fields we control
        serializable = [
            {
                "id": it.id,
                "subject": it.subject,
                "sender": it.sender,
                "sender_email": it.sender_email,
                "date": it.date.isoformat() if it.date else None,
                "read": it.read,
                "flagged": it.flagged,
                "mailbox": it.mailbox,
                "body": it.body,
                "blocked": blocked,
            }
            for (it, blocked) in filtered
        ]
        print(json.dumps(serializable, indent=2))
        return 0

    columns = [c.strip().lower() for c in args.columns.split(",") if c.strip()]
    table = format_table(filtered, columns)
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


