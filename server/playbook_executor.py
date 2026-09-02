"""
Playbook executor — runs declarative JSON workflows.
"""
import asyncio
import json
from pathlib import Path
from typing import Callable, Optional

PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent / "playbooks"


def list_playbooks() -> list:
    playbooks = []
    for path in sorted(PLAYBOOKS_DIR.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            playbooks.append({
                "playbook_id": data.get("playbook_id", path.stem),
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "category": data.get("category", "general"),
            })
        except Exception as e:
            print(f"[Playbooks] Failed to load {path}: {e}")
    return playbooks


def get_playbook(playbook_id: str) -> Optional[dict]:
    for path in PLAYBOOKS_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        if data.get("playbook_id") == playbook_id:
            return data
    return None


async def run_playbook(
    playbook_id: str,
    prompt: str,
    sandbox_manager,
    agent_runner,
    broadcast_action: Optional[Callable] = None,
) -> dict:
    """
    Execute playbook steps. Currently maps workflow steps to agent tasks
    on provisioned machines; full multi-machine routing is incremental.
    """
    playbook = get_playbook(playbook_id)
    if not playbook:
        return {"status": "error", "message": f"Playbook not found: {playbook_id}"}

    if broadcast_action:
        await broadcast_action("playbook", {
            "type": "action",
            "step": 0,
            "thought": f"Starting playbook: {playbook.get('name', playbook_id)}",
            "action_type": "playbook_start",
            "agent": "Playbook Engine",
            "machine_id": "playbook",
            "playbook_id": playbook_id,
        })

    machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
    if machines:
        machine_id = machines[0]["id"]
    else:
        from .runtime import ensure_running_sandbox
        machine_id = await ensure_running_sandbox(sandbox_manager, f"Playbook-{playbook_id}")

    # Build enriched prompt from playbook metadata
    enriched = (
        f"[Playbook: {playbook.get('name', playbook_id)}]\n"
        f"{playbook.get('description', '')}\n\n"
        f"User goal: {prompt}"
    )

    result = await agent_runner.run_task(
        sandbox_id=machine_id,
        prompt=enriched,
        sandbox_manager=sandbox_manager,
        broadcast_action=broadcast_action,
    )

    if broadcast_action:
        await broadcast_action("playbook", {
            "type": "action",
            "step": 99,
            "thought": f"Playbook {playbook_id} finished: {result.get('status')}",
            "action_type": "playbook_complete",
            "agent": "Playbook Engine",
            "machine_id": machine_id,
            "playbook_id": playbook_id,
        })

    return {**result, "playbook_id": playbook_id, "machine_id": machine_id}
