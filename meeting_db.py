"""SQLite persistence for structured meeting intelligence."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("meetings.db")


def init_db() -> None:
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                transcript TEXT NOT NULL,
                intelligence_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
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


def save_meeting(filename: str, transcript: str, intelligence: dict[str, Any]) -> int:
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.execute(
            "INSERT INTO meetings (filename, transcript, intelligence_json, created_at) VALUES (?, ?, ?, ?)",
            (filename, transcript, json.dumps(intelligence), datetime.now().isoformat(timespec="seconds")),
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


def recent_meetings(limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, filename, intelligence_json, created_at FROM meetings ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {"id": row["id"], "filename": row["filename"], "created_at": row["created_at"], "intelligence": json.loads(row["intelligence_json"])}
            for row in rows
        ]
    finally:
        connection.close()
