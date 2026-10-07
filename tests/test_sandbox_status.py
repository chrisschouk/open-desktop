import pytest

from server.sandbox_status import (
    DESKTOP_INTENTS,
    should_fallback_desktop,
)


def test_should_fallback_when_sandbox_unavailable():
    status = {"sandbox_available": False}
    assert should_fallback_desktop("research", None, status) is True
    assert should_fallback_desktop("playbook", None, status) is True
    assert should_fallback_desktop("chat", None, status) is False


def test_should_not_fallback_when_forced():
    status = {"sandbox_available": False}
    assert should_fallback_desktop("research", "research", status) is False
    assert should_fallback_desktop("playbook", "playbook", status) is False


def test_should_not_fallback_when_sandbox_available():
    status = {"sandbox_available": True}
    assert should_fallback_desktop("research", None, status) is False


def test_desktop_intents_set():
    assert "research" in DESKTOP_INTENTS
    assert "browser" not in DESKTOP_INTENTS


@pytest.mark.asyncio
async def test_agent_plan_shows_fallback_when_sandbox_disabled(monkeypatch):
    monkeypatch.setenv("SANDBOX_ENABLED", "false")
    import importlib
    import server.config as config
    import server.sandbox_status as sandbox_status

    importlib.reload(config)
    importlib.reload(sandbox_status)

    from server.agent_api import agent_plan

    result = await agent_plan(
        "Open a browser and research UK radio pluggers",
        force_intent="research",
    )
    # forced intent should NOT fallback in plan — user explicitly asked for desktop
    assert result["intent"] == "research"

    result = await agent_plan("Open a browser and research UK radio pluggers")
    if result.get("original_intent") == "research":
        assert result["fallback"] is True
        assert result["intent"] == "browser"
        assert result["tier"] == "T1"


@pytest.mark.asyncio
async def test_get_sandbox_status_disabled(monkeypatch):
    monkeypatch.setenv("SANDBOX_ENABLED", "false")
    import importlib
    import server.config as config
    import server.sandbox_status as sandbox_status

    importlib.reload(config)
    importlib.reload(sandbox_status)

    status = await sandbox_status.get_sandbox_status()
    assert status["sandbox_enabled"] is False
    assert status["sandbox_available"] is False
    assert status["reason"] == "sandbox_disabled"
