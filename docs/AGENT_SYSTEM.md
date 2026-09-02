# Agent System — Master Ontology

> **Read this first if you are an AI agent operating OpenDesktop/OpenWorker.**

This document defines the **synthetic system** as one coherent control stack — not a bag of endpoints. Everything else (`ARCHITECTURE.md`, `AGENT_API.md`, `agent/manifest.yaml`) elaborates layers of this tower.

---

## 1. What this system is (one sentence)

**OpenDesktop** is a self-hosted *control plane* for disposable Linux desktops; **OpenWorker** is the *reasoning layer* that routes messages to the cheapest capable executor and maintains session continuity while sandboxes come and go.

---

## 2. The agent's job here

You are not "calling APIs." You are running a **closed-loop controller**:

```
ORIENT → PLAN → ACT → OBSERVE → VERIFY → REPORT
```

| Phase | Goal | Primary surfaces |
|-------|------|------------------|
| **Orient** | Know system health, keys, sandboxes, active sessions | `GET /health`, `agent/manifest.yaml`, `openworker orient` (planned) |
| **Plan** | Pick the cheapest tier that can succeed | Intent router, skills, playbooks, `tier` field |
| **Act** | Execute with idempotent, session-scoped commands | `POST /chat`, tools, playbooks |
| **Observe** | Read state without burning tokens on pixels | Session poll, `ws/actions`, audit |
| **Verify** | Confirm `status: idle` and outcome in messages | `GET /sessions/:id` |
| **Report** | Summarize for human or upstream channel | Reply text + structured metadata |

**Default bias:** observe before you act again; escalate tier only when the cheaper tier failed or is insufficient.

---

## 3. Identity model (what persists vs what is disposable)

Borrowed from Buzz's "relay vs body" pattern — adapted for desktop agents:

```
┌─────────────────────────────────────────────────────────┐
│  PERSISTENT (identity + memory)                         │
│  session_id · channel_key · persona_id · audit chain    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  EPHEMERAL (compute body)                               │
│  machine_id (sandbox) · vision steps · screenshots      │
└─────────────────────────────────────────────────────────┘
```

| Identifier | Lifetime | Meaning |
|------------|----------|---------|
| `session_id` | Until deleted | Conversation thread, status machine, message history |
| `channel_key` | Maps 1:1 to session | `discord:guild:channel`, `telegram:chat:user`, `web:…` |
| `machine_id` | Container lifecycle | Sandbox body — replaceable, not sacred |
| `playbook_id` | Static catalog | Named procedure template |
| `skill_id` | Static catalog | Trigger + instructions, may bind a playbook |
| `trace_id` | Per request (planned) | Correlate chat → actions → audit |

**Agent rule:** Never anchor memory on `machine_id`. Always anchor on `session_id` or `channel_key`.

---

## 4. Abstraction tower (bottom-up)

Each layer only knows the layer below through **narrow contracts**.

```
L4  CHANNELS      gateway · MCP · CLI · Web UI · Buzz harness
      │             Normalize inbound text → dispatch → outbound reply
      ▼
L3  PROCEDURES     playbooks · workflows · skills
      │             Reusable campaign shapes; skills bias routing
      ▼
L2  CAPABILITIES   intents: chat | browser | research | automate | playbook
      │             Router + tier selection
      ▼
L1  PRIMITIVES     tools: openworker_chat · desktop_* · run_playbook · list_sandboxes
      │             MCP-exposed; map 1:1 to control-plane calls
      ▼
L0  SUBSTRATE      sessions · messages · machines · audit · health · schedules
```

**Legibility rule:** An agent should be able to operate the entire system from **L1 + L0** alone. L2–L4 are conveniences that save tokens and reduce error.

---

## 5. Resource tiers (minimize spend)

Always prefer the **lowest tier** that satisfies the user goal.

| Tier | Name | Cost driver | When to use |
|------|------|-------------|-------------|
| **T0** | `chat` | Small LLM call | Q&A, planning, clarification, no live facts |
| **T1** | `browser` | Search snippets + small LLM | Quick facts, definitions, single-source lookup |
| **T2** | `research` | Sandbox + vision loop | Multi-site research, extraction, reports needing GUI |
| **T3** | `playbook` | T2 + template metadata | Vertical campaigns (music PR, lead gen) |
| **T4** | `fleet` | Multi-sandbox (roadmap) | Parallel machines — not production yet |

**Escalation ladder:** T0 → T1 → T2 → T3. Never jump to T2 for "what is X?"

**Override (planned):** `POST /chat` with `force_intent` or `force_tier` for agents that already classified locally.

---

## 6. Session state machine

Every `session_id` is a finite state machine. Respect it — do not send concurrent work messages while `working`.

```
                    ┌──────────┐
         create     │   idle   │◄────────────────┐
        ──────────► │          │                 │
                    └────┬─────┘                 │
                         │ user message           │
                         │ (T0/T1 sync)           │
                         ├────────────────────────┤
                         │ async task (T2/T3)     │
                         ▼                        │
                    ┌──────────┐   complete/error │
                    │ working  │─────────────────┘
                    └──────────┘
```

