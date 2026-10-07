"""
Group chats — shared project threads with per-Worker memory retained.
Soft limit: 6 Workers per group (DESIGN_PRIMITIVES.md).
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from typing import List, Optional

from . import memory
from .workers import get_worker, MAX_WORKERS

MAX_WORKERS_PER_GROUP = 6


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(memory.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_groups():
    memory.init_db()
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS group_chats (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                session_id TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS group_chat_members (
                group_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                PRIMARY KEY (group_id, worker_id)
            );
        """)


def create_group_chat(name: str, worker_ids: List[str], coordinator_id: Optional[str] = None) -> dict:
    if len(worker_ids) > MAX_WORKERS_PER_GROUP:
        raise ValueError(f"Max {MAX_WORKERS_PER_GROUP} Workers per group chat")
    for wid in worker_ids:
        if not get_worker(wid):
            raise ValueError(f"Worker not found: {wid}")
    # Session owned by coordinator or first worker
    owner = coordinator_id or worker_ids[0]
    session = memory.create_session(worker_id=owner)
    gid = f"grp_{uuid.uuid4().hex[:10]}"
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO group_chats (id, name, session_id, created_at) VALUES (?, ?, ?, ?)",
            (gid, name, session["id"], now),
        )
        for wid in worker_ids:
            role = "coordinator" if wid == owner else "member"
            conn.execute(
                "INSERT INTO group_chat_members (group_id, worker_id, role) VALUES (?, ?, ?)",
                (gid, wid, role),
            )
    memory.add_message(
        session["id"],
        "assistant",
        f"Group **{name}** opened with {len(worker_ids)} Workers. "
        f"Shared context lives here; each Worker keeps their own memory.",
        {"group_id": gid, "intent": "group_created"},
        kind="event",
    )
    return get_group(gid)


def get_group(group_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM group_chats WHERE id = ?", (group_id,)).fetchone()
        if not row:
            return None
        members = conn.execute(
            "SELECT * FROM group_chat_members WHERE group_id = ?",
            (group_id,),
        ).fetchall()
    d = dict(row)
    d["members"] = [dict(m) for m in members]
    return d


def list_groups(limit: int = 20) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM group_chats ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [get_group(r["id"]) for r in rows]
