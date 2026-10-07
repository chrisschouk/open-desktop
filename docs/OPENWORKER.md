# OpenWorker

OpenWorker is the **reasoning and routing layer** of [OpenDesktop](../README.md).

> **Agents:** Read [AGENT_SYSTEM.md](AGENT_SYSTEM.md) first. This page is a product summary.
> **Design:** [DESIGN_PRIMITIVES.md](DESIGN_PRIMITIVES.md) — Workers, chats, prompts, tools, artifacts.

The main object in the product is a **Worker** (persistent agent), not a chat history. Chats belong to Workers. Sandboxes are each Worker’s computer — glance via preview, or take over when needed.

---

## What it does (capability tiers)

| Tier | Mode | What happens |
|------|------|----------------|
| T0 | **Chat** | Fast LLM — questions, planning, no sandbox cost |
| T1 | **Browser** | Search snippets + LLM — quick facts without a desktop |
| T2 | **Research / Automate** | Vision loop on a Linux sandbox — real browsing, forms, RPA |
| T3 | **Playbook** | T2 guided by a campaign template (music PR, lead gen, etc.) |

The intent router picks the **lowest tier** that can satisfy the request.

---

## Agent entry points

| Harness | Command / path |
|---------|----------------|
| MCP (preferred) | `openworker_chat` via `connectors/mcp_server.py` |
| CLI | `openworker chat "…"` |
| REST | `POST /api/v1/chat` |
| Gateway | `POST /api/v1/gateway/dispatch` |

All paths converge on `ChatService` — same semantics everywhere.

---

## Worker + session model

- `GET/POST /api/v1/workers` → roster; default Worker is seeded from the `openworker` persona
- `POST /api/v1/workers/:id/chats` (or `POST /api/v1/sessions` with `worker_id`) → create chat + greeting
- `POST /api/v1/chat` → route message (respect `status: working` mutex; presence updates on the Worker)
- `GET /api/v1/sessions/:id` → poll until `idle`
- `GET/POST /api/v1/workers/:id/routines` → standing work that can start without a prompt

See [AGENT_API.md](AGENT_API.md) for the full loop.

---

## Personas → Workers

`personas/*.yaml` define tone and greeting. On startup, OpenDesktop ensures a default **Worker** (`wrk_openworker`) from the `openworker` persona. Additional Workers can share tools/skills while keeping separate memory and routines.

---

## Extensions

| Type | Location | Discovery |
|------|----------|-------------|
| Skills | `skills/*/SKILL.md` | `/skills`, WorkerHub |
| Playbooks | `playbooks/*.json` | `/playbooks` |
| Tools | MCP + `/tools` | `agent/manifest.yaml` |

---

## Discord / Telegram

Thin adapters → `gateway.dispatch()`. See `connectors/`.

---

## See also

- [DESIGN_PRIMITIVES.md](DESIGN_PRIMITIVES.md) — Workers, presence, computer levels
- [AGENT_SYSTEM.md](AGENT_SYSTEM.md) — ontology
- [ARCHITECTURE.md](ARCHITECTURE.md) — system map
- [DEMO.md](DEMO.md) — music PR golden path
