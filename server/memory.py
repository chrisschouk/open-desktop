"""
SQLite session and message store for OpenWorker chat.
Sessions (chats) belong to Workers when worker_id is set.
"""
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA_DIR

DB_PATH = DATA_DIR / "sessions.db"

MESSAGE_KINDS = ("text", "event", "widget", "artifact_ref", "computer_status")


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
        if "worker_id" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN worker_id TEXT")
        msg_cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
        if "kind" not in msg_cols:
            conn.execute("ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'text'")


def create_session(
    persona_id: str = "openworker",
    channel_key: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> dict:
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    now = time.time()
    # Lazy default worker binding without circular import at module load
    if worker_id is None:
        try:
            from .workers import DEFAULT_WORKER_ID, ensure_default_worker
            ensure_default_worker()
            worker_id = DEFAULT_WORKER_ID
        except Exception:
            worker_id = "wrk_openworker"
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sessions
               (id, persona_id, channel_key, status, worker_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, persona_id, channel_key, "idle", worker_id, now, now),
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


def try_acquire_session(session_id: str) -> bool:
    """Atomically move session idle → working. Returns False if already busy."""
    now = time.time()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE sessions SET status = 'working', updated_at = ? WHERE id = ? AND status = 'idle'",
            (now, session_id),
        )
        return cur.rowcount == 1


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
    kind: str = "text",
) -> dict:
    if kind not in MESSAGE_KINDS:
        kind = "text"
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = time.time()
    meta = dict(metadata) if metadata else {}
    meta.setdefault("kind", kind)
    meta_json = json.dumps(meta)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO messages
               (id, session_id, role, content, metadata, kind, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, session_id, role, content, meta_json, kind, now),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return {
        "id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "kind": kind,
        "metadata": meta,
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
        if not d.get("kind") and isinstance(d.get("metadata"), dict):
            d["kind"] = d["metadata"].get("kind", "text")
        elif not d.get("kind"):
            d["kind"] = "text"
        result.append(d)
    return result


def list_sessions(limit: int = 20, worker_id: Optional[str] = None) -> List[dict]:
    with _connect() as conn:
        if worker_id:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE worker_id = ? ORDER BY updated_at DESC LIMIT ?",
                (worker_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]
