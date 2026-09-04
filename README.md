# OpenDesktop + OpenWorker

OpenDesktop is the open source platform. **OpenWorker** is the conversational desktop agent that runs on top of it — persistent **Workers** with their own computers, not disposable chat sessions.

## Quick start

```bash
git clone https://github.com/chrisschouk/open-desktop.git
cd open-desktop
cp .env.example .env
# One OpenRouter key covers chat + desktop — see docs/API_KEYS.md
# OPENROUTER_API_KEY=sk-or-v1-...

# Build sandbox image (first time only)
docker build -t opendesktop-sandbox:latest -f sandbox-engine/Dockerfile.sandbox sandbox-engine/

# Start server + dashboard
docker compose up -d server dashboard

# Or run locally:
python3 -m venv venv && source venv/bin/activate
pip install -r server/requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

cd client && python3 -m http.server 8888
```

Open **http://localhost:8888** → OpenWorker Chat tab.

## For AI agents

**Start:** [agent/README.md](agent/README.md) · [agent/manifest.yaml](agent/manifest.yaml) · [docs/AGENT_SYSTEM.md](docs/AGENT_SYSTEM.md)

```
orient → plan → act → observe → verify
GET /health → POST /sessions → POST /chat → poll session → report
```

Prefer MCP `openworker_chat` or CLI `openworker chat`. Full contract: [docs/AGENT_API.md](docs/AGENT_API.md).

## Architecture

```
Control plane (sessions, router, audit)
         ↓
Channels: MCP · CLI · REST · Gateway · Web
         ↓
OpenWorker tiers: T0 chat → T1 browser → T2 desktop → T3 playbook
         ↓
Compute plane (Docker sandboxes) + vision loop
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/AGENT_SYSTEM.md](docs/AGENT_SYSTEM.md)

## CLI

```bash
openworker orient                              # system snapshot
openworker plan "Research UK radio pluggers"   # dry-run tier
openworker chat "Research UK radio pluggers"
openworker wait sess_abc                       # poll until idle
openworker hub
```

## Buzz / MCP integration

```bash
OPENDESKTOP_API_URL=http://localhost:8000 python connectors/mcp_server.py
```

See [docs/BUZZ.md](docs/BUZZ.md) and [docs/WORKERHUB.md](docs/WORKERHUB.md).

## Demo

Music PR golden path: [docs/DEMO.md](docs/DEMO.md) · `./scripts/demo_music_pr.sh`

## Brand

- **OpenDesktop** — platform & engine
- **OpenWorker** — conversational agent

See [docs/BRAND.md](docs/BRAND.md).

## API

```bash
# Start a chat session
curl -X POST http://localhost:8000/api/v1/sessions

# Send a message
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Research UK indie radio pluggers", "session_id": "sess_..."}'
```

## Discord bot (optional)

```bash
export DISCORD_BOT_TOKEN=...
export OPENDESKTOP_API_URL=http://localhost:8000
python connectors/discord_bot.py
```

Or: `docker compose --profile discord up -d`

## Configuration

See `.env.example` and [docs/API_KEYS.md](docs/API_KEYS.md). One OpenRouter key is enough:

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | **Recommended** — one key for chat + desktop |
| `SANDBOX_MODE` | `local` (default) or `remote` |
| `OPENDESKTOP_API_TOKEN` | Bearer auth for gateway/MCP when exposed |
| `DEFAULT_PERSONA` | `openworker` (default) |

## Documentation

| Doc | Audience |
|-----|----------|
| [docs/README.md](docs/README.md) | Index |
| [docs/AGENT_SYSTEM.md](docs/AGENT_SYSTEM.md) | AI agents |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Agent-accretive plan |

## Playbooks

Built-in workflows in `playbooks/`:

- `pb_web_research` — web research & synthesis
- `pb_lead_gen_campaign` — multi-agent lead gen
- `pb_music_pr_discovery` — music PR contact discovery
- `pb_data_entry_rpa` — cross-app RPA

## License

MIT
