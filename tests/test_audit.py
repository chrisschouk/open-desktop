import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def audit_db(monkeypatch):
    tmp = tempfile.mkdtemp()
    data_dir = Path(tmp)
    monkeypatch.setattr("server.audit.DATA_DIR", data_dir)
    monkeypatch.setattr("server.audit.AUDIT_DB", data_dir / "audit.db")
    from server import audit

    audit.init_audit()
    return audit


def test_audit_chain_valid(audit_db):
    audit_db.append_audit("chat", {"message": "hello"})
    audit_db.append_audit("action", {"type": "click", "x": 10, "y": 20})
    result = audit_db.verify_chain()
    assert result["valid"] is True
    assert result["entries"] == 2


def test_list_audit_returns_entries(audit_db):
    audit_db.append_audit("test", {"foo": "bar"})
    entries = audit_db.list_audit()
    assert len(entries) == 1
    assert entries[0]["event_type"] == "test"
