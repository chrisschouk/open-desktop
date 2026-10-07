"""
Sandbox availability — local Docker, remote Hetzner SSH, or disabled.
"""
import asyncio
from typing import Optional

from .config import HETZNER_HOST, SANDBOX_ENABLED, SANDBOX_MODE, SSH_HOST_ALIAS

DESKTOP_INTENTS = frozenset({"research", "automate", "playbook"})


def effective_sandbox_mode() -> str:
    mode = SANDBOX_MODE.lower()
    if mode == "remote" or (mode != "local" and HETZNER_HOST):
        return "remote"
    return "local"


async def _local_docker_available() -> dict:
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


async def _remote_docker_available() -> dict:
    if not HETZNER_HOST:
        return {"available": False, "error": "HETZNER_HOST not set"}
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            SSH_HOST_ALIAS,
            "docker", "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return {"available": True, "host": HETZNER_HOST, "ssh_alias": SSH_HOST_ALIAS}
        err = stderr.decode().strip() or "remote docker unavailable"
        return {"available": False, "error": err, "host": HETZNER_HOST}
    except FileNotFoundError:
        return {"available": False, "error": "ssh not found"}
    except Exception as e:
        return {"available": False, "error": str(e), "host": HETZNER_HOST}


async def get_sandbox_status() -> dict:
    mode = effective_sandbox_mode()
    status = {
        "sandbox_enabled": SANDBOX_ENABLED,
        "sandbox_mode": mode,
        "hetzner_host": HETZNER_HOST or None,
        "ssh_host_alias": SSH_HOST_ALIAS,
    }

    if not SANDBOX_ENABLED:
        status.update({
            "sandbox_available": False,
            "reason": "sandbox_disabled",
        })
        return status

    if mode == "remote":
        remote = await _remote_docker_available()
        status["remote"] = remote
        status["sandbox_available"] = remote.get("available", False)
        if not status["sandbox_available"]:
            status["reason"] = remote.get("error", "remote_sandbox_unavailable")
    else:
        docker = await _local_docker_available()
        status["docker"] = docker
        status["sandbox_available"] = docker.get("available", False)
        if not status["sandbox_available"]:
            status["reason"] = docker.get("error", "local_docker_unavailable")

    return status


def should_fallback_desktop(
    intent: str,
    force_intent: Optional[str],
    sandbox_status: dict,
) -> bool:
    """Downgrade T2/T3 desktop intents to browser when sandbox is unavailable."""
    if intent not in DESKTOP_INTENTS:
        return False
    if force_intent in DESKTOP_INTENTS:
        return False
    return not sandbox_status.get("sandbox_available", False)
