# OpenDesktop Brand Architecture

## Names (locked)

| Name | What it is |
|---|---|
| **OpenDesktop** | Platform, engine, repo, infrastructure (control plane) |
| **OpenWorker** | Conversational agent — routing, sessions, personas (reasoning layer) |

Tagline: **Open source desktop agent**

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
| Skills | L3 procedures (knowledge) | `skills/*/SKILL.md` |
| Playbooks | L3 procedures (structure) | `playbooks/*.json` |
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
| **Workflows** | `workflows/*.yaml` | scheduler import |
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
