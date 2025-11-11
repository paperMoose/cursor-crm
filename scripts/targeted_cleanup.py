#!/usr/bin/env python3
"""
Targeted email cleanup: Delete product updates, event invites, marketing/promos.
Keep Parlance Labs and other important senders.

Usage:
  python3 scripts/email_cli.py --limit 500 --json | python3 scripts/targeted_cleanup.py --dry-run
  python3 scripts/email_cli.py --limit 500 --json | python3 scripts/targeted_cleanup.py --delete --yes
"""

import argparse
import json
import subprocess
import sys
from typing import List, Dict, Set


# Domains/senders to DELETE
DELETE_DOMAINS = {
    'posthog.com', 'clerk.com', 'fabric.so', 'granola.so', 'fathom.video',
    'cartesia.ai', 'linear.app', 'featherso.com', 'shack15.com', 'canva.com',
    'vailresortsmail.com', 'metamail.com', 'postman.com', 'venmo.com',
    'beehiiv.com', 'luma-mail.com', 'user.luma-mail.com', 'calendar.luma-mail.com'
}

DELETE_SENDER_PATTERNS = {
    'no-reply@', 'noreply@', 'notifications@', 'marketing@', 'update@',
    'concierge@', 'memberships@', 'hey@posthog.com', 'joe@posthog.com',
    'care@fabric.so', 'tibo@mail.featherso.com', 'kismat@shack15.com'
}

DELETE_SUBJECT_PATTERNS = {
    'you are invited to', 'you\'re invited', 'calendar updated', 'new login to',
    'security alert', 'stay connected', 'welcome to', 'unlock offers',
    'soak up summer', 'summer vibes', 'escape ladder', 'struggling to choose'
}

# Preserve these (case-insensitive)
PRESERVE_DOMAINS = {
    'parlance-labs@courses.maven.com', 'maven.com'  # Keep Parlance Labs
}

PRESERVE_SENDERS = {
    'parlance labs', 'parlance-labs'
}


def should_delete(email: Dict) -> bool:
    sender_email = (email.get('sender_email') or '').lower()
    sender = (email.get('sender') or '').lower()
    subject = (email.get('subject') or '').lower()
    
    # Preserve Parlance Labs
    if any(preserve in sender_email for preserve in PRESERVE_DOMAINS):
        return False
    if any(preserve in sender for preserve in PRESERVE_SENDERS):
        return False
    
    # Check delete criteria
    domain = sender_email.split('@')[-1] if '@' in sender_email else ''
    
    if domain in DELETE_DOMAINS:
        return True
    
    if any(pattern in sender_email for pattern in DELETE_SENDER_PATTERNS):
        return True
        
    if any(pattern in subject for pattern in DELETE_SUBJECT_PATTERNS):
        return True
    
    return False


def jxa_delete_by_ids(ids: List[int]) -> None:
    if not ids:
        return
    
    # Build JS array
    id_list = ','.join(str(i) for i in ids)
    js = f"""
const Mail = Application('Mail');
const inbox = Mail.inbox;
var idMap = Object.create(null);
[{id_list}].forEach(function(v) {{ idMap[v] = true; }});
var msgs = inbox.messages();
var deleted = 0;
for (var i = 0; i < msgs.length; i++) {{
  var m = msgs[i];
  try {{
    var mid = m.id();
    if (idMap[mid]) {{
      Mail.delete(m);
      deleted++;
    }}
  }} catch (e) {{}}
}}
deleted;
"""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", js], 
        capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        print(f"Deleted {result.stdout.strip()} messages via Apple Mail")
    else:
        print(f"Error deleting: {result.stderr}")


def main():
    parser = argparse.ArgumentParser(description='Targeted email cleanup')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted')
    parser.add_argument('--delete', action='store_true', help='Actually delete messages')
    parser.add_argument('--yes', action='store_true', help='Confirm deletion')
    
    args = parser.parse_args()
    
    if args.delete and not args.yes:
        print("--delete requires --yes for confirmation")
        return 1
    
    # Read emails from stdin
    raw = sys.stdin.read()
    emails = json.loads(raw)
    
    to_delete = []
    to_keep = []
    
    for email in emails:
        if should_delete(email):
            to_delete.append(email)
        else:
            to_keep.append(email)
    
    print(f"Total emails: {len(emails)}")
    print(f"To delete: {len(to_delete)}")
    print(f"To keep: {len(to_keep)}")
    
    if args.dry_run or not args.delete:
        print("\nSample emails to DELETE:")
        for email in to_delete[:10]:
            print(f"  - {email.get('sender', 'Unknown')} | {email.get('subject', 'No subject')}")
        
        print("\nSample emails to KEEP:")
        for email in to_keep[:10]:
            print(f"  + {email.get('sender', 'Unknown')} | {email.get('subject', 'No subject')}")
    
    if args.delete and args.yes:
        delete_ids = [email.get('id') for email in to_delete if email.get('id')]
        if delete_ids:
            print(f"Deleting {len(delete_ids)} messages...")
            jxa_delete_by_ids(delete_ids)
        else:
            print("No valid message IDs to delete")
    
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

