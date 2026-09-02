# Contributing to OpenDesktop

Thanks for helping build the open source desktop agent stack.

## Getting started

1. Fork and clone the repo
2. `cp .env.example .env` and add API keys
3. Build the sandbox image: `docker build -t opendesktop-sandbox:latest -f sandbox-engine/Dockerfile.sandbox sandbox-engine/`
4. Run the server: `uvicorn server.main:app --reload`
5. Run the client: `cd client && python3 -m http.server 8888`

## Project structure

- `server/` — FastAPI engine, OpenWorker chat, vision agent
- `client/` — Web UI (chat + operator fleet view)
- `personas/` — OpenWorker personality YAML files
- `playbooks/` — Declarative workflow JSON
- `connectors/` — Discord and future channel bots
- `sandbox-engine/` — Docker desktop image
- `open_desktop/` — Python SDK

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

## Code of conduct

Be direct, be kind, no harassment. We're building tools for people who are tired of wasting time on overpriced software.
