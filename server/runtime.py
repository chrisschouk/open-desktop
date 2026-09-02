"""
Shared helpers for sandbox provisioning and API auth.
"""
import os
import asyncio
import time
from typing import Optional

API_GATEWAY_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", os.getenv("API_GATEWAY_TOKEN", ""))


def verify_api_token(authorization: Optional[str]) -> bool:
    """If OPENDESKTOP_API_TOKEN is set, require Bearer token on sensitive routes."""
    if not API_GATEWAY_TOKEN:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return authorization.removeprefix("Bearer ").strip() == API_GATEWAY_TOKEN


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
    await wait_for_sandbox_running(sandbox_manager, machine_id)
    return machine_id
