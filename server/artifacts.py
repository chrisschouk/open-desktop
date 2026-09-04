"""
Artifacts — durable Worker outputs (files, reports, screenshot refs).
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Optional

from .config import DATA_DIR
from . import memory

ARTIFACTS_DIR = DATA_DIR / "artifacts"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(memory.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_artifacts():
    memory.init_db()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                session_id TEXT,
                kind TEXT NOT NULL DEFAULT 'file',
                title TEXT NOT NULL,
                path TEXT,
                mime_type TEXT,
                meta_json TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_artifacts_worker ON artifacts(worker_id);
        """)


def create_artifact(
    worker_id: str,
    title: str,
    kind: str = "file",
    session_id: Optional[str] = None,
    content: Optional[bytes] = None,
    text: Optional[str] = None,
    mime_type: Optional[str] = None,
    meta: Optional[dict] = None,
    source_path: Optional[str] = None,
) -> dict:
    art_id = f"art_{uuid.uuid4().hex[:12]}"
    now = time.time()
    dest: Optional[str] = None

    worker_dir = ARTIFACTS_DIR / worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)

    if content is not None:
        ext = ".bin"
        if mime_type == "image/jpeg":
            ext = ".jpg"
        elif mime_type == "image/png":
            ext = ".png"
        elif mime_type == "text/markdown" or kind == "report":
            ext = ".md"
        elif mime_type == "text/plain":
            ext = ".txt"
        elif mime_type == "application/json":
            ext = ".json"
        dest_path = worker_dir / f"{art_id}{ext}"
        dest_path.write_bytes(content)
        dest = str(dest_path)
    elif text is not None:
        dest_path = worker_dir / f"{art_id}.md"
        dest_path.write_text(text, encoding="utf-8")
        dest = str(dest_path)
        mime_type = mime_type or "text/markdown"
    elif source_path:
        src = Path(source_path)
        if src.exists():
            dest_path = worker_dir / f"{art_id}_{src.name}"
            shutil.copy2(src, dest_path)
            dest = str(dest_path)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO artifacts
               (id, worker_id, session_id, kind, title, path, mime_type, meta_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                art_id,
                worker_id,
                session_id,
                kind,
                title,
                dest,
                mime_type,
                json.dumps(meta or {}),
                now,
            ),
        )
    return get_artifact(art_id)


def get_artifact(artifact_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    meta = d.pop("meta_json", None)
    d["meta"] = json.loads(meta) if meta else {}
    return d


def list_artifacts(worker_id: Optional[str] = None, limit: int = 50) -> List[dict]:
    with _connect() as conn:
        if worker_id:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE worker_id = ? ORDER BY created_at DESC LIMIT ?",
                (worker_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM artifacts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        meta = d.pop("meta_json", None)
        d["meta"] = json.loads(meta) if meta else {}
        result.append(d)
    return result


def artifact_ref_payload(artifact: dict) -> dict:
    return {
        "artifact_id": artifact["id"],
        "title": artifact["title"],
        "kind": artifact["kind"],
        "mime_type": artifact.get("mime_type"),
        "worker_id": artifact["worker_id"],
    }
