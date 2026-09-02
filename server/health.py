"""
Health checks for OpenDesktop / OpenWorker control plane.
"""
import os
from typing import Any, Dict

from .config import (
    CHAT_API_KEY,
    HETZNER_HOST,
    OPENROUTER_API_KEY,
    SANDBOX_ENABLED,
    SANDBOX_IMAGE,
    SANDBOX_MODE,
    SCHEDULER_ENABLED,
    SSH_HOST_ALIAS,
    VISION_API_KEY,
    llm_provider_label,
)
from .runtime import API_GATEWAY_TOKEN
from .sandbox_factory import sandbox_manager
from .sandbox_status import get_sandbox_status


async def get_health() -> Dict[str, Any]:
    chat_key = os.getenv("CHAT_API_KEY") or os.getenv("OPENROUTER_API_KEY") or CHAT_API_KEY
    vision_key = os.getenv("VISION_API_KEY") or os.getenv("OPENROUTER_API_KEY") or VISION_API_KEY
    api_key_configured = bool(chat_key or vision_key)

    sandbox = await get_sandbox_status()
    machines = sandbox_manager.list_sandboxes()

    return {
        "status": "ok",
        "platform": "OpenDesktop",
        "agent": "OpenWorker",
        "sandbox_enabled": sandbox["sandbox_enabled"],
        "sandbox_available": sandbox["sandbox_available"],
        "sandbox_mode": sandbox["sandbox_mode"],
        "hetzner_host": HETZNER_HOST or None,
        "ssh_host_alias": SSH_HOST_ALIAS,
        "sandbox_image": SANDBOX_IMAGE,
        "api_key_configured": api_key_configured,
        "llm_provider": llm_provider_label(),
        "chat_api_key_configured": bool(chat_key),
        "vision_api_key_configured": bool(vision_key),
        "api_token_required": bool(API_GATEWAY_TOKEN),
        "scheduler_enabled": SCHEDULER_ENABLED,
        "docker": sandbox.get("docker") or sandbox.get("remote") or {"available": False},
        "sandbox": sandbox,
        "machines": {
            "total": len(machines),
            "running": sum(1 for m in machines if m.get("status") == "running"),
        },
    }
