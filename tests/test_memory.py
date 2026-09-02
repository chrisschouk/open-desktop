import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def memory_db(monkeypatch):
    tmp = tempfile.mkdtemp()
    data_dir = Path(tmp)
    monkeypatch.setattr("server.memory.DATA_DIR", data_dir)
    monkeypatch.setattr("server.memory.DB_PATH", data_dir / "sessions.db")
    from server import memory

    memory.init_db()
    return memory


def test_try_acquire_session_atomic(memory_db):
    session = memory_db.create_session()
    sid = session["id"]

    assert memory_db.try_acquire_session(sid) is True
    assert memory_db.get_session(sid)["status"] == "working"
    assert memory_db.try_acquire_session(sid) is False


def test_get_messages_returns_latest(memory_db):
    session = memory_db.create_session()
    sid = session["id"]
    for i in range(60):
        memory_db.add_message(sid, "user", f"msg-{i}")
    msgs = memory_db.get_messages(sid, limit=50)
    assert len(msgs) == 50
    assert msgs[0]["content"] == "msg-10"
    assert msgs[-1]["content"] == "msg-59"
