"""
Playbook executor — runs declarative JSON workflow templates.

Playbooks describe multi-machine campaign steps for planning and telemetry.
Execution currently runs on a single healthy sandbox with the full workflow
injected into the vision agent prompt (fleet routing is incremental).
"""
import json
from pathlib import Path
from typing import Callable, Optional

PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent / "playbooks"
EXECUTION_MODE = "single_sandbox_template"


def list_playbooks() -> list:
    playbooks = []
    for path in sorted(PLAYBOOKS_DIR.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            workflow = data.get("workflow") or []
            templates = data.get("templates_required") or {}
            playbooks.append({
                "playbook_id": data.get("playbook_id", path.stem),
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "category": data.get("category", "general"),
                "step_count": len(workflow),
                "fleet_machines_declared": len(templates),
                "execution_mode": EXECUTION_MODE,
                "execution_note": (
                    "Runs on one sandbox today; JSON steps guide the agent prompt. "
                    "Multi-machine fleet routing is on the roadmap."
                ),
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


def _workflow_prompt(playbook: dict, user_prompt: str) -> str:
    lines = [
        f"[Playbook: {playbook.get('name', playbook.get('playbook_id'))}]",
        playbook.get("description", ""),
        "",
        "Follow these campaign steps in order (single sandbox execution):",
    ]
    for step in playbook.get("workflow") or []:
        lines.append(
            f"  Step {step.get('step')}: [{step.get('action', 'task')}] {step.get('description', '')}"
        )
    lines.extend(["", f"User goal: {user_prompt}"])
    return "\n".join(lines)


async def _broadcast_step(
    broadcast_action: Optional[Callable],
    playbook_id: str,
    step: dict,
    machine_id: str,
    phase: str,
):
    if not broadcast_action:
        return
    await broadcast_action("playbook", {
        "type": "action",
        "step": step.get("step"),
        "thought": step.get("description", ""),
        "action_type": f"playbook_{phase}",
        "agent": f"Template · {step.get('machine', 'sandbox')}",
        "machine_id": machine_id,
        "playbook_id": playbook_id,
        "playbook_action": step.get("action"),
    })


async def run_playbook(
    playbook_id: str,
    prompt: str,
    sandbox_manager,
    agent_runner,
    broadcast_action: Optional[Callable] = None,
) -> dict:
    playbook = get_playbook(playbook_id)
    if not playbook:
        return {"status": "error", "message": f"Playbook not found: {playbook_id}"}

    workflow = playbook.get("workflow") or []

    if broadcast_action:
        await broadcast_action("playbook", {
            "type": "action",
            "step": 0,
            "thought": (
                f"Starting template: {playbook.get('name', playbook_id)} "
                f"({len(workflow)} steps, single-sandbox mode)"
            ),
            "action_type": "playbook_start",
            "agent": "Playbook Engine",
            "machine_id": "playbook",
            "playbook_id": playbook_id,
            "execution_mode": EXECUTION_MODE,
        })

    machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
    if machines:
        machine_id = machines[0]["id"]
    else:
        from .runtime import ensure_running_sandbox
        machine_id = await ensure_running_sandbox(sandbox_manager, f"Playbook-{playbook_id}")

    for step in workflow:
        await _broadcast_step(broadcast_action, playbook_id, step, machine_id, "step_planned")

    enriched = _workflow_prompt(playbook, prompt)

    result = await agent_runner.run_task(
        sandbox_id=machine_id,
        prompt=enriched,
        sandbox_manager=sandbox_manager,
        broadcast_action=broadcast_action,
    )

    if broadcast_action:
        await broadcast_action("playbook", {
            "type": "action",
            "step": len(workflow) + 1,
            "thought": f"Template {playbook_id} finished: {result.get('status')}",
            "action_type": "playbook_complete",
            "agent": "Playbook Engine",
            "machine_id": machine_id,
            "playbook_id": playbook_id,
            "execution_mode": EXECUTION_MODE,
        })

    return {
        **result,
        "playbook_id": playbook_id,
        "machine_id": machine_id,
        "execution_mode": EXECUTION_MODE,
        "steps_planned": len(workflow),
    }
