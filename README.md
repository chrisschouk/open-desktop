# OpenDesktop + OpenWorker

OpenDesktop is the open source platform. **OpenWorker** is the conversational desktop agent that runs on top of it — Grok-style chat that actually spins up a Linux desktop and does the work.

## Quick start

```bash
git clone https://github.com/totalaudiopromo/open-desktop.git
cd open-desktop
cp .env.example .env
# Add your CHAT_API_KEY and VISION_API_KEY

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

## Architecture

```
Channels (Discord, Telegram, Web)
         ↓
   Gateway dispatch
         ↓
OpenWorker (intent router + skills)
    ↓ chat / browser / desktop
Desktop Sandbox (Docker XFCE) + vision loop
```

## CLI

```bash
python cli/openworker.py chat "Research UK radio pluggers"
python cli/openworker.py playbook run pb_music_pr_discovery --prompt "indie rock"
python cli/openworker.py hub
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

See `.env.example`. Key variables:

| Variable | Purpose |
|---|---|
| `SANDBOX_MODE` | `local` (default) or `remote` |
| `CHAT_API_KEY` | Fast LLM for conversation |
| `VISION_API_KEY` | Multimodal model for desktop control |
| `DEFAULT_PERSONA` | `openworker` (default) |

## Playbooks

Built-in workflows in `playbooks/`:

- `pb_web_research` — web research & synthesis
- `pb_lead_gen_campaign` — multi-agent lead gen
- `pb_music_pr_discovery` — music PR contact discovery
- `pb_data_entry_rpa` — cross-app RPA

## License

MIT
