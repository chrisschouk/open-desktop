# Contributing to OpenDesktop

Thanks for helping build the open source desktop agent stack.

## Getting started

1. Fork and clone the repo
2. `cp .env.example .env` and add API keys
3. Build the sandbox image: `docker build -t opendesktop-sandbox:latest -f sandbox-engine/Dockerfile.sandbox sandbox-engine/`
4. Run the server: `uvicorn server.main:app --reload`
5. Run the client: `cd client && python3 -m http.server 8888`

## Project structure

- `agent/` — **AI agent entry** (`manifest.yaml`, README)
- `server/` — FastAPI control plane, OpenWorker chat, vision agent
- `client/` — Human observability UI (agents prefer API/MCP)
- `personas/` — OpenWorker personality YAML files
- `playbooks/` — Campaign template JSON (L3 procedures)
- `skills/` — Skill markdown (L3 knowledge)
- `connectors/` — Discord, Telegram, MCP → gateway
- `sandbox-engine/` — Docker desktop image (compute plane)
- `open_desktop/` — Python SDK
- `docs/` — [Documentation index](docs/README.md) — start at [AGENT_SYSTEM.md](docs/AGENT_SYSTEM.md) for agents

## Adding a playbook

1. Create `playbooks/your_playbook.json` following the existing schema
2. Include `playbook_id`, `name`, `description`, and `workflow` steps
3. Test via Operator Fleet view or `POST /api/v1/playbooks/run`

## Adding a persona

1. Add `personas/your_persona.yaml` with `id`, `name`, `system_prompt`, `greeting`
2. Set `DEFAULT_PERSONA=your_persona` in `.env`

## Pull requests

- Keep changes focused
- Test locally before submitting
- Update README if you add config or features
- **Agent coherence:** new features must route through `ChatService` or `tools`; update `agent/manifest.yaml` if capabilities change

See [docs/ROADMAP.md](docs/ROADMAP.md) for agent-accretive priorities.

## Code of conduct

Be direct, be kind, no harassment. We're building tools for people who are tired of wasting time on overpriced software.
