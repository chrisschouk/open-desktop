"""
Shared helpers for sandbox provisioning and API auth.
"""
import ipaddress
import os
import asyncio
import time
from typing import Optional

from fastapi import Request

API_GATEWAY_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", os.getenv("API_GATEWAY_TOKEN", ""))


def verify_api_token(authorization: Optional[str]) -> bool:
    """If OPENDESKTOP_API_TOKEN is set, require Bearer token on sensitive routes."""
    if not API_GATEWAY_TOKEN:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return authorization.removeprefix("Bearer ").strip() == API_GATEWAY_TOKEN


def is_trusted_local_request(request: Request) -> bool:
    """Allow key setup from loopback / private LAN (local dev dashboard)."""
    if not request.client:
        return False
    host = request.client.host
    if host in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def can_set_api_key(request: Request, authorization: Optional[str]) -> bool:
    """Keys via UI only from trusted networks, or with Bearer token when configured."""
    if API_GATEWAY_TOKEN:
        return verify_api_token(authorization)
    return is_trusted_local_request(request)


async def wait_for_sandbox_running(sandbox_manager, machine_id: str, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = sandbox_manager.get_sandbox(machine_id)
        if info and info.get("status") == "running":
            return True
        await asyncio.sleep(2)
    return False


async def ensure_running_sandbox(sandbox_manager, name: str = "OpenWorker Agent") -> str:
    machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
    if machines:
        return machines[0]["id"]
    machine_data = await sandbox_manager.create_sandbox(name=name)
    machine_id = machine_data["id"]
    if not await wait_for_sandbox_running(sandbox_manager, machine_id):
        raise RuntimeError(f"Sandbox {machine_id} did not become healthy in time")
    return machine_id
