"""
Routines — Worker-owned standing work (schedules that land in Worker transcripts).

Wraps the schedules DB with worker_id, pause/resume, and transcript events.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from typing import List, Optional

from .config import DATA_DIR
from . import memory
from .artifacts import create_artifact, artifact_ref_payload
from .playbook_executor import run_playbook
from .sandbox_factory import sandbox_manager
from .agent_runner import agent_runner

SCHEDULE_DB = DATA_DIR / "schedules.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(SCHEDULE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_routines():
    SCHEDULE_DB.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                cron_expr TEXT NOT NULL,
                playbook_id TEXT,
                prompt TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at REAL,
                next_run_at REAL NOT NULL,
                interval_seconds INTEGER NOT NULL DEFAULT 86400,
                created_at REAL NOT NULL
            );
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(schedules)").fetchall()]
        if "worker_id" not in cols:
            conn.execute("ALTER TABLE schedules ADD COLUMN worker_id TEXT")
        if "paused" not in cols:
            conn.execute("ALTER TABLE schedules ADD COLUMN paused INTEGER NOT NULL DEFAULT 0")


# Re-export schedule helpers used by main / workflow_loader
def init_schedules():
    init_routines()


def create_schedule(
    name: str,
    prompt: str,
    interval_seconds: int = 86400,
    playbook_id: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> dict:
    return create_routine(
        name=name,
        prompt=prompt,
        interval_seconds=interval_seconds,
        playbook_id=playbook_id,
        worker_id=worker_id,
    )


def create_routine(
    name: str,
    prompt: str,
    interval_seconds: int = 86400,
    playbook_id: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> dict:
    from .workers import DEFAULT_WORKER_ID, ensure_default_worker

    ensure_default_worker()
    wid = worker_id or DEFAULT_WORKER_ID
    sched_id = f"rtn_{uuid.uuid4().hex[:8]}"
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO schedules
               (id, name, cron_expr, playbook_id, prompt, enabled, next_run_at,
                interval_seconds, created_at, worker_id, paused)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 0)""",
            (
                sched_id,
                name,
                f"every_{interval_seconds}s",
                playbook_id,
                prompt,
                now + interval_seconds,  # first run after one interval (or allow due now? article: standing)
                interval_seconds,
                now,
                wid,
            ),
        )
    # For UX: allow immediate next_run = now so first tick can fire; use now for demos
    with _connect() as conn:
        conn.execute(
            "UPDATE schedules SET next_run_at = ? WHERE id = ?",
            (now, sched_id),
        )
    return get_routine(sched_id)


def get_schedule(sched_id: str) -> Optional[dict]:
    return get_routine(sched_id)


def get_routine(routine_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id = ?", (routine_id,)).fetchone()
        return _normalize(dict(row)) if row else None


def list_schedules() -> list:
    return list_routines()


def list_routines(worker_id: Optional[str] = None) -> List[dict]:
    with _connect() as conn:
        if worker_id:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE worker_id = ? ORDER BY created_at DESC",
                (worker_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
    return [_normalize(dict(r)) for r in rows]


def _normalize(d: dict) -> dict:
    d["id"] = d.get("id")
    d["paused"] = bool(d.get("paused"))
    d["enabled"] = bool(d.get("enabled"))
    d["routine"] = True
    return d


def pause_routine(routine_id: str) -> Optional[dict]:
    with _connect() as conn:
        conn.execute("UPDATE schedules SET paused = 1, enabled = 0 WHERE id = ?", (routine_id,))
    return get_routine(routine_id)


def resume_routine(routine_id: str) -> Optional[dict]:
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "UPDATE schedules SET paused = 0, enabled = 1, next_run_at = ? WHERE id = ?",
            (now, routine_id),
        )
    return get_routine(routine_id)


def delete_routine(routine_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM schedules WHERE id = ?", (routine_id,))
        return cur.rowcount == 1


def _due_schedules() -> list:
    now = time.time()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE enabled = 1 AND paused = 0 AND next_run_at <= ?",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]


def _mark_ran(sched_id: str, interval_seconds: int):
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "UPDATE schedules SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (now, now + interval_seconds, sched_id),
        )


async def _post_routine_to_transcript(job: dict, summary: str, ok: bool = True):
    from .workers import DEFAULT_WORKER_ID, set_presence

    worker_id = job.get("worker_id") or DEFAULT_WORKER_ID
    # Find or create a chat for this worker to receive the run
    chats = memory.list_sessions(limit=1, worker_id=worker_id)
    if chats:
        session_id = chats[0]["id"]
    else:
        session = memory.create_session(worker_id=worker_id)
        session_id = session["id"]

    memory.add_message(
        session_id,
        "assistant",
        f"Routine **{job['name']}** {'completed' if ok else 'failed'}.",
        metadata={
            "intent": "routine_run",
            "routine_id": job["id"],
            "ok": ok,
        },
        kind="event",
    )
    art = create_artifact(
        worker_id=worker_id,
        title=f"Routine: {job['name']}",
        kind="report",
        session_id=session_id,
        text=summary,
        meta={"routine_id": job["id"], "prompt": job.get("prompt")},
    )
    memory.add_message(
        session_id,
        "assistant",
        art["title"],
        metadata=artifact_ref_payload(art),
        kind="artifact_ref",
    )
    set_presence(worker_id, "done" if ok else "blocked", current_action=None)


async def run_due_jobs(broadcast_action=None):
    from .workers import DEFAULT_WORKER_ID, set_presence

    for job in _due_schedules():
        print(f"[Scheduler] Running job {job['id']}: {job['name']}")
        worker_id = job.get("worker_id") or DEFAULT_WORKER_ID
        set_presence(worker_id, "working", current_action=f"Routine: {job['name']}")
        summary = ""
        ok = True
        try:
            if job.get("playbook_id"):
                await run_playbook(
                    job["playbook_id"], job["prompt"], sandbox_manager, agent_runner, broadcast_action
                )
                summary = f"Playbook `{job['playbook_id']}` ran with prompt:\n\n{job['prompt']}"
            else:
                from .orchestrator import orchestrator
                machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
                if machines:
                    mid = machines[0]["id"]
                else:
                    mid = (await sandbox_manager.create_sandbox(name=f"Scheduled-{job['name']}"))["id"]
                    await asyncio.sleep(8)
                await orchestrator.run_single_task(mid, job["prompt"], broadcast_action)
                summary = f"Task ran on `{mid}`:\n\n{job['prompt']}"
        except Exception as e:
            ok = False
            summary = f"Error: {e}"
            print(f"[Scheduler] Job {job['id']} failed: {e}")
        try:
            await _post_routine_to_transcript(job, summary, ok=ok)
        except Exception as e:
            print(f"[Scheduler] Transcript post failed: {e}")
        _mark_ran(job["id"], job["interval_seconds"])


async def scheduler_loop(broadcast_action=None, poll_seconds: int = 60):
    init_routines()
    while True:
        try:
            await run_due_jobs(broadcast_action)
        except Exception as e:
            print(f"[Scheduler] Loop error: {e}")
        await asyncio.sleep(poll_seconds)
