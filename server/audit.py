"""
Tamper-evident audit log for OpenWorker agent actions (Buzz buzz-audit inspired).
"""
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

from .config import DATA_DIR

AUDIT_DB = DATA_DIR / "audit.db"
GENESIS_HASH = "0" * 64


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(AUDIT_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_audit():
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
        """)


def _last_hash() -> str:
    with _connect() as conn:
        row = conn.execute(
            "SELECT entry_hash FROM audit_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return row["entry_hash"] if row else GENESIS_HASH


def append_audit(event_type: str, payload: Dict[str, Any]) -> dict:
    entry_id = f"aud_{uuid.uuid4().hex[:12]}"
    now = time.time()
    prev_hash = _last_hash()
    body = json.dumps({"id": entry_id, "event_type": event_type, "payload": payload, "prev_hash": prev_hash, "created_at": now}, sort_keys=True)
    entry_hash = hashlib.sha256(body.encode()).hexdigest()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (id, event_type, payload, prev_hash, entry_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (entry_id, event_type, json.dumps(payload), prev_hash, entry_hash, now),
        )
    return {"id": entry_id, "entry_hash": entry_hash, "prev_hash": prev_hash}


def list_audit(limit: int = 50) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def verify_chain(limit: int = 1000) -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    expected_prev = GENESIS_HASH
    for row in rows:
        if row["prev_hash"] != expected_prev:
            return {"valid": False, "broken_at": row["id"]}
        body = json.dumps({
            "id": row["id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]),
            "prev_hash": row["prev_hash"],
            "created_at": row["created_at"],
        }, sort_keys=True)
        if hashlib.sha256(body.encode()).hexdigest() != row["entry_hash"]:
            return {"valid": False, "broken_at": row["id"]}
        expected_prev = row["entry_hash"]
    return {"valid": True, "entries": len(rows)}
