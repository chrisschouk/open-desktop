"""
SQLite session and message store for OpenWorker chat.
"""
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA_DIR

DB_PATH = DATA_DIR / "sessions.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                persona_id TEXT NOT NULL DEFAULT 'openworker',
                channel_key TEXT,
                status TEXT NOT NULL DEFAULT 'idle',
                machine_id TEXT,
                playbook_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS channel_sessions (
                channel_key TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "channel_key" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN channel_key TEXT")


def create_session(persona_id: str = "openworker", channel_key: Optional[str] = None) -> dict:
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, persona_id, channel_key, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, persona_id, channel_key, "idle", now, now),
        )
        if channel_key:
            conn.execute(
                "INSERT OR REPLACE INTO channel_sessions (channel_key, session_id, updated_at) VALUES (?, ?, ?)",
                (channel_key, session_id, now),
            )
    return get_session(session_id)


def get_channel_session(channel_key: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT session_id FROM channel_sessions WHERE channel_key = ?",
            (channel_key,),
        ).fetchone()
    return row["session_id"] if row else None


def get_session(session_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return dict(row)


def update_session(session_id: str, **fields):
    fields["updated_at"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [session_id]
    with _connect() as conn:
        conn.execute(f"UPDATE sessions SET {sets} WHERE id = ?", vals)


def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> dict:
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = time.time()
    meta_json = json.dumps(metadata) if metadata else None
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, meta_json, now),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return {
        "id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "metadata": metadata,
        "created_at": now,
    }


def get_messages(session_id: str, limit: int = 50) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM (
                 SELECT * FROM messages WHERE session_id = ?
                 ORDER BY created_at DESC LIMIT ?
               ) ORDER BY created_at ASC""",
            (session_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if d.get("metadata"):
            d["metadata"] = json.loads(d["metadata"])
        result.append(d)
    return result


def list_sessions(limit: int = 20) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
