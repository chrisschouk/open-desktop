# Agent Entry Point

**You are an AI agent operating OpenDesktop/OpenWorker.**

Start here:

1. Read [docs/AGENT_SYSTEM.md](../docs/AGENT_SYSTEM.md) — ontology & control loop
2. Load [manifest.yaml](manifest.yaml) — machine-readable capabilities
3. Follow [docs/AGENT_API.md](../docs/AGENT_API.md) — REST/MCP contracts

## Cold start (30 seconds)

```bash
openworker orient
# or: curl -s localhost:8000/api/v1/agent/orient
openworker plan "your task here"   # dry-run tier before spending
```

## Golden path

```
POST /sessions → openworker plan "…" → POST /chat → openworker wait sess_…
```

Prefer MCP tool `openworker_chat` when available.

## Do not

- Poll screenshot WebSockets for status
- Send concurrent `/chat` while `session.status == working`
- Anchor memory on `machine_id`
