# OpenDesktop Brand Architecture

## Names (locked)

| Name | What it is |
|---|---|
| **OpenDesktop** | Platform, engine, repo, infrastructure (control plane) |
| **OpenWorker** | Conversational product surface — routing, Workers, chats (reasoning layer) |
| **Worker** | Persistent agent with identity, memory, routines, and its own computer |

Tagline: **Open source desktop agent**

“Grok-style” means a **coworker you come back to** (Worker roster + presence + computer), not a disposable chat-history sidebar. See [DESIGN_PRIMITIVES.md](DESIGN_PRIMITIVES.md).

---

## Positioning

- **OpenClaw** — always-on personal operator on your machine
- **OpenHands** — autonomous software engineer
- **OpenDesktop** — self-hosted desktop agent you can *watch* do real work

One-liner: *OpenClaw talks. OpenHands codes. OpenDesktop works — on a screen you can see.*

---

## Agent-centric framing

For AI agents, the brand maps to **layers**:

| Brand term | Agent layer | Artifact |
|------------|-------------|----------|
| OpenDesktop | L0 substrate + compute plane | sandboxes, health, audit |
| OpenWorker | L2 capabilities + L4 channels | chat router, gateway, MCP |
| Worker | Persistent identity + context | roster, presence, routines, affinity |
| Skills | L3 procedures (knowledge) | `skills/*/SKILL.md` |
| Playbooks | L3 procedures (structure) | `playbooks/*.json` |
| Artifacts | Durable outputs | `data/artifacts/`, transcript refs |
| WorkerHub | Discovery registry | `/workerhub` |

Full ontology: [AGENT_SYSTEM.md](AGENT_SYSTEM.md)

---

## Vertical wedge

Music PR, lead gen, web research — ship as **skill + playbook** pairs before touching core code.

---

## Extension model (coherent accretion)

| Layer | Format | Agent discovers |
|---|---|---|
| **Skills** | `skills/*/SKILL.md` | triggers → context + optional playbook_id |
| **Playbooks** | `playbooks/*.json` | step templates; `execution_mode: single_sandbox_template` |
| **Tools** | `server/tools.py` | MCP `tools/list` |
| **Routines / Workflows** | `workflows/*.yaml` + Worker routines API | scheduler import; Worker-owned standing work |
| **Connectors** | `connectors/*.py` | gateway channel names |

**Rule:** New verticals extend L3; they do not fork routing logic.

---

## WorkerHub

Community registry for skills and playbooks. Agents use `GET /api/v1/workerhub` or `openworker hub`.

See [WORKERHUB.md](WORKERHUB.md).

---

## Block Buzz

Buzz = team relay/workspace. OpenDesktop = desktop body.

See [BUZZ.md](BUZZ.md).
