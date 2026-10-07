# Design Primitives — Worker-Centric OpenDesktop

> Product language for persistent agents. Inspired by [Designing Grok Bot](https://x.ai/news/designing-grok-bot), adapted to OpenDesktop / OpenWorker brand.

OpenDesktop is the compute substrate. **OpenWorker** is the product surface. The persistent agent people work with is a **Worker** — not a disposable chat session.

---

## Five primitives

| Primitive | Meaning | Ownership |
|-----------|---------|-----------|
| **Worker** | Persistent agent with identity, memory, runtime affinity, and tools | First-class; organizes the product |
| **Chat** | Conversational interface for working with a Worker | Belongs to a Worker |
| **Prompt** | Context or instructions — one-shot, saved as a Skill, or triggered as a Routine | Continuum |
| **Tool** | Access to information and action (APIs, shell, computer use, MCP) | Account-level (shared) |
| **Artifact** | Durable outputs Workers create or modify (files, reports, screenshots) | Referenced from chats |

Everything else (models, context windows, sandboxes, system prompts) stays beneath the interface until the user has a reason to care.

### Capabilities vs context

- **Shared (account):** tools, skills catalog, playbooks, connectors
- **Per-Worker:** memory, routines, chat history, sandbox affinity, presence

```
Account ── Tools · Skills · Playbooks
              │
Worker ──── Identity · Memory · Routines · Chats · Affinity
              │
          machine_id (ephemeral body)
```

---

## Presence

A Worker roster must answer: who is this, what are they doing, how much do I need to know?

| Presence | Trigger | UI |
|----------|---------|-----|
| `idle` | No active work | Calm avatar |
| `thinking` | T0/T1 in flight | Subtle motion |
| `working` | T2/T3 vision / sandbox loop | Active motion + computer status tint |
| `waiting` | Needs human / takeover offered | Attention motion |
| `blocked` | Error or permission failure | Blocked state |
| `done` | Task complete, awaiting ack | Settle / done pulse |

Avatar motion carries lifecycle. Hover reveals `current_action` (from the action stream). Do not use a permanent prose ticker as the primary status.

---

## Computer access levels

Each Worker has its own computer (sandbox). The interface provides three levels so users can enter the workspace without being drawn into operating it:

| Level | Behavior |
|-------|----------|
| **Status** | Accent on Worker / header when the computer is active |
| **Preview** | Opt-in pinned side panel — watch without leaving the chat |
| **Takeover** | Full-screen computer; user controls; then hand back to the Worker |

Default bias: do **not** encourage continuous supervision. Preview is collapsed unless opened. Action Stream folds into presence hover / optional debug.

---

## Heterogeneous transcript

Messages carry a `kind`. Conversation, system events, interactive objects, and visualizations share one timeline.

| Kind | Use |
|------|-----|
| `text` | Prose |
| `event` | Routine created, playbook started, Worker-to-Worker ping |
| `widget` | Email draft, confirmation card, task board |
| `artifact_ref` | Link to a durable artifact |
| `computer_status` | Sandbox started / step summary |

---

## Routines

Routines are Worker-owned standing responsibilities (schedule or event). They appear in the Worker’s main interface; runs land in that Worker’s transcript. A prompt can start work — so can a schedule, an event, or another Worker.

---

## Soft limits

| Limit | Value | Why |
|-------|-------|-----|
| Workers per account | ~50 | Roster must stay scannable |
| Workers per group chat | ~6 | Coordination without dispatcher UI |

---

## Disappearing interface

Prefer delegation over management chrome:

- No always-visible machine tab bar for chat users
- Operator Fleet and Developer Console are power-user surfaces
- One settings path for API keys
- Presence + computer levels replace dense fleet dispatch as the default path

---

## See also

- [AGENT_SYSTEM.md](AGENT_SYSTEM.md) — identity model (`worker_id`, `session_id`, `machine_id`)
- [OPENWORKER.md](OPENWORKER.md) — product summary
- [BRAND.md](BRAND.md) — naming
- [ROADMAP.md](ROADMAP.md) — Phase G
