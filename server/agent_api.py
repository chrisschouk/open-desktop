"""
Agent-native API — orient, plan, manifest, response envelopes, trace IDs.
"""
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import memory
from .health import get_health
from .intent_router import classify_intent
from .sandbox_factory import sandbox_manager
from .sandbox_status import get_sandbox_status, should_fallback_desktop
from .skills import match_skills
from .workerhub import get_workerhub_catalog

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "agent" / "manifest.yaml"

INTENT_TIERS = {
    "chat": "T0",
    "browser": "T1",
    "research": "T2",
    "automate": "T2",
    "playbook": "T3",
    "busy": None,
    "fleet": "T4",
}

TIER_COST = {
    "T0": "low",
    "T1": "low",
    "T2": "high",
    "T3": "high",
    "T4": "very_high",
}


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def intent_to_tier(intent: Optional[str]) -> Optional[str]:
    if not intent:
        return None
    return INTENT_TIERS.get(intent)


def tier_cost(tier: Optional[str]) -> Optional[str]:
    if not tier:
        return None
    return TIER_COST.get(tier)


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"error": "manifest not found", "path": str(MANIFEST_PATH)}
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f) or {}


async def agent_orient(session_limit: int = 10) -> dict:
    health = await get_health()
    machines = sandbox_manager.list_sandboxes()
    sessions = memory.list_sessions(limit=session_limit)
    working = [s for s in sessions if s.get("status") == "working"]
    hub = get_workerhub_catalog()

    return {
        "ok": True,
        "health": health,
        "machines": machines,
        "sessions": {
            "recent": sessions,
            "working_count": len(working),
            "working_ids": [s["id"] for s in working],
        },
        "hub_summary": {
            "skills_count": len(hub.get("skills", [])),
            "playbooks_count": len(hub.get("playbooks", [])),
            "skill_ids": [s.get("id") for s in hub.get("skills", [])],
            "playbook_ids": [p.get("playbook_id") for p in hub.get("playbooks", [])],
        },
        "next": _orient_next(health),
    }


def _orient_next(health: dict) -> List[str]:
    steps = []
    if not health.get("api_key_configured"):
        steps.append("configure_api_key")
    if not health.get("sandbox_available"):
        sandbox = health.get("sandbox") or {}
        if not health.get("sandbox_enabled"):
            steps.append("browser_research_only_sandbox_disabled")
        elif health.get("sandbox_mode") == "remote":
            if not health.get("hetzner_host"):
                steps.append("set_hetzner_host")
            else:
                steps.append("fix_hetzner_ssh_or_remote_docker")
        else:
            steps.append("start_docker_for_desktop_tasks")
    if not steps:
        steps.append("create_session_or_chat")
    return steps


async def agent_plan(
    message: str,
    session_id: Optional[str] = None,
    force_intent: Optional[str] = None,
) -> dict:
    history = None
    if session_id:
        session = memory.get_session(session_id)
        if not session:
            return {"ok": False, "error": "Session not found", "session_id": session_id}
        history = memory.get_messages(session_id)

    matched_skills = match_skills(message)
    skill_playbook = matched_skills[0].get("playbook_id") if matched_skills else None

    if force_intent and force_intent in INTENT_TIERS:
        intent = force_intent
        classification = {
            "intent": intent,
            "playbook_id": skill_playbook,
            "task_prompt": message,
            "forced": True,
        }
    else:
        classification = await classify_intent(message, history)
        intent = classification.get("intent") or "chat"
        if skill_playbook and intent in ("research", "playbook", "automate"):
            intent = "playbook"
            classification["playbook_id"] = skill_playbook

    tier = intent_to_tier(intent)
    playbook_id = classification.get("playbook_id") or skill_playbook
    sandbox_status = await get_sandbox_status()
    sandbox_required = tier in ("T2", "T3", "T4")
    fallback = should_fallback_desktop(intent, force_intent, sandbox_status)

    plan = {
        "ok": True,
        "dry_run": True,
        "message": message,
        "session_id": session_id,
        "intent": intent,
        "tier": tier,
        "estimated_cost": tier_cost(tier),
        "sandbox_required": sandbox_required,
        "sandbox_available": sandbox_status.get("sandbox_available", False),
        "sandbox_mode": sandbox_status.get("sandbox_mode"),
        "playbook_id": playbook_id,
        "task_prompt": classification.get("task_prompt") or message,
        "skills": [s["id"] for s in matched_skills],
        "classification": classification,
        "next": _plan_next(intent, session_id),
    }

    if fallback:
        plan["fallback"] = True
        plan["fallback_intent"] = "browser"
        plan["fallback_tier"] = "T1"
        plan["fallback_cost"] = tier_cost("T1")
        plan["original_intent"] = intent
        plan["intent"] = "browser"
        plan["tier"] = "T1"
        plan["estimated_cost"] = tier_cost("T1")
        plan["sandbox_required"] = False
        plan["next"] = _plan_next("browser", session_id)

    return plan


