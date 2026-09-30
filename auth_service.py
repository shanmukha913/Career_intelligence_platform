"""Local account registration and revocable session tokens."""

import hashlib
import hmac
import secrets
import sqlite3
import time

import meeting_db

PASSWORD_ITERATIONS = 260_000
SESSION_SECONDS = 60 * 60 * 24 * 30
MIN_PASSWORD_LENGTH = 12


def init_auth_db() -> None:
    meeting_db.init_db()


def register_user(email: str, password: str) -> int:
    normalized_email = (email or "").strip().lower()
    if "@" not in normalized_email or len(normalized_email) > 254:
        raise ValueError("Enter a valid email address")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must contain at least {MIN_PASSWORD_LENGTH} characters")

    init_auth_db()
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    connection = sqlite3.connect(meeting_db.DB_PATH)
    try:
        cursor = connection.execute(
            "INSERT INTO users (email, password_hash, password_salt, created_at) VALUES (?, ?, ?, datetime('now'))",
            (normalized_email, password_hash, salt),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.IntegrityError as error:
        raise ValueError("An account with this email already exists") from error
    finally:
        connection.close()


def authenticate_user(email: str, password: str) -> str:
    init_auth_db()
    connection = sqlite3.connect(meeting_db.DB_PATH)
    try:
        row = connection.execute(
            "SELECT id, password_hash, password_salt FROM users WHERE email = ?",
            ((email or "").strip().lower(),),
        ).fetchone()
        if row is None or not hmac.compare_digest(_hash_password(password or "", row[2]), row[1]):
            raise ValueError("Invalid email or password")
        token = secrets.token_urlsafe(32)
        connection.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_hash_token(token), row[0], int(time.time()) + SESSION_SECONDS),
        )
        connection.commit()
        return token
    finally:
        connection.close()


def resolve_session(token: str) -> int | None:
    if not token:
        return None
    init_auth_db()
    connection = sqlite3.connect(meeting_db.DB_PATH)
    try:
        row = connection.execute(
            "SELECT user_id, expires_at FROM auth_sessions WHERE token_hash = ?",
            (_hash_token(token),),
        ).fetchone()
        if row is None:
            return None
        if row[1] <= int(time.time()):
            connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_hash_token(token),))
            connection.commit()
            return None
        return int(row[0])
    finally:
        connection.close()


def revoke_session(token: str) -> None:
    if not token:
        return
    init_auth_db()
    connection = sqlite3.connect(meeting_db.DB_PATH)
    try:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_hash_token(token),))
        connection.commit()
    finally:
        connection.close()


def user_email(user_id: int) -> str | None:
    init_auth_db()
    connection = sqlite3.connect(meeting_db.DB_PATH)
    try:
        row = connection.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def _hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
