# OpenDesktop System Architecture

> **Cloud Desktop Infrastructure & Sandbox Engine for Autonomous AI Agents**

OpenDesktop provides a fleet of isolated, containerized Linux desktop environments accessible via REST APIs, WebSockets, and the `open_desktop` Python SDK.

---

## 1. Core Architecture

- **Persistent Desktop Sandboxes**: Full Linux userland environments with XFCE4, Google Chrome, VS Code, Obsidian, terminal tools, and local storage.
- **Provider-Agnostic Engine**: Drive desktops using any vision-capable model provider (Anthropic Claude, OpenAI GPT-4, Google Gemini, OpenRouter).
- **Multi-Machine Fleet Orchestration**: Declarative playbooks that coordinate specialized machine roles (`ops_machine`, `rpa_machine`, `vault_machine`).

---

## 2. Platform Positioning

- **Specialized Computer-Use Sandbox**: Purpose-built for AI computer-use loops with low-latency screenshot streaming and isolated X11 display sandboxing (`DISPLAY=:1`).
- **Full OS Environment**: Supports desktop applications, local binaries, and terminal workflows beyond simple headless browser automation.
- **Decoupled Architecture**: Clean separation between control plane (FastAPI engine) and execution runtime (isolated Docker containers).

---

## 3. Primary Execution Patterns

1. **Vision-Driven Desktop Control**: Pass desktop screenshots to multimodal models and execute precise input events (`click`, `type`, `drag`, `press`).
2. **Autonomous Agent Execution**: Run CLI tools and background workers directly inside the container environment.
3. **Cross-Application Automation**: Automate data transfer across web interfaces and desktop software lacking native REST APIs.
