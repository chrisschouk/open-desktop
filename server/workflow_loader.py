"""
Load Buzz-style workflow YAML files into the scheduler on startup.
"""
from pathlib import Path
from typing import List

import yaml

from .scheduler import create_schedule, list_schedules, init_schedules

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"


def _workflow_key(path: Path) -> str:
    return path.stem


def _existing_workflow_names() -> set:
    return {s.get("name") for s in list_schedules()}


def load_workflow_files(workflows_dir: Path = WORKFLOWS_DIR) -> List[dict]:
    """Import workflows/*.yaml into schedules if not already present."""
    init_schedules()
    if not workflows_dir.exists():
        return []

    imported = []
    seen_names = _existing_workflow_names()

    for path in sorted(workflows_dir.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Workflows] Failed to parse {path.name}: {e}")
            continue

        name = data.get("name") or path.stem.replace("_", " ").title()
        if name in seen_names:
            continue

        trigger = data.get("trigger") or {}
        interval = int(trigger.get("interval_seconds", 86400))
        prompt = data.get("prompt") or ""
        playbook_id = data.get("playbook_id")

        if not prompt:
            print(f"[Workflows] Skipping {path.name} — no prompt")
            continue

        sched = create_schedule(
            name=name,
            prompt=prompt,
            interval_seconds=interval,
            playbook_id=playbook_id,
            worker_id=data.get("worker_id"),
        )
        seen_names.add(name)
        imported.append({"file": path.name, "schedule_id": sched["id"], "name": name})
        print(f"[Workflows] Imported {path.name} → schedule {sched['id']}")

    return imported
