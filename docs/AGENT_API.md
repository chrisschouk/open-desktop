# Agent API Contract

> How AI agents should interact with OpenDesktop for **accurate observation** and **minimal token spend**.
> Ontology: [AGENT_SYSTEM.md](AGENT_SYSTEM.md) · Machine catalog: [../agent/manifest.yaml](../agent/manifest.yaml)

---

## 1. Design goals

1. **JSON in, JSON out** — no HTML scraping
2. **Progressive disclosure** — cheap calls first (`health` → `session` → `actions`)
3. **Explicit next steps** — responses should tell the agent what to poll (target envelope)
4. **Session-scoped mutex** — never parallelize desktop work on one session
5. **Tier visibility** — know cost class before escalating

---

## 2. Base URL & auth

```
http://localhost:8000/api/v1
```

| Condition | Header |
|-----------|--------|
| `OPENDESKTOP_API_TOKEN` set | `Authorization: Bearer <token>` on `/gateway/dispatch`, `/tools/call` |
| Local dev | Usually none for `/chat`, `/sessions` |

MCP: `OPENDESKTOP_API_URL` + optional `OPENDESKTOP_API_TOKEN`.

---

## 3. Orientation sequence (run on every cold start)

```bash
openworker orient
# or
curl -s localhost:8000/api/v1/agent/orient
```

Returns health, machines, recent sessions, working count, hub summary, and `next` hints.

Optional dry-run before spending:

```bash
openworker plan "Research UK radio pluggers"
```

**Abort if** `api_key_configured: false` — cannot proceed past T0 without keys.
**Warn if** `docker.available: false` — T2+ will fail.

---

## 4. Session lifecycle (canonical agent loop)

### 4.1 Create or resume

```http
POST /api/v1/sessions
{"persona_id": "openworker"}
→ { "session": { "id": "sess_…", "status": "idle" }, "greeting": "…" }
```

Resume via `session_id` on subsequent `POST /chat` calls.

Channel adapters use `channel_key` mapping internally — agents using REST should keep one `session_id` per task thread.

### 4.2 Send work

```http
POST /api/v1/chat
{"message": "…", "session_id": "sess_…"}
```

**Current response shape** (all `/chat` responses):

```json
{
  "ok": true,
  "trace_id": "tr_…",
  "session_id": "sess_…",
  "intent": "research",
  "tier": "T2",
  "estimated_cost": "high",
  "status": "working",
  "reply": "On it — spinning up a desktop…",
  "observe": {
    "session": "/api/v1/sessions/sess_…",
    "machines": "/api/v1/machines",
    "actions_ws": "ws://localhost:8000/ws/actions"
  },
  "next": ["poll_session", "subscribe_actions"]
}
```

Legacy fields (`session_id`, `intent`, `reply`, `status`) remain at top level for compatibility.

### 4.3 Observe while `working`

```http
GET /api/v1/sessions/sess_…
→ { "session": { "status": "working|idle|error", … }, "messages": […] }
```

Poll every **3–5s**. Stop when `session.status` is `idle` or `error`.

**Prefer** WebSocket for action granularity:

```
ws://localhost:8000/ws/actions
→ {"type":"action","action_type":"click","thought":"…","machine_id":"sbx_…","step":3}
```

### 4.4 Verify & report

Read final assistant messages where `metadata.status` is `completed` or `error`.
Optional: `GET /api/v1/audit?limit=20` for tamper-evident trace.

---

## 5. Intent reference

| Intent | Tier | Sync? | Sandbox? |
|--------|------|-------|----------|
| `chat` | T0 | Yes | No |
| `browser` | T1 | Yes | No |
| `research` | T2 | No | Yes |
| `automate` | T2 | No | Yes |
| `playbook` | T3 | No | Yes |
| `busy` | — | Yes | — (retry later) |

**Agent override (planned):**

```json
{"message": "…", "session_id": "…", "force_intent": "browser"}
```

---

## 6. MCP tools (preferred harness)

Start: `python connectors/mcp_server.py`

| Tool | Use when |
|------|----------|
| `openworker_chat` | Default — full router + session |
| `list_sandboxes` | Orient on fleet |
| `desktop_screenshot` | Debug vision only (expensive) |
| `desktop_click` / `desktop_type` | Manual intervention / recovery |
| `run_playbook` | Skip chat prose; run template directly |

`openworker_chat` arguments:

```json
{
  "message": "Find 10 UK radio pluggers",
  "session_id": "sess_optional",
  "persona_id": "openworker"
}
```

Returns same structure as `POST /chat`.

---

## 7. CLI (scriptable agents)

```bash
openworker chat "message" --session sess_…   # JSON stdout
openworker session create
openworker sandboxes list
openworker skills list
openworker hub
openworker playbook run pb_music_pr_discovery --prompt "…"
```

**Planned:**

```bash
openworker orient          # ✅ shipped
openworker plan "…"        # ✅ shipped
openworker wait sess_…     # ✅ shipped
```

---

## 8. Direct control APIs (use sparingly)

| Endpoint | Agent use case |
|----------|----------------|
| `POST /machines` | Pre-provision before long campaign |
| `POST /machines/{id}/actions` | Recovery when vision stuck |
| `POST /playbooks/run` | Fire-and-forget background (no session ack) |
| `POST /tools/call` | Structured primitive access |

Bypassing `/chat` loses intent routing and session ack semantics — only for tool-first agents.

---

## 9. Error semantics

| HTTP | Meaning | Agent action |
|------|---------|--------------|
| 200 + `status: working` | Async job started | Poll session |
| 200 + `intent: busy` | Mutex held | Wait, poll |
| 404 session | Bad session_id | Create new session |
| 401 | Token required | Add Bearer |
| 403 keys/set | Untrusted origin | Set key in `.env` instead |

---

## 10. Token budget guidelines

| Action | Relative cost |
|--------|---------------|
| `GET /health` | ★☆☆☆☆ |
| `POST /chat` T0 | ★★☆☆☆ |
| `POST /chat` T1 | ★★☆☆☆ |
| `GET /sessions/:id` | ★☆☆☆☆ |
| `WS /actions` | ★★☆☆☆ (low per event) |
| `POST /chat` T2/T3 | ★★★★★ (vision loop) |
| `GET /screenshot` / stream WS | ★★★★★ (avoid) |

---

## 11. Example: complete agent script (music PR)

```bash
# Orient
curl -s localhost:8000/api/v1/health | jq '.api_key_configured, .docker.available'

# Session
SID=$(curl -s -X POST localhost:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"persona_id":"openworker"}' | jq -r '.session.id')

# Act
curl -s -X POST localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"Find 10 UK indie radio pluggers\",\"session_id\":\"$SID\"}"

# Observe until idle
while [ "$(curl -s localhost:8000/api/v1/sessions/$SID | jq -r '.session.status')" = "working" ]; do
  sleep 5
done

# Report
curl -s localhost:8000/api/v1/sessions/$SID | jq '.messages[-1]'
```

Or: `./scripts/demo_music_pr.sh`

---

## 12. Agent-native endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/agent/orient` | ✅ One-call bootstrap |
| `GET /api/v1/agent/manifest` | ✅ Machine-readable catalog |
| `POST /api/v1/agent/plan` | ✅ Dry-run classify |

See [ROADMAP.md](ROADMAP.md) Phase D for MCP resources and streaming.
