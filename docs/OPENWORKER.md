# OpenWorker

OpenWorker is the conversational agent layer of [OpenDesktop](../README.md).

## What it does

- **Chat** — fast LLM replies for questions and planning (no sandbox cost)
- **Research** — spins up an isolated Linux desktop, opens Chrome, browses the web
- **Automate** — clicks, types, fills forms via vision-driven control loop
- **Playbooks** — runs pre-built workflows (web research, lead gen, music PR)

## Personas

Personas live in `personas/*.yaml`. Default is `openworker` — direct, capable, no corporate fluff.

Customize tone by editing the YAML or adding your own persona.

## API

```
POST /api/v1/sessions     → create session + greeting
POST /api/v1/chat         → send message (auto-routes intent)
GET  /api/v1/sessions/:id → history + status
GET  /api/v1/personas     → list personas
GET  /api/v1/playbooks    → list playbooks
```

## Discord

See `connectors/discord_bot.py`. Mention the bot or use `!worker <task>`.
