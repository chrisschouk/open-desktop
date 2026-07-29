# OpenDesktop

> Cloud Desktop Infrastructure & Container Sandbox Engine for Autonomous AI Agents

OpenDesktop is an open-source, provider-agnostic container sandbox platform and digital employee OS. It provisions isolated Linux desktop environments reachable via REST APIs, WebSockets, and a Python SDK, enabling vision-capable AI models to observe and control graphical software, web browsers, and local development environments.

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

## Technical Capabilities

- **Isolated Linux Sandboxes**: Headless virtual framebuffers (`Xvfb 1280x800x24`) with XFCE4 desktop environments, Google Chrome, VS Code, Obsidian, Node.js 20, and developer toolchains in isolated Docker containers.
- **Provider-Agnostic Vision Loop**: Multimodal observe-think-act control loop supporting OpenRouter, OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), and Google Gemini.
- **Low-Latency Telemetry Streaming**: Real-time JPEG screenshot stream over WebSockets (`ws://localhost:8000/ws/stream/{machine_id}`) and action event broadcasting (`ws://localhost:8000/ws/actions`).
- **Declarative Playbook Engine**: Workflow orchestrator executing multi-agent campaigns across specialized machine roles (`ops_machine`, `rpa_machine`, `vault_machine`).
- **Programmatic SDK Control**: Native Python SDK (`open_desktop`) for machine lifecycle management, URL navigation, form filling, screenshot capture, and vault synchronization.

---

## Installation & Deployment

### 1. Prerequisites

- Python 3.10+
- Docker (Local host or remote Linux VPS)
- SSH access to Docker host (if deploying remotely)

### 2. Environment Setup

Copy `.env.example` or set environment variables:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export OPENAI_API_KEY="sk-proj-..."
export HETZNER_HOST="46.225.66.39"  # Or local Docker daemon
```

### 3. Launch Backend Engine

```bash
git clone https://github.com/totalaudiopromo/open-desktop.git
cd open-desktop

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt

# Start FastAPI Server
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Launch Web Dashboard Client

```bash
cd client
python3 -m http.server 8888
```

Access the dashboard at `http://localhost:8888`.

---

## Python SDK Usage (`open_desktop`)

```python
import open_desktop

# Connect to cloud desktop sandbox
machine = open_desktop.Machine("mach_01", api_key="sk_live_opendesktop_...")
session = open_desktop.Session(machine, job_name="Market Research Campaign")

# High-level automation methods
session.open_url("https://www.google.com")
session.fill_form({"q": "OpenDesktop Infrastructure"})
session.run_playbook("pb_web_research", prompt="Analyze competitive landscape")

session.finish()
```

---

## REST & WebSocket API Specification

### Provision Machine Sandbox

```http
POST /api/v1/machines
Content-Type: application/json

{
  "name": "Research Node 01",
  "template": "medium"
}
```

### Execute Declarative Fleet Campaign

```http
POST /api/v1/playbooks/run
Content-Type: application/json

{
  "playbook_id": "pb_web_research",
  "prompt": "Research market competitors and export structured markdown to Obsidian Vault"
}
```

### Dynamic API Key Update

```http
POST /api/v1/keys/set
Content-Type: application/json

{
  "api_key": "sk-or-v1-..."
}
```

### WebSocket Streaming Endpoints

```
WS /ws/stream/{machine_id}   # Base64 JPEG frame stream
WS /ws/actions               # Real-time action telemetry feed
```

---

## Project Structure

```
open-desktop/
├── client/                     # Web dashboard frontend (HTML/CSS/JS)
│   ├── app.js                  # WebSocket stream manager & DOM renderer
│   ├── index.html              # Operator & Developer console UI
│   └── styles.css              # Dark mode design system & responsive grid
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
├── docs/                       # System architecture documentation
└── docker-compose.yml          # Local container orchestration spec
```

---

## License

MIT License.
