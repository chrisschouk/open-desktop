# OpenDesktop – Computers for Digital Employees

> **Instant cloud desktops your AI agents and digital employees can see, control, and operate in under a second.**

OpenDesktop is an open, provider-agnostic Digital Employee OS. It provisions persistent Linux desktop sandboxes reachable over a REST API, WebSockets VNC, and the `open_desktop` Python SDK.

---

## 🌟 Core Feature Architecture

- **Persistent Cloud Desktops**: Full Linux userland environments with Chromium Browser, terminal, file system, and GUI desktop.
- **Provider-Agnostic Engine**: Drive desktops using Anthropic Claude 3.5, OpenAI GPT-4, Google Gemini, or Nous Hermes 3.
- **Declarative Playbook Engine**: Coordinate specialized machines (`ops_machine`, `support_machine`, `rpa_machine`) across multi-agent campaigns.
- **Obsidian Second Brain Integration**: Automatically write structured research reports, credentials, and daily notes to Markdown vaults.
- **60FPS Real-Time Fleet Dashboard**: 2x2 multi-screen grid for monitoring 4 cloud machines operating simultaneously.

---

## 📦 Quickstart

### 1. Install & Launch Server
```bash
python3 server/main.py
```

### 2. Python SDK Usage (`open_desktop`)
```python
import open_desktop

machine = open_desktop.Machine("mach_01", api_key="sk_live_opendesktop_...")
session = open_desktop.Session(machine, job_name="B2B Market Intelligence")

# Higher-order flow helpers
session.open_url("https://www.google.com")
session.fill_form({"q": "OpenDesktop Digital Employee OS"})
session.run_playbook("pb_web_research", prompt="Analyze 10 B2B SaaS competitors")

session.finish()
```

### 3. Declarative Fleet Playbook Dispatch
```bash
curl -X POST http://localhost:8000/api/v1/playbooks/run \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_id": "pb_web_research",
    "prompt": "Research 10 B2B SaaS competitors and write summary report to Obsidian Vault"
  }'
```

---

## 📖 Documentation & Guides

- [Introduction & Positioning Guide](docs/INTRODUCTION.md)
- [Developer Quickstart](docs/QUICKSTART.md)
- [Walkthrough Artifact](file:///Users/chrisschofield/.gemini/antigravity/brain/7f2b2e85-5687-4fd1-803c-592e5f1edf51/walkthrough.md)
