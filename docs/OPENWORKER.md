# OpenWorker

OpenWorker is the **reasoning and routing layer** of [OpenDesktop](../README.md).

> **Agents:** Read [AGENT_SYSTEM.md](AGENT_SYSTEM.md) first. This page is a product summary.

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

## Session model

- `POST /api/v1/sessions` → create thread + greeting
- `POST /api/v1/chat` → route message (respect `status: working` mutex)
- `GET /api/v1/sessions/:id` → poll until `idle`

See [AGENT_API.md](AGENT_API.md) for the full loop.

---

## Personas

`personas/*.yaml` — default `openworker`. Tone only; routing unchanged.

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

- [AGENT_SYSTEM.md](AGENT_SYSTEM.md) — ontology
- [ARCHITECTURE.md](ARCHITECTURE.md) — system map
- [DEMO.md](DEMO.md) — music PR golden path
