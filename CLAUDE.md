# open-orgo (OpenDesktop + OpenWorker)

FastAPI control plane (`server/`) for Docker desktop sandboxes plus the OpenWorker chat agent. Python >=3.10 (pyproject); remote is `chrisschouk/open-desktop`.

## Commands
- Setup: `python3 -m venv venv && source venv/bin/activate && pip install -r server/requirements.txt` (add `pytest pytest-asyncio pyyaml` for tests; `pip install -e .[dev]` also works per pyproject).
- Config: `cp .env.example .env` (one `OPENROUTER_API_KEY` is enough; see docs/API_KEYS.md).
- Run server: `uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload`; dashboard: `cd client && python3 -m http.server 8888`.
- Docker: `docker compose up -d server dashboard`. The sandbox image is built separately: `docker build -t opendesktop-sandbox:latest -f sandbox-engine/Dockerfile.sandbox sandbox-engine/`.
- Test: `pytest tests/ -q` (asyncio_mode auto; 35 tests, about 1 second).
- CI import smoke check: `python -c "from server.main import app; from server.gateway import dispatch; from server.skills import list_skills_catalog; from server.tools import list_tools"`.
- No linter or type checker is configured.

## Layout
- `server/` API, router, chat, workers, sandbox managers; `cli/openworker.py` CLI; `connectors/` Discord/Telegram/MCP.
- `client/` static dashboard; `sandbox-engine/` image and in-container agent daemon; `open_desktop/` SDK.
- `playbooks/`, `personas/`, `skills/`, `workflows/`: data files loaded at runtime. `docs/AGENT_SYSTEM.md` is the entry doc.

## Gotchas
- `venv/`, `.env` and `data/` are gitignored. Never commit them.
- `SANDBOX_MODE` selects local Docker or remote Hetzner over SSH; set `SANDBOX_ENABLED=false` to fall back to browser research.
- Compose maps `/var/run/docker.sock` into the server container.