def _plan_next(intent: str, session_id: Optional[str]) -> List[str]:
    if intent == "chat" or intent == "browser":
        return ["post_chat"]
    if session_id:
        return ["post_chat", "poll_session", "subscribe_actions"]
    return ["create_session", "post_chat", "poll_session", "subscribe_actions"]


def _api_base(request_base: Optional[str]) -> str:
    base = (request_base or "http://localhost:8000").rstrip("/")
    return base


def _ws_base(request_base: Optional[str]) -> str:
    base = _api_base(request_base)
    if base.startswith("https://"):
        return "wss://" + base.removeprefix("https://")
    return "ws://" + base.removeprefix("http://")


def build_observe(
    session_id: str,
    request_base: Optional[str] = None,
    machine_id: Optional[str] = None,
) -> dict:
    api = _api_base(request_base)
    ws = _ws_base(request_base)
    observe = {
        "health": f"{api}/api/v1/health",
        "orient": f"{api}/api/v1/agent/orient",
        "session": f"{api}/api/v1/sessions/{session_id}",
        "machines": f"{api}/api/v1/machines",
        "audit": f"{api}/api/v1/audit",
        "actions_ws": f"{ws}/ws/actions",
    }
    if machine_id:
        observe["machine"] = f"{api}/api/v1/machines/{machine_id}"
        observe["stream_ws"] = f"{ws}/ws/stream/{machine_id}"
    return observe


def build_next(status: str, intent: Optional[str] = None) -> List[str]:
    if status == "working":
        return ["poll_session", "subscribe_actions"]
    if status == "error":
        return ["read_session_messages", "check_audit"]
    if intent in ("chat", "browser"):
        return []
    return ["read_session_messages"]


def envelope_chat_response(
    result: dict,
    trace_id: str,
    request_base: Optional[str] = None,
) -> dict:
    """Wrap chat_service result in agent-legible envelope."""
    if result.get("error"):
        return {
            "ok": False,
            "trace_id": trace_id,
            "error": result["error"],
            **result,
        }

    session_id = result.get("session_id")
    intent = result.get("intent")
    status = result.get("status", "idle")
    tier = intent_to_tier(intent)

    session = memory.get_session(session_id) if session_id else None
    machine_id = result.get("machine_id") or (session.get("machine_id") if session else None)

    envelope = {
        "ok": True,
        "trace_id": trace_id,
        "session_id": session_id,
        "intent": intent,
        "tier": tier,
        "estimated_cost": tier_cost(tier),
        "status": status,
        "reply": result.get("reply"),
        "playbook_id": result.get("playbook_id"),
        "skills": result.get("skills", []),
    }

    if result.get("fallback"):
        envelope["fallback"] = True
        envelope["original_intent"] = result.get("original_intent")
        envelope["tier"] = "T1"
        envelope["estimated_cost"] = tier_cost("T1")

    if session_id:
        envelope["observe"] = build_observe(session_id, request_base, machine_id)
        envelope["next"] = build_next(status, intent)

    return envelope
