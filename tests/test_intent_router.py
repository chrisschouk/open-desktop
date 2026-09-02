from server.intent_router import _heuristic_classify


def test_heuristic_chat_greeting():
    result = _heuristic_classify("Hello, what can you do?")
    assert result["intent"] == "chat"


def test_heuristic_playbook_music_pr():
    result = _heuristic_classify("Run a music pr campaign for indie rock")
    assert result["intent"] == "playbook"
    assert result["playbook_id"] == "pb_music_pr_discovery"


def test_heuristic_browser_lookup():
    result = _heuristic_classify("What is a radio plugger?")
    assert result["intent"] == "browser"


def test_heuristic_research():
    result = _heuristic_classify("Find 10 UK playlist curators")
    assert result["intent"] in ("research", "automate")
