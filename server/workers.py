"""
Workers — persistent OpenWorker agents (identity, presence, affinity, memory).

Product language: a Worker is the durable agent; chats (sessions) belong to Workers.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

from .config import DATA_DIR, PERSONAS_DIR
from . import memory

MAX_WORKERS = 50
DEFAULT_WORKER_ID = "wrk_openworker"
PRESENCE_STATES = ("idle", "thinking", "working", "waiting", "blocked", "done")

# In-memory current action (action stream); not persisted
_current_actions: Dict[str, str] = {}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(memory.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_workers():
    """Ensure workers table exists and default Worker is seeded."""
    memory.init_db()
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT 'default',
                role TEXT NOT NULL DEFAULT 'general',
                persona_ref TEXT NOT NULL DEFAULT 'openworker',
                memory_json TEXT,
                preferred_machine_id TEXT,
                presence TEXT NOT NULL DEFAULT 'idle',
                current_action TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_workers_updated ON workers(updated_at);
        """)
    ensure_starter_roster()


def ensure_default_worker() -> dict:
    existing = get_worker(DEFAULT_WORKER_ID)
    if existing:
        return existing
    persona = _persona_meta("openworker")
    return create_worker(
        name=persona.get("name") or "OpenWorker",
        avatar="openworker",
        role=persona.get("tagline") or "Your open source desktop agent",
        persona_ref="openworker",
        worker_id=DEFAULT_WORKER_ID,
    )


def ensure_starter_roster():
    """Seed default + optional specialist Workers for multi-Worker demos."""
    ensure_default_worker()
    if not get_worker("wrk_research"):
        create_worker(
            name="Research Worker",
            avatar="research",
            role="Deep web research specialist",
            persona_ref="research",
            worker_id="wrk_research",
        )
    if not get_worker("wrk_coordinator"):
        create_worker(
            name="Chief of Staff",
            avatar="ops",
            role="Coordinates specialists; routes work",
            persona_ref="openworker",
            worker_id="wrk_coordinator",
        )


def _persona_meta(persona_id: str) -> dict:
    path = PERSONAS_DIR / f"{persona_id}.yaml"
    if not path.exists():
        return {"id": persona_id, "name": persona_id}
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"id": persona_id, "name": persona_id}


def _row_to_worker(row: sqlite3.Row) -> dict:
    d = dict(row)
    mem = d.pop("memory_json", None)
    d["memory"] = json.loads(mem) if mem else {}
    # Overlay live current_action if set
    live = _current_actions.get(d["id"])
    if live is not None:
        d["current_action"] = live
    return d


def create_worker(
    name: str,
    avatar: str = "default",
    role: str = "general",
    persona_ref: str = "openworker",
    worker_id: Optional[str] = None,
    memory_data: Optional[dict] = None,
) -> dict:
    workers = list_workers()
    if len(workers) >= MAX_WORKERS and not worker_id:
        raise ValueError(f"Worker limit reached ({MAX_WORKERS})")
    wid = worker_id or f"wrk_{uuid.uuid4().hex[:10]}"
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO workers
               (id, name, avatar, role, persona_ref, memory_json, presence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'idle', ?, ?)""",
            (
                wid,
                name,
                avatar,
                role,
                persona_ref,
                json.dumps(memory_data or {}),
                now,
                now,
            ),
        )
    return get_worker(wid)


def get_worker(worker_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
    return _row_to_worker(row) if row else None


def list_workers(limit: int = 50) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM workers ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_worker(r) for r in rows]


def update_worker(worker_id: str, **fields) -> Optional[dict]:
    if "memory" in fields:
        fields["memory_json"] = json.dumps(fields.pop("memory") or {})
    allowed = {
        "name", "avatar", "role", "persona_ref", "memory_json",
        "preferred_machine_id", "presence", "current_action",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_worker(worker_id)
    if "presence" in updates and updates["presence"] not in PRESENCE_STATES:
        raise ValueError(f"Invalid presence: {updates['presence']}")
    updates["updated_at"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [worker_id]
    with _connect() as conn:
        conn.execute(f"UPDATE workers SET {sets} WHERE id = ?", vals)
    if "current_action" in updates:
        if updates["current_action"]:
            _current_actions[worker_id] = updates["current_action"]
        else:
            _current_actions.pop(worker_id, None)
    return get_worker(worker_id)


def set_presence(
    worker_id: str,
    presence: str,
    current_action: Optional[str] = None,
) -> Optional[dict]:
    if presence not in PRESENCE_STATES:
        raise ValueError(f"Invalid presence: {presence}")
    fields: Dict[str, Any] = {"presence": presence}
    if current_action is not None:
        fields["current_action"] = current_action
        if current_action:
            _current_actions[worker_id] = current_action
        else:
            _current_actions.pop(worker_id, None)
    return update_worker(worker_id, **fields)


def set_current_action(worker_id: str, action: Optional[str]):
    if action:
        _current_actions[worker_id] = action
        update_worker(worker_id, current_action=action)
    else:
        _current_actions.pop(worker_id, None)
        update_worker(worker_id, current_action=None)


def presence_from_session_status(status: str, tier: Optional[str] = None) -> str:
    """Map session FSM + tier to Worker presence."""
    if status == "error":
        return "blocked"
    if status == "working":
        if tier in ("T0", "T1", "chat", "browser"):
            return "thinking"
        return "working"
    if status == "idle":
        return "idle"
    return "idle"


def sync_presence_from_session(session_id: str, tier: Optional[str] = None, action: Optional[str] = None):
    session = memory.get_session(session_id)
    if not session:
        return
    worker_id = session.get("worker_id") or DEFAULT_WORKER_ID
    presence = presence_from_session_status(session.get("status") or "idle", tier)
    set_presence(worker_id, presence, current_action=action)


def create_chat_for_worker(
    worker_id: str,
    channel_key: Optional[str] = None,
) -> dict:
    worker = get_worker(worker_id)
    if not worker:
        raise ValueError(f"Worker not found: {worker_id}")
    return memory.create_session(
        persona_id=worker.get("persona_ref") or "openworker",
        channel_key=channel_key,
        worker_id=worker_id,
    )


def list_worker_chats(worker_id: str, limit: int = 20) -> List[dict]:
    return memory.list_sessions(limit=limit, worker_id=worker_id)


def roster_summary() -> List[dict]:
    """Compact roster for orient / UI."""
    out = []
    for w in list_workers():
        out.append({
            "id": w["id"],
            "name": w["name"],
            "avatar": w["avatar"],
            "role": w["role"],
            "presence": w["presence"],
            "current_action": w.get("current_action"),
            "preferred_machine_id": w.get("preferred_machine_id"),
        })
    return out
