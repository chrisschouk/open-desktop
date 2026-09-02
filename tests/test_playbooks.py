import pytest

from server.playbook_executor import EXECUTION_MODE, list_playbooks


def test_playbooks_expose_execution_metadata():
    playbooks = list_playbooks()
    assert len(playbooks) >= 1
    music = next((p for p in playbooks if p["playbook_id"] == "pb_music_pr_discovery"), None)
    assert music is not None
    assert music["execution_mode"] == EXECUTION_MODE
    assert music["step_count"] >= 1
    assert "execution_note" in music
