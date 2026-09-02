"""
Scheduled playbook jobs — cron-style automation for OpenWorker.
"""
import asyncio
import json
import sqlite3
import time
import uuid
from typing import Optional

from .config import DATA_DIR
from .playbook_executor import run_playbook
from .sandbox_factory import sandbox_manager
from .agent_runner import agent_runner

SCHEDULE_DB = DATA_DIR / "schedules.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(SCHEDULE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_schedules():
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


def create_schedule(
    name: str,
    prompt: str,
    interval_seconds: int = 86400,
    playbook_id: Optional[str] = None,
) -> dict:
    sched_id = f"sched_{uuid.uuid4().hex[:8]}"
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO schedules
               (id, name, cron_expr, playbook_id, prompt, enabled, next_run_at, interval_seconds, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
            (sched_id, name, f"every_{interval_seconds}s", playbook_id, prompt, now, interval_seconds, now),
        )
    return get_schedule(sched_id)


def get_schedule(sched_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id = ?", (sched_id,)).fetchone()
        return dict(row) if row else None


def list_schedules() -> list:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def _due_schedules() -> list:
    now = time.time()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE enabled = 1 AND next_run_at <= ?",
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


async def run_due_jobs(broadcast_action=None):
    for job in _due_schedules():
        print(f"[Scheduler] Running job {job['id']}: {job['name']}")
        try:
            if job.get("playbook_id"):
                await run_playbook(
                    job["playbook_id"], job["prompt"], sandbox_manager, agent_runner, broadcast_action
                )
            else:
                from .orchestrator import orchestrator
                machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
                if machines:
                    mid = machines[0]["id"]
                else:
                    mid = (await sandbox_manager.create_sandbox(name=f"Scheduled-{job['name']}"))["id"]
                    await asyncio.sleep(8)
                await orchestrator.run_single_task(mid, job["prompt"], broadcast_action)
        except Exception as e:
            print(f"[Scheduler] Job {job['id']} failed: {e}")
        _mark_ran(job["id"], job["interval_seconds"])


async def scheduler_loop(broadcast_action=None, poll_seconds: int = 60):
    init_schedules()
    while True:
        try:
            await run_due_jobs(broadcast_action)
        except Exception as e:
            print(f"[Scheduler] Loop error: {e}")
        await asyncio.sleep(poll_seconds)
