"""
OpenWorker Skills — Markdown + YAML frontmatter (ClawHub-style, lighter than playbooks).

Skills teach the agent HOW to do something; playbooks define fleet orchestration steps.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .config import DATA_DIR

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
USER_SKILLS_DIR = DATA_DIR / "skills"


def _parse_skill_file(path: Path) -> Optional[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()

    skill_id = frontmatter.get("id") or path.parent.name
    triggers = frontmatter.get("triggers") or []
    if isinstance(triggers, str):
        triggers = [triggers]

    return {
        "id": skill_id,
        "name": frontmatter.get("name", skill_id),
        "description": frontmatter.get("description", ""),
        "triggers": [t.lower() for t in triggers],
        "playbook_id": frontmatter.get("playbook_id"),
        "content": body,
        "path": str(path),
    }


def load_all_skills() -> List[dict]:
    skills: Dict[str, dict] = {}
    for base in (SKILLS_DIR, USER_SKILLS_DIR):
        if not base.exists():
            continue
        for path in base.rglob("SKILL.md"):
            skill = _parse_skill_file(path)
            if skill:
                skills[skill["id"]] = skill
    return list(skills.values())


def match_skills(message: str, limit: int = 3) -> List[dict]:
    lower = message.lower()
    matched = []
    for skill in load_all_skills():
        score = 0
        for trigger in skill.get("triggers", []):
            if trigger in lower:
                score += len(trigger)
        if score > 0:
            matched.append((score, skill))
    matched.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in matched[:limit]]


def skills_context_for_message(message: str) -> str:
    """Inject matched skill instructions into agent prompts."""
    matched = match_skills(message)
    if not matched:
        return ""
    parts = ["## Active OpenWorker Skills\n"]
    for skill in matched:
        parts.append(f"### {skill['name']} (`{skill['id']}`)\n{skill['content']}\n")
    return "\n".join(parts)


def list_skills_catalog() -> List[dict]:
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "triggers": s.get("triggers", []),
            "playbook_id": s.get("playbook_id"),
        }
        for s in load_all_skills()
    ]
