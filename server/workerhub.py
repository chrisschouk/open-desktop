"""
WorkerHub — catalog of installable skills and playbooks for OpenWorker.
"""
from .skills import list_skills_catalog
from .playbook_executor import list_playbooks

HUB_VERSION = "0.1.0"


def get_workerhub_catalog() -> dict:
    skills = list_skills_catalog()
    playbooks = list_playbooks()
    return {
        "name": "WorkerHub",
        "version": HUB_VERSION,
        "description": "Open source skill and playbook catalog for OpenDesktop OpenWorker",
        "skills": skills,
        "playbooks": playbooks,
        "install": {
            "skills": "Copy SKILL.md into skills/<name>/ or data/skills/",
            "playbooks": "Add JSON to playbooks/ directory",
        },
    }
