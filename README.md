# OpenDesktop

> Cloud Desktop Infrastructure & Sandbox Platform for Autonomous AI Agents

OpenDesktop is a provider-agnostic digital employee OS and cloud sandbox platform. It provisions persistent, containerized Linux desktop environments reachable via REST APIs, WebSockets, and a Python SDK, enabling vision-capable AI agents to interact with graphical desktop software, web browsers, and local development tools.

---

## Architecture Overview

```
                      +----------------------------------+
                      |         Web Dashboard / UI       |
                      |   http://localhost:8888 (Client) |
                      +----------------+-----------------+
                                       |
                       HTTP REST & WS  | Live Video Stream &
                       Action Telemetry| Telemetry Feed
                                       v
                      +----------------------------------+
                      |        OpenDesktop Engine        |
                      |     FastAPI Server (:8000)       |
                      | - Remote Sandbox Manager (SSH)   |
                      | - Fleet Orchestrator & Vision    |
                      |   Agent Loop (OpenRouter/OpenAI) |
                      +----------------+-----------------+
                                       |
                     Container Lifecycle| HTTP REST & scrot
                     Control (SSH)     | Screen Capture
                                       v
                      +----------------------------------+
                      |         Hetzner Cloud VPS        |
                      |        (Host: 46.225.66.39)      |
                      |                                  |
                      |  +----------------------------+  |
                      |  | Docker Sandbox Container   |  |
                      |  | - Xvfb (1280x800x24)      |  |
                      |  | - XFCE4 Desktop & noVNC    |  |
                      |  | - Chrome, VS Code, Obsidian|  |
                      |  | - Agent Daemon REST API    |  |
                      |  +----------------------------+  |
                      +----------------------------------+
```

---

## Core Capabilities

- **Isolated Linux Sandboxes**: Provision headless virtual framebuffers (Xvfb 1280x800) with XFCE4 desktop environments, Google Chrome, VS Code, Obsidian, and standard Linux toolchains in isolated Docker containers.
- **Provider-Agnostic Vision Loop**: Vision-driven LLM control loop (Observe -> Think -> Act) supporting OpenRouter, OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), and Google Gemini.
- **Low-Latency Telemetry Streaming**: Stream real-time desktop frame buffers to connected clients via WebSockets (`ws://localhost:8000/ws/stream/{machine_id}`).
- **Declarative Playbook Engine**: Orchestrate multi-step workflow campaigns across specialized machine roles (`ops_machine`, `rpa_machine`, `vault_machine`).
- **Programmatic Control**: High-level Python SDK (`open_desktop`) for machine lifecycle management, navigation, form automation, and execution logging.

---

## Quickstart

### 1. Requirements

- Python 3.10+
- Docker (on host or remote Linux VPS)
- SSH access to Docker host (if running remote deployment)

### 2. Launch Server

```bash
git clone https://github.com/totalaudiopromo/open-desktop.git
cd open-desktop

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt

# Start FastAPI Engine
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Launch Frontend Client

```bash
cd client
python3 -m http.server 8888
```

Access the dashboard at `http://localhost:8888`.

---

## Python SDK Usage (`open_desktop`)

```python
import open_desktop

# Initialize machine handle
machine = open_desktop.Machine("mach_01", api_key="sk_live_opendesktop_...")
session = open_desktop.Session(machine, job_name="Market Research Campaign")

# High-level automation methods
session.open_url("https://www.google.com")
session.fill_form({"q": "OpenDesktop Sandbox Infrastructure"})
session.run_playbook("pb_web_research", prompt="Analyze competitive landscape")

session.finish()
```

---

## API Reference

### Create Sandbox Machine

```http
POST /api/v1/machines
Content-Type: application/json

{
  "name": "Research Node 01",
  "template": "medium"
}
```

### Run Declarative Playbook Campaign

```http
POST /api/v1/playbooks/run
Content-Type: application/json

{
  "playbook_id": "pb_web_research",
  "prompt": "Research 10 market competitors and export structured markdown to Obsidian Vault"
}
```

### Stream Telemetry & Screenshots

```http
GET /api/v1/machines/{machine_id}/screenshot
WS  /ws/stream/{machine_id}
WS  /ws/actions
```

---

## Project Structure

```
open-desktop/
├── client/                     # Web dashboard frontend (HTML/CSS/JS)
│   ├── app.js                  # WebSocket client & DOM manager
│   ├── index.html              # Operator & Developer UI
│   └── styles.css              # Design system & responsive layout
├── server/                     # FastAPI engine & orchestrator
│   ├── agent_runner.py         # LLM vision observe-think-act loop
│   ├── docker_manager.py       # Remote Docker lifecycle & SSH manager
│   ├── main.py                 # REST & WebSocket API router
│   └── orchestrator.py         # Multi-agent campaign coordinator
├── sandbox-engine/             # Sandbox Docker image definition
│   ├── Dockerfile.sandbox      # XFCE4, Chrome, VS Code, Obsidian container
│   ├── agent_daemon.py         # Fast REST control daemon inside sandbox
│   └── entrypoint.sh           # Container init script & Xvfb startup
├── open_desktop/               # Python SDK package
│   └── machine.py              # Client SDK implementation
├── playbooks/                  # Declarative workflow JSON definitions
├── docs/                       # Architecture documentation
└── docker-compose.yml          # Local container orchestration spec
```

---

## License

MIT License.
