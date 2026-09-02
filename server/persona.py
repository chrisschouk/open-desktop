"""
Load OpenWorker / OpenDesktop persona YAML files.
"""
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .config import DEFAULT_PERSONA, PERSONAS_DIR


_cache: Dict[str, dict] = {}


def load_persona(persona_id: Optional[str] = None) -> dict:
    pid = persona_id or DEFAULT_PERSONA
    if pid in _cache:
        return _cache[pid]

    path = PERSONAS_DIR / f"{pid}.yaml"
    if not path.exists():
        path = PERSONAS_DIR / "default.yaml"

    with open(path) as f:
        data = yaml.safe_load(f)

    _cache[pid] = data
    return data


def get_system_prompt(persona_id: Optional[str] = None) -> str:
    return load_persona(persona_id).get("system_prompt", "You are a helpful assistant.")


def get_greeting(persona_id: Optional[str] = None) -> str:
    return load_persona(persona_id).get("greeting", "Hello! How can I help?")