| Status | Agent behavior |
|--------|----------------|
| `idle` | Safe to send new `POST /chat` |
| `working` | Poll `GET /sessions/:id`; subscribe `ws/actions`; do **not** send another task |
| `error` | Read last assistant message metadata; consider tier downgrade or human escalation |

Acquisition is atomic (`try_acquire_session`) — trust the server, not local assumptions.

---

## 7. Observation strategy (token-efficient)

**Do not** pull screenshots unless debugging vision coordinates. Prefer:

1. **`GET /api/v1/health`** — keys, docker, machine counts (~50 tokens)
2. **`GET /api/v1/sessions/:id`** — status + last N messages
3. **`GET /api/v1/machines`** — sandbox status URLs (not frames)
4. **`WS /ws/actions`** — step events (`thought`, `action_type`, `machine_id`)
5. **`GET /api/v1/audit`** — tamper-evident history for compliance/debug
6. **`WS /ws/stream/:id`** — **expensive**; human demo only

**Polling cadence:** 3–5s for session status while `working`; back off to 10s after 2 min.

---

## 8. Action surfaces (pick one harness)

All paths converge on `chat_service.handle_message` or tool registry.

| Harness | Agent-ergonomic? | Notes |
|---------|------------------|-------|
| **MCP** (`connectors/mcp_server.py`) | ★★★★★ | `openworker_chat` = full router; best for Buzz/Cursor |
| **CLI** (`openworker`) | ★★★★☆ | JSON stdout; scriptable |
| **REST** `/api/v1/chat` | ★★★★☆ | Universal; pair with session poll |
| **Gateway** `/api/v1/gateway/dispatch` | ★★★☆☆ | Multi-channel; needs Bearer if token set |
| **Web UI** | ★☆☆☆☆ | Human demo; avoid for agents |

**Golden path for agents:** MCP `openworker_chat` or CLI `openworker chat` with `--session`.

---

## 9. Extension model (how the system grows)

| Artifact | Location | Agent discovers via |
|----------|----------|---------------------|
| **Skill** | `skills/*/SKILL.md` | `/skills`, `/workerhub`, skill match on message |
| **Playbook** | `playbooks/*.json` | `/playbooks`, `/workerhub` |
| **Workflow** | `workflows/*.yaml` | Scheduler import at startup |
| **Tool** | `server/tools.py` registry | `/tools`, MCP `tools/list` |
| **Persona** | `personas/*.yaml` | `/personas` |
| **Connector** | `connectors/*.py` | Gateway channel name |

**Accretion principle:** New verticals ship as **skill + playbook** first; only promote to tool or core router when the pattern stabilizes.

---

## 10. Coherence rules (system invariants)

1. **Single routing brain** — `intent_router` + `chat_service`; no duplicate classification in connectors.
2. **Sessions are mutex** — one async desktop job per session.
3. **Sandboxes are cattle** — create, use, stop; reconcile on restart (`reconcile_from_docker`).
4. **Honest templates** — playbooks declare `execution_mode: single_sandbox_template` until fleet lands.
5. **Audit appends** — hash-chained; never mutate history.
6. **Keys are unified** — `OPENROUTER_API_KEY` feeds chat + vision unless split intentionally.
7. **Agent envelope (target)** — every mutating response should eventually include `observe` + `next` hints (see `AGENT_API.md`).

---

## 11. Failure modes & recovery

| Symptom | Likely cause | Agent action |
|---------|--------------|--------------|
| `api_key_configured: false` | Missing `.env` | Stop; ask human for `OPENROUTER_API_KEY` |
| `docker.available: false` | Docker down | T0/T1 only; cannot T2+ |
| `status: working` stuck | Vision loop hung | Poll audit/actions; timeout → report; optional sandbox restart |
| `intent: busy` | Concurrent message | Wait; poll session |
| 401 on gateway/tools | `OPENDESKTOP_API_TOKEN` set | Add `Authorization: Bearer` |
| Empty screenshot stream | Machine not `running` | `POST /machines` or wait for health |

---

## 12. Related documents

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Control plane vs compute plane, component map |
| [AGENT_API.md](AGENT_API.md) | REST/MCP contracts, envelopes, examples |
| [../agent/manifest.yaml](../agent/manifest.yaml) | Machine-readable capability catalog |
| [ROADMAP.md](ROADMAP.md) | Agent-accretive implementation phases |
| [BUZZ.md](BUZZ.md) | Workspace integration (Buzz = relay, OpenDesktop = hands) |
| [API_KEYS.md](API_KEYS.md) | Credential model |

---

## 13. Mental model (keep in context window)

```
User message
    → Gateway/CLI/MCP (normalize)
    → Session (memory + mutex)
    → Router (tier pick)
    → Executor (chat | browser | vision | playbook)
    → Sandbox (optional body)
    → Actions WS + Audit (observe)
    → Session idle (verify)
    → Reply (report)
```

You are the driver. The system is the vehicle. **Orient on L0, plan on L2, act on L1, observe on WS/audit, never confuse the body for the driver.**
