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

## Phase B — Observation API (low implementation, high agent value)

**Goal:** One call to understand everything; cheap dry-runs.

| Item | Description |
|------|-------------|
| `GET /api/v1/agent/orient` | `{ health, machines[], active_sessions[], hub_summary }` |
| `GET /api/v1/agent/manifest` | JSON export of `agent/manifest.yaml` |
| `POST /api/v1/agent/plan` | `{ message }` → `{ intent, tier, playbook_id, estimated_cost }` no side effects |
| Response envelope | Add `observe`, `next`, `tier` to `/chat` responses |
| `trace_id` | Correlate chat → actions → audit entries |

**Success metric:** Agent never polls screenshot WS for status.

---

## Phase C — CLI parity (`openworker` as agent shell)

| Command | Behavior |
|---------|----------|
| `openworker orient` | Pretty JSON orient snapshot |
| `openworker plan "…"` | Dry-run router |
| `openworker wait sess_…` | Block until idle; exit 0/1 |
| `openworker chat --json-envelope` | Full target response shape |

**Success metric:** Shell scripts replace ad-hoc curl loops.

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

## Non-goals (preserve coherence)

- ❌ Duplicate routing in connectors
- ❌ UI-only features without API parity
- ❌ Nostr relay rewrite (integrate with Buzz instead)
- ❌ Hidden state outside sessions/audit/machines

---

## How to prioritize contributions

Ask: **Does this help an agent orient, plan, act, observe, or verify with fewer tokens and fewer mistakes?**

If yes → Phase B–D. If it's human polish only → defer unless it exposes agent APIs.
