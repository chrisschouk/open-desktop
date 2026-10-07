"""Tests for Worker-centric design primitives."""
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def worker_env(monkeypatch):
    tmp = tempfile.mkdtemp()
    data_dir = Path(tmp)
    monkeypatch.setattr("server.memory.DATA_DIR", data_dir)
    monkeypatch.setattr("server.memory.DB_PATH", data_dir / "sessions.db")
    monkeypatch.setattr("server.artifacts.ARTIFACTS_DIR", data_dir / "artifacts")
    monkeypatch.setattr("server.routines.SCHEDULE_DB", data_dir / "schedules.db")
    from server import memory
    from server import workers
    from server import artifacts
    from server import routines

    memory.init_db()
    workers.init_workers()
    artifacts.init_artifacts()
    routines.init_routines()
    return memory, workers, artifacts, routines


def test_default_worker_seeded(worker_env):
    memory, workers, artifacts, routines = worker_env
    w = workers.get_worker(workers.DEFAULT_WORKER_ID)
    assert w is not None
    assert w["name"] == "OpenWorker"
    assert w["presence"] == "idle"


def test_session_bound_to_worker(worker_env):
    memory, workers, artifacts, routines = worker_env
    session = memory.create_session()
    assert session["worker_id"] == workers.DEFAULT_WORKER_ID


def test_create_second_worker_and_chat(worker_env):
    memory, workers, artifacts, routines = worker_env
    w2 = workers.create_worker(name="Music PR", avatar="music", role="Music PR specialist")
    chat = workers.create_chat_for_worker(w2["id"])
    assert chat["worker_id"] == w2["id"]
    chats = workers.list_worker_chats(w2["id"])
    assert len(chats) >= 1


def test_presence_states(worker_env):
    memory, workers, artifacts, routines = worker_env
    wid = workers.DEFAULT_WORKER_ID
    workers.set_presence(wid, "working", current_action="Browsing SubmitHub")
    w = workers.get_worker(wid)
    assert w["presence"] == "working"
    assert "SubmitHub" in (w.get("current_action") or "")


def test_message_kinds(worker_env):
    memory, workers, artifacts, routines = worker_env
    session = memory.create_session()
    sid = session["id"]
    memory.add_message(sid, "assistant", "Hello", kind="text")
    memory.add_message(sid, "assistant", "Routine created", kind="event")
    memory.add_message(sid, "assistant", "Draft email", kind="widget")
    msgs = memory.get_messages(sid)
    kinds = [m["kind"] for m in msgs]
    assert "text" in kinds
    assert "event" in kinds
    assert "widget" in kinds


def test_artifact_and_routine(worker_env):
    memory, workers, artifacts, routines = worker_env
    wid = workers.DEFAULT_WORKER_ID
    art = artifacts.create_artifact(wid, "Weekly report", kind="report", text="# Report\n\nDone.")
    assert art["id"].startswith("art_")
    assert Path(art["path"]).exists()
    rtn = routines.create_routine("Morning briefing", "Summarize inbox", interval_seconds=3600, worker_id=wid)
    assert rtn["worker_id"] == wid
    assert rtn["id"].startswith("rtn_")
    paused = routines.pause_routine(rtn["id"])
    assert paused["paused"] is True


def test_worker_limit(worker_env):
    memory, workers, artifacts, routines = worker_env
    # starter roster may already have several workers
    existing = len(workers.list_workers())
    for i in range(workers.MAX_WORKERS - existing):
        workers.create_worker(name=f"W{i}")
    with pytest.raises(ValueError):
        workers.create_worker(name="overflow")


def test_group_chat(worker_env):
    memory, workers, artifacts, routines = worker_env
    from server import groups
    groups.init_groups()
    g = groups.create_group_chat(
        "Acme launch",
        [workers.DEFAULT_WORKER_ID, "wrk_research"],
        coordinator_id="wrk_coordinator",
    )
    assert g["id"].startswith("grp_")
    assert len(g["members"]) == 2
