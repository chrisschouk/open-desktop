# OpenDesktop + OpenWorker Quickstart

Get a local OpenWorker chat and desktop sandbox running in a few minutes.

---

## One-command bootstrap

```bash
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

This copies `.env.example` → `.env`, builds the sandbox Docker image, and installs Python deps (including the `openworker` CLI).

Add your LLM key to `.env`:

```bash
CHAT_API_KEY=sk-...
VISION_API_KEY=sk-...
```

---

## Start the stack

**API server** (terminal 1):

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

**Web client** (terminal 2):

```bash
cd client && python3 -m http.server 8888
```

Open http://localhost:8888 — OpenWorker Chat is the default tab.

---

## Health check

```bash
curl http://localhost:8000/api/v1/health | jq
```

Returns `api_key_configured`, `docker.available`, sandbox mode, and machine counts.

---

## CLI

```bash
# After pip install -e .
openworker chat "What can you do?"
openworker chat "Research UK indie radio pluggers" --session sess_abc
openworker sandboxes list
openworker skills list
openworker playbook run pb_music_pr_discovery --prompt "indie rock release"
```

---

## Provision a sandbox manually

```bash
curl -X POST http://localhost:8000/api/v1/machines \
  -H "Content-Type: application/json" \
  -d '{"name": "Research-Worker-01"}'
```

Sandboxes survive server restarts — on startup, OpenDesktop reconciles `opendesktop-*` containers from Docker.

---

## Run a playbook

```bash
curl -X POST http://localhost:8000/api/v1/playbooks/run \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_id": "pb_music_pr_discovery",
    "prompt": "Find 10 UK indie radio pluggers for a rock release"
  }'
```

---

## Scheduled workflows

Drop YAML files in `workflows/` — they auto-import into the scheduler on startup:

```yaml
name: Weekly Music PR Discovery
trigger:
  interval_seconds: 604800
playbook_id: pb_music_pr_discovery
prompt: Find 10 new UK indie radio pluggers
```

---

## Buzz MCP integration

Expose OpenDesktop to [Block Buzz](https://github.com/block/buzz) agents via stdio MCP:

```json
{
  "mcpServers": {
    "opendesktop": {
      "command": "python",
      "args": ["connectors/mcp_server.py"],
      "env": {
        "OPENDESKTOP_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Tools include `openworker_chat` (conversational agent), `desktop_click`, `run_playbook`, and `list_sandboxes`. See [docs/BUZZ.md](BUZZ.md).

---

## Production notes

- Set `OPENDESKTOP_API_TOKEN` to require Bearer auth on `/api/v1/gateway/dispatch` and `/api/v1/tools/call`
- Set `AUTO_PROVISION_FLEET=false` (default) unless you want two machines on startup
- Use `SANDBOX_MODE=remote` with `HETZNER_HOST` for VPS deployments
