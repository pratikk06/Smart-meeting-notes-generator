"""
Day 4 scope: persist meetings to SQLite so users can browse past meetings
instead of losing everything when the Streamlit session ends.

Design notes:
- SQLite over a full DB server: this is a single-user local app, so a
  server-based DB (Postgres/MySQL) would be unnecessary operational overhead.
  SQLite needs zero setup and the whole DB is just one file.
- We store notes/transcript as JSON text in a column rather than normalizing
  into separate tables (e.g. a decisions table, an action_items table).
  For a read-mostly, no-cross-meeting-query use case, that normalization
  buys nothing but adds joins — so we keep it simple.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.config import DATA_DIR

DB_PATH = DATA_DIR / "meetings.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the meetings table if it doesn't exist yet. Safe to call every startup."""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            original_filename TEXT,
            transcript_text TEXT,
            notes_json TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_meeting(title: str, notes: dict, transcript_text: str = "",
                  original_filename: str = "") -> int:
    """Save a meeting's notes (+ optional transcript) to history. Returns the new row id."""
    conn = _get_connection()
    cursor = conn.execute(
        """INSERT INTO meetings (title, created_at, original_filename, transcript_text, notes_json)
           VALUES (?, ?, ?, ?, ?)""",
        (
            title,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            original_filename,
            transcript_text,
            json.dumps(notes),
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def list_meetings() -> list:
    """Return all saved meetings, most recent first, WITHOUT full transcript (for a lightweight list view)."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT id, title, created_at, original_filename FROM meetings ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_meeting(meeting_id: int) -> dict:
    """Fetch one meeting's full details (including transcript + parsed notes) by id."""
    conn = _get_connection()
    row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    result["notes"] = json.loads(result["notes_json"])
    return result


def delete_meeting(meeting_id: int) -> None:
    conn = _get_connection()
    conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()


# Ensure table exists as soon as this module is imported
init_db()