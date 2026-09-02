# WorkerHub

**Agent discovery registry** for OpenWorker skills and playbooks.

WorkerHub is how agents (and humans) enumerate what the system *can* do without reading the filesystem.

---

## API

```http
GET /api/v1/workerhub
```

Returns bundled skills (`skills/*/SKILL.md`) and playbooks (`playbooks/*.json`) with metadata.

## CLI

```bash
openworker hub
```

## Agent usage

Call during **orient** phase (see [AGENT_SYSTEM.md](AGENT_SYSTEM.md)):

```
health → workerhub → (optional) plan message
```

Match flow:

1. User message arrives
2. `match_skills(message)` checks triggers
3. Matched skill may set `playbook_id` and inject context into prompt
4. Intent router runs (skill can bias toward playbook)

---

## Adding a skill

1. Create `skills/<your-skill>/SKILL.md`:

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

2. Restart server, or copy to `data/skills/` for user-local overlay.

**Agent-accretion tip:** Skills are cheap to ship — prefer a skill over a new core route.

---

## Adding a playbook

`playbooks/my_playbook.json` — require `playbook_id`, `name`, `workflow[]`.

Declare honest `execution_mode` in API responses (see playbook executor).

---

## Future (WorkerHub v2)

See [ROADMAP.md](ROADMAP.md) Phase F:

- Semver pins for agents
- `workerhub install <package>`
- Session → skill export

---

## Buzz integration

Buzz agents discover OpenDesktop capabilities via MCP + WorkerHub:

```bash
OPENDESKTOP_API_URL=http://localhost:8000 python connectors/mcp_server.py
```

Prefer `openworker_chat` tool. See [BUZZ.md](BUZZ.md).
