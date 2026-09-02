# WorkerHub

Community catalog for **OpenWorker** skills and playbooks.

## API

```
GET /api/v1/workerhub
```

Returns bundled skills (`skills/*/SKILL.md`) and playbooks (`playbooks/*.json`).

## CLI

```bash
python cli/openworker.py hub
```

## Adding a skill

1. Create `skills/<your-skill>/SKILL.md` with YAML frontmatter:

```yaml
---
id: my-skill
name: My Skill
triggers:
  - keyword phrase
playbook_id: pb_optional
---
Instructions for OpenWorker...
```

2. Restart the server or copy to `data/skills/` for user-local skills.

## Adding a playbook

Add `playbooks/my_playbook.json` following existing schema (`playbook_id`, `name`, `workflow`).

## Buzz integration

Buzz agents can call OpenDesktop via the MCP stdio server:

```bash
OPENDESKTOP_API_URL=http://localhost:8000 python connectors/mcp_server.py
```

See [BUZZ.md](BUZZ.md).
