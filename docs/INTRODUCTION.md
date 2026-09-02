# OpenDesktop System Architecture

> **Open source desktop agent platform — OpenWorker does the talking and the doing.**

OpenDesktop provides isolated, containerized Linux desktop environments. **OpenWorker** is the conversational agent that routes chat vs automation and drives the vision control loop.

---

## 1. Core Architecture

- **OpenWorker Chat Layer**: Intent router (chat / research / automate / playbook) + session memory
- **Persistent Desktop Sandboxes**: XFCE4, Chrome, VS Code, Obsidian in Docker
- **Provider-Agnostic Engine**: Any OpenAI-compatible chat + vision API (OpenAI, Groq, Ollama)
- **Playbook Engine**: Declarative JSON workflows for lead gen, web research, music PR

---

## 2. Platform Positioning

- **Grok-style chat** that actually spins up a desktop when needed
- **Self-hosted** — local Docker by default, optional remote VPS mode
- **Music industry wedge** — built-in PR discovery and lead gen playbooks

---

## 3. Primary Execution Patterns

1. **Chat** — fast LLM, no sandbox (questions, planning)
2. **Vision-Driven Desktop Control** — screenshots → multimodal model → click/type/bash
3. **Playbook Campaigns** — multi-step workflows with fleet orchestration
