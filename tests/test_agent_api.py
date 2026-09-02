import pytest

from server.agent_api import (
    agent_plan,
    build_next,
    envelope_chat_response,
    intent_to_tier,
    load_manifest,
    new_trace_id,
    tier_cost,
)


def test_intent_to_tier():
    assert intent_to_tier("chat") == "T0"
    assert intent_to_tier("browser") == "T1"
    assert intent_to_tier("research") == "T2"
    assert intent_to_tier("playbook") == "T3"
    assert tier_cost("T0") == "low"
    assert tier_cost("T2") == "high"


def test_new_trace_id_format():
    tid = new_trace_id()
    assert tid.startswith("tr_")


def test_load_manifest():
    manifest = load_manifest()
    assert manifest.get("system", {}).get("name") == "OpenDesktop"
    assert "tiers" in manifest


@pytest.mark.asyncio
async def test_agent_plan_dry_run():
    result = await agent_plan("What is a radio plugger?")
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["intent"] in ("chat", "browser", "research", "automate", "playbook")
    assert result["tier"] is not None


@pytest.mark.asyncio
async def test_agent_plan_force_intent():
    result = await agent_plan("hello", force_intent="chat")
    assert result["intent"] == "chat"
    assert result["tier"] == "T0"
    assert result["classification"]["forced"] is True


def test_envelope_chat_response():
    result = {
        "session_id": "sess_test123",
        "intent": "chat",
        "reply": "hi",
        "status": "idle",
    }
    env = envelope_chat_response(result, "tr_abc", "http://localhost:8000")
    assert env["ok"] is True
    assert env["trace_id"] == "tr_abc"
    assert env["tier"] == "T0"
    assert "observe" in env
    assert "next" in env
    assert env["observe"]["session"].endswith("sess_test123")


def test_build_next_working():
    assert "poll_session" in build_next("working")
