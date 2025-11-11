import os
import sqlite3
import tempfile
import datetime as dt
import subprocess
import unittest


APPLE_EPOCH_UNIX = 978307200


def _apple_ns_from_datetime(ts: dt.datetime) -> int:
    # Messages stores nanoseconds since 2001-01-01
    return int((ts.timestamp() - APPLE_EPOCH_UNIX) * 1_000_000_000)


def _create_fake_messages_db(path: str) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    # Minimal schema needed by our queries
    cur.execute("CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT, uncanonicalized_id TEXT)")
    cur.execute("CREATE TABLE message (ROWID INTEGER PRIMARY KEY, handle_id INTEGER, text TEXT, date INTEGER)")
    cur.execute("CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT)")
    cur.execute("CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER)")
    # Sample rows
    now = dt.datetime.now()
    mdate = _apple_ns_from_datetime(now)
    cur.execute("INSERT INTO handle (ROWID, id, uncanonicalized_id) VALUES (1, '+15551234567', '+15551234567')")
    cur.execute("INSERT INTO chat (ROWID, chat_identifier) VALUES (1, 'iMessage;+15551234567')")
    cur.execute(
        "INSERT INTO message (ROWID, handle_id, text, date) VALUES (1, 1, ?, ?)",
        ("todo: Sign up for Foam Village shift", mdate),
    )
    cur.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 1)")
    conn.commit()
    conn.close()


class TestImessageIngest(unittest.TestCase):
    def test_ingest_parses_todo_and_emits_tags(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "chat.db")
            _create_fake_messages_db(db_path)
            cmd = [
                "python3",
                os.path.join(os.getcwd(), "scripts/imessage_ingest.py"),
                "--db",
                db_path,
                "--since",
                "today",
                "--dry-run",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            out = result.stdout.strip()
            self.assertIn("@reminder(message=\"Sign up for Foam Village shift\"", out)


if __name__ == "__main__":
    unittest.main()

