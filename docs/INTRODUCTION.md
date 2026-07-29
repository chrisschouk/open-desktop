# OpenDesktop – Computers for Digital Employees

> **Instant cloud desktops your AI agents and digital employees can see, control, and operate in under a second.**

OpenDesktop provides a fleet of sandboxed Linux desktop environments, reachable over a clean REST API, WebSockets VNC, and the `open_desktop` Python SDK.

---

## 1. What OpenDesktop Is

- **Persistent Cloud Desktops**: Full Linux userland environments with browser (Chromium), terminal, file system, and GUI desktop ready for agent interaction.
- **Provider-Agnostic Engine**: Drive desktops using any LLM or model provider (Anthropic Claude, OpenAI GPT-4, Google Gemini, Nous Hermes 3).
- **Multi-Machine Fleet Orchestration**: Declarative playbooks that coordinate specialized machines (`research_machine`, `signup_machine`, `vault_machine`).

---

## 2. What OpenDesktop Is Not

- **Not a General Cloud VPS Provider**: OpenDesktop is purpose-built for AI computer-use loops, with high-speed visual screenshot endpoints and isolated display sandboxing (`DISPLAY=:1`).
- **Not an AI Model Provider**: Bring your own LLMs, local weights, or API keys.
- **Not a Browser Extension**: OpenDesktop provides full OS desktop sandboxes, not just headless browser sessions.

---

## 3. Three Primary Usage Patterns

1. **LLM-Driven Desktop Control**: Pass high-resolution screenshots to vision-capable models (e.g. Claude 3.5 Sonnet, Hermes 3) and execute mouse/keyboard actions (`click`, `type`, `press`).
2. **In-Machine Agent Execution**: Deploy agent CLIs and autonomous employees (OpenClaw, Dewey, custom scripts) directly inside the desktop environment.
3. **Continuous Scripting & RPA**: Run automated web form entry, cross-app data synchronization, and dev tools continuously across persistent machines.
