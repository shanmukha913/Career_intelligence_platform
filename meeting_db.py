"""SQLite persistence for structured meeting intelligence."""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("MEETING_DB_PATH", "meetings.db"))


def init_db() -> None:
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash BLOB NOT NULL,
                password_salt BLOB NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash BLOB PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                transcript TEXT NOT NULL,
                intelligence_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                owner_id INTEGER,
                source TEXT NOT NULL DEFAULT 'upload',
                external_id TEXT,
                FOREIGN KEY(owner_id) REFERENCES users(id)
            )"""
        )
        meeting_columns = {row[1] for row in connection.execute("PRAGMA table_info(meetings)")}
        if "owner_id" not in meeting_columns:
            connection.execute("ALTER TABLE meetings ADD COLUMN owner_id INTEGER")
        if "source" not in meeting_columns:
            connection.execute("ALTER TABLE meetings ADD COLUMN source TEXT NOT NULL DEFAULT 'upload'")
        if "external_id" not in meeting_columns:
            connection.execute("ALTER TABLE meetings ADD COLUMN external_id TEXT")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_meetings_external_source "
            "ON meetings(owner_id, source, external_id) WHERE external_id IS NOT NULL"
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                responsibilities TEXT NOT NULL,
                UNIQUE(meeting_id, name),
                FOREIGN KEY(meeting_id) REFERENCES meetings(id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                assignee TEXT NOT NULL,
                deadline TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(meeting_id, task, assignee),
                FOREIGN KEY(meeting_id) REFERENCES meetings(id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS deadlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                due_date TEXT NOT NULL,
                UNIQUE(meeting_id, item, due_date),
                FOREIGN KEY(meeting_id) REFERENCES meetings(id)
            )"""
        )
        connection.commit()
    finally:
        connection.close()


def save_meeting(
    filename: str,
    transcript: str,
    intelligence: dict[str, Any],
    owner_id: int | None = None,
    source: str = "upload",
    external_id: str | None = None,
) -> int:
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        if external_id:
            existing = connection.execute(
                "SELECT id FROM meetings WHERE owner_id IS ? AND source = ? AND external_id = ?",
                (owner_id, source, external_id),
            ).fetchone()
            if existing:
                return int(existing[0])
        cursor = connection.execute(
            "INSERT INTO meetings (filename, transcript, intelligence_json, created_at, owner_id, source, external_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (filename, transcript, json.dumps(intelligence), datetime.now().isoformat(timespec="seconds"), owner_id, source, external_id),
        )
        meeting_id = int(cursor.lastrowid)
        for participant in intelligence.get("participants", []):
            connection.execute(
                "INSERT OR IGNORE INTO participants (meeting_id, name, responsibilities) VALUES (?, ?, ?)",
                (meeting_id, participant["name"], participant["responsibilities"]),
            )
        for action in intelligence.get("action_items", []):
            connection.execute(
                "INSERT OR IGNORE INTO action_items (meeting_id, task, assignee, deadline, priority, status) VALUES (?, ?, ?, ?, ?, ?)",
                (meeting_id, action["task"], action["assignee"], action["deadline"], action["priority"], action["status"]),
            )
        for deadline in intelligence.get("deadlines", []):
            connection.execute(
                "INSERT OR IGNORE INTO deadlines (meeting_id, item, due_date) VALUES (?, ?, ?)",
                (meeting_id, deadline["item"], deadline["due_date"]),
            )
        connection.commit()
        return meeting_id
    finally:
        connection.close()


def recent_meetings(limit: int = 10, owner_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.row_factory = sqlite3.Row
        if owner_id is None:
            rows = connection.execute(
                "SELECT id, filename, intelligence_json, created_at FROM meetings ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT id, filename, intelligence_json, created_at FROM meetings WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        return [
            {"id": row["id"], "filename": row["filename"], "created_at": row["created_at"], "intelligence": json.loads(row["intelligence_json"])}
            for row in rows
        ]
    finally:
        connection.close()


def meeting_analytics(owner_id: int) -> dict[str, Any]:
    """Return meeting totals and eight-week activity for one account only."""
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        rows = connection.execute(
            "SELECT transcript, intelligence_json, created_at FROM meetings WHERE owner_id = ?",
            (owner_id,),
        ).fetchall()
    finally:
        connection.close()

    today = datetime.now().date()
    current_week = today - timedelta(days=today.weekday())
    weeks = [current_week - timedelta(weeks=offset) for offset in reversed(range(8))]
    weekly_counts = {week.isoformat(): 0 for week in weeks}
    total_words = 0
    action_items = 0
    deadlines = 0
    participants = set()

    for transcript, intelligence_json, created_at in rows:
        total_words += len(transcript.split())
        intelligence = json.loads(intelligence_json)
        action_items += len(intelligence.get("action_items", []))
        deadlines += len(intelligence.get("deadlines", []))
        participants.update(
            participant.get("name", "").strip().casefold()
            for participant in intelligence.get("participants", [])
            if participant.get("name", "").strip()
        )
        try:
            meeting_date = datetime.fromisoformat(created_at).date()
            meeting_week = meeting_date - timedelta(days=meeting_date.weekday())
            if meeting_week.isoformat() in weekly_counts:
                weekly_counts[meeting_week.isoformat()] += 1
        except (TypeError, ValueError):
            continue

    return {
        "meetings": len(rows),
        "transcript_words": total_words,
        "action_items": action_items,
        "deadlines": deadlines,
        "participants": len(participants),
        "weekly_activity": weekly_counts,
    }


def get_meeting(meeting_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
    """Retrieve one meeting and its structured intelligence by ID."""
    init_db()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        if owner_id is None:
            row = connection.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM meetings WHERE id = ? AND owner_id = ?", (meeting_id, owner_id)
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "filename": row["filename"], "transcript": row["transcript"], "created_at": row["created_at"], "intelligence": json.loads(row["intelligence_json"])}
    finally:
        connection.close()


def get_external_meeting(owner_id: int, source: str, external_id: str) -> int | None:
    """Return the local meeting ID for an already imported provider recording."""
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        row = connection.execute(
            "SELECT id FROM meetings WHERE owner_id = ? AND source = ? AND external_id = ?",
            (owner_id, source, external_id),
        ).fetchone()
        return int(row[0]) if row else None
    finally:
        connection.close()
