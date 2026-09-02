"""
Health checks for OpenDesktop / OpenWorker control plane.
"""
import asyncio
import os
from typing import Any, Dict

from .config import (
    CHAT_API_KEY,
    SANDBOX_MODE,
    SANDBOX_IMAGE,
    SCHEDULER_ENABLED,
    VISION_API_KEY,
)
from .runtime import API_GATEWAY_TOKEN
from .sandbox_factory import sandbox_manager


async def _docker_available() -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return {"available": proc.returncode == 0}
    except FileNotFoundError:
        return {"available": False, "error": "docker not found"}


async def get_health() -> Dict[str, Any]:
    chat_key = os.getenv("CHAT_API_KEY") or CHAT_API_KEY
    vision_key = os.getenv("VISION_API_KEY") or VISION_API_KEY
    api_key_configured = bool(chat_key or vision_key)

    docker = await _docker_available()
    machines = sandbox_manager.list_sandboxes()

    return {
        "status": "ok",
        "platform": "OpenDesktop",
        "agent": "OpenWorker",
        "sandbox_mode": SANDBOX_MODE,
        "sandbox_image": SANDBOX_IMAGE,
        "api_key_configured": api_key_configured,
        "chat_api_key_configured": bool(chat_key),
        "vision_api_key_configured": bool(vision_key),
        "api_token_required": bool(API_GATEWAY_TOKEN),
        "scheduler_enabled": SCHEDULER_ENABLED,
        "docker": docker,
        "machines": {
            "total": len(machines),
            "running": sum(1 for m in machines if m.get("status") == "running"),
        },
    }
