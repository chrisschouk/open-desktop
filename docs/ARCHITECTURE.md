# System Architecture

> Cohesive view of OpenDesktop + OpenWorker as a **control plane** and **compute plane**.
> For agent operation semantics, see [AGENT_SYSTEM.md](AGENT_SYSTEM.md).

---

## 1. Architectural stance

The system is designed as a **two-plane agent stack**:

```
┌──────────────────────────────────────────────────────────────────┐
│                     CONTROL PLANE (Python/FastAPI)                │
│  Sessions · Router · Skills · Playbooks · Scheduler · Audit       │
│  Gateway · Tools · MCP · CLI                                      │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTP (daemon API)
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                     COMPUTE PLANE (Docker sandboxes)              │
│  XFCE · Chrome · VS Code · Obsidian · agent_daemon (screenshot)   │
└──────────────────────────────────────────────────────────────────┘
```

**Control plane** holds truth: who said what, what tier ran, what happened.
**Compute plane** is replaceable: any sandbox can die; sessions and audit survive.

---

## 2. Component map (interconnected, not siloed)

```
                    ┌─────────────┐
   Discord/Telegram │  Gateway    │ Web/CLI/MCP
        ──────────►│  dispatch   │◄──────────
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ ChatService │◄─── Skills (trigger bias)
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ChatAgent   BrowserResearch  PlaybookExecutor
         (T0)            (T1)              │
              │            │                ▼
              │            │         AgentRunner (T2/T3)
              │            │                │
              └────────────┴────────────────┘
                           │
                    ┌──────▼──────┐
                    │SandboxManager│◄── LocalDocker / RemoteSSH
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Sandboxes  │
                    └─────────────┘

Parallel observability: Audit (append-only) · WS Actions · WS Stream
```

Every user-facing path **must** flow through `ChatService` or the **Tool registry** — never bypass the router for "convenience."

---

## 3. Data stores

| Store | File | Contents |
|-------|------|----------|
| Sessions | `data/sessions.db` | sessions, messages, channel_sessions |
| Audit | `data/audit.db` | hash-chained events |
| Schedules | `data/schedules.db` | cron-style jobs |
| Vault | `data/vault/` | agent output files (Obsidian, exports) |
| User skills | `data/skills/` | overlay on bundled `skills/` |

SQLite is intentional: single-node self-host, zero ops burden, agent-readable via API.

---

## 4. Execution paths (unified semantics)

| Path | Entry | Tier | Async? |
|------|-------|------|--------|
| Chat reply | `POST /chat` → intent `chat` | T0 | No |
| Browser research | `POST /chat` → intent `browser` | T1 | No |
| Desktop research | `POST /chat` → intent `research` | T2 | Yes (`working`) |
| RPA / automate | `POST /chat` → intent `automate` | T2 | Yes |
| Playbook template | `POST /chat` → intent `playbook` | T3 | Yes |
| Direct playbook | `POST /playbooks/run` | T3 | Background task |
| Fleet campaign | `POST /orchestrate` | T4* | Background |
| Tool call | `POST /tools/call` | varies | Usually async for playbooks |

\*T4 orchestrator exists; multi-machine fidelity is roadmap.

---

## 5. Sandbox lifecycle

```
create → starting → running → (stop) → stopped
                  ↘ unhealthy / error
```

On **server restart**, `LocalDockerManager.reconcile_from_docker()` rehydrates `opendesktop-*` containers from `docker ps` so agents don't see a false empty fleet.

**Agent implication:** After control-plane restart, call `GET /machines` before assuming no sandboxes exist.

---

## 6. Connector architecture

All connectors are **thin adapters**:

```
External event → normalize {channel, channel_id, message, user_id}
              → gateway.dispatch()
              → same ChatService response as REST
```

No connector-specific routing logic. This keeps agent mental models stable across Discord, Telegram, Buzz MCP, and CLI.

---

## 7. Security boundaries

| Surface | Default | Hardened |
|---------|---------|----------|
| `/chat`, `/sessions` | Open | Reverse proxy + auth (operator choice) |
| `/gateway/dispatch`, `/tools/call` | Open | `OPENDESKTOP_API_TOKEN` Bearer |
| `/keys/set` | Localhost/LAN only | + Bearer when token set |
| Sandboxes | Local Docker | Remote SSH mode (`SANDBOX_MODE=remote`) |

Agents should assume **localhost dev** vs **production token** modes and read `health.api_token_required`.

---

## 8. Modularity contracts

### Skills (`skills/*/SKILL.md`)
- **Input:** user message text
- **Output:** optional playbook bias + injected context string
- **Does not:** execute sandboxes directly

### Playbooks (`playbooks/*.json`)
- **Input:** `playbook_id` + user prompt
- **Output:** enriched vision prompt + step telemetry
- **Does not:** guarantee multi-machine fleet (yet)

### Tools (`server/tools.py`)
- **Input:** JSON arguments per JSON Schema
- **Output:** JSON result
- **Does:** thin wrapper over API internals — stable for MCP

### Workflows (`workflows/*.yaml`)
- **Input:** schedule trigger
- **Output:** scheduler row → playbook or orchestrator prompt
- **Does not:** replace playbooks; imports at startup

---

## 9. Web client role

The browser UI (`client/`) is a **human observability console** — chat, live stream, fleet view. Agents should prefer API/MCP.

Design principle: anything doable in the UI must be doable via `POST /chat` or tools (parity).

---

## 10. Buzz / external agent workspaces

See [BUZZ.md](BUZZ.md). Architecture summary:

- **Buzz** = team relay (messages, git, YAML workflows, coding agents)
- **OpenDesktop** = desktop body via MCP `openworker_chat` + sandbox tools

OpenDesktop does not replace Buzz; it extends agents that need a screen.

---

## 11. Evolution constraints (keep the system coherent)

When adding features, ask:

1. Does it route through `ChatService` or `tools`?
2. Does it respect session mutex?
3. Does it declare a tier (T0–T4)?
4. Does it append to audit?
5. Is it discoverable in `agent/manifest.yaml`?

If any answer is "no," the feature fragments agent legibility.

---

## 12. See also

- [AGENT_SYSTEM.md](AGENT_SYSTEM.md) — agent ontology & control loop
- [AGENT_API.md](AGENT_API.md) — API contracts
- [OPENWORKER.md](OPENWORKER.md) — product-facing summary
- [ROADMAP.md](ROADMAP.md) — what ships next
