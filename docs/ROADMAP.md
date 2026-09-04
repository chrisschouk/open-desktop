# Roadmap — Agent-Accretive Evolution

> Prioritized by what makes the system **more legible and controllable for AI agents**,
> not by feature count. See [AGENT_SYSTEM.md](AGENT_SYSTEM.md) for the target ontology.

---

## Phase A — Legibility (documentation & manifest) ✅ current PR

**Goal:** Any agent can orient without exploring the codebase.

- [x] `docs/AGENT_SYSTEM.md` — master ontology
- [x] `docs/ARCHITECTURE.md` — cohesive system map
- [x] `docs/AGENT_API.md` — contracts & loops
- [x] `agent/manifest.yaml` — machine-readable catalog
- [x] Cross-link existing docs into the tower

**Success metric:** Agent cold-starts from manifest + orient docs in <2k tokens.

---

## Phase B — Observation API ✅ shipped

**Goal:** One call to understand everything; cheap dry-runs.

| Item | Status |
|------|--------|
| `GET /api/v1/agent/orient` | ✅ |
| `GET /api/v1/agent/manifest` | ✅ |
| `POST /api/v1/agent/plan` | ✅ |
| Response envelope on `/chat` | ✅ `ok`, `trace_id`, `tier`, `observe`, `next` |
| `trace_id` in audit | ✅ `chat_route`, `chat_complete`, `chat_error` |
| `force_intent` on `/chat` | ✅ |

---

## Phase C — CLI parity ✅ shipped

| Command | Status |
|---------|--------|
| `openworker orient` | ✅ |
| `openworker plan "…"` | ✅ |
| `openworker wait sess_…` | ✅ |
| `openworker manifest` | ✅ |
| Enveloped `openworker chat` | ✅ via API |

MCP: `openworker_orient`, `openworker_plan` tools added.

---

## Phase D — MCP depth (Buzz / Cursor native)

| Item | Description |
|------|-------------|
| MCP **resources** | `session://{id}`, `machine://{id}`, `audit://tail` |
| MCP **prompts** | Persona templates as named prompts |
| `openworker_orient` tool | Single call bootstrap |
| Streaming | Partial replies for long T0 chat |

**Success metric:** Buzz agent operates OpenDesktop without reading repo docs.

---

## Phase E — Execution fidelity

| Item | Description |
|------|-------------|
| Playbook **step executor** | Run per-step sub-prompts or parallel machines |
| Fleet T4 | Honest multi-machine `orchestrate` |
| `force_intent` / `force_tier` on `/chat` | Agent override when router wrong |
| Sandbox **affinity** | Session remembers preferred `machine_id` |

**Success metric:** Playbook JSON matches runtime behavior.

---

## Phase F — Accretion marketplace (WorkerHub)

| Item | Description |
|------|-------------|
| Skill/playbook **semver** in manifest | Agents pin versions |
| `workerhub install <id>` | Pull community packages to `data/` |
| Signed packages | Optional hash verification |
| Agent-generated skills | Export successful session → `SKILL.md` draft |

**Success metric:** New verticals ship without core code changes.

---

## Phase G — Worker-centric product model

**Goal:** Organize the product around persistent **Workers** (Grok Bot design primitives), with API parity for the dashboard.

| Item | Description |
|------|-------------|
| Design contract | [DESIGN_PRIMITIVES.md](DESIGN_PRIMITIVES.md) — five primitives, presence, computer levels |
| `worker_id` | Persistent identity; sessions/chats owned by Workers |
| Presence | `idle` / `thinking` / `working` / `waiting` / `blocked` / `done` on Worker + session |
| Computer levels | Status → Preview → Takeover for each Worker’s sandbox |
| Routines | Worker-owned schedules; runs land in Worker transcript |
| Artifacts | Durable outputs + `artifact_ref` message kinds |
| Roster UI | Dashboard default = Worker roster, not machine tabs |

**Success metric:** `openworker orient` returns workers + presence; dashboard opens on a roster; Routine runs appear in transcript without a user prompt.

---

## Non-goals (preserve coherence)

- ❌ Duplicate routing in connectors
- ❌ UI-only features without API parity
- ❌ Nostr relay rewrite (integrate with Buzz instead)
- ❌ Hidden state outside workers/sessions/audit/machines/artifacts

---

## How to prioritize contributions

Ask: **Does this help an agent orient, plan, act, observe, or verify with fewer tokens and fewer mistakes?**

If yes → Phase B–D. If it's human polish only → defer unless it exposes agent APIs.
