# OpenDesktop vs Block Buzz

[Block Buzz](https://github.com/block/buzz) is a self-hostable **team workspace** where humans and AI agents are first-class members of the same channels — built on **Nostr** (signed event log), with YAML workflows, git integration, and ACP/MCP agent harnesses.

OpenDesktop is a **desktop agent platform** — isolated XFCE sandboxes, vision-driven computer use, live screen streaming, and vertical playbooks (music PR, lead gen).

Different products. Complementary infrastructure.

---

## What Buzz is

| Layer | Buzz |
|---|---|
| Core | Nostr relay — every message, reaction, workflow step, git patch is a signed event |
| UX | Slack-like streams, forums, DMs, canvases, search, audit log |
| Agents | `buzz-acp` harness — @mentions in channels → ACP agents (Goose, Codex, Claude Code) |
| Tools | `buzz-dev-mcp` — shell + file editor for coding agents |
| Automation | YAML workflows: `message_posted`, `reaction_added`, `schedule`, `webhook` triggers |
| Remote agents | Disposable compute body (K8s); identity + history live on the relay |
| Stack | Rust monorepo (relay, auth, search, workflow, media, git) + Tauri desktop |

Tagline: *The relay is the workspace.*

---

## What OpenDesktop is

| Layer | OpenDesktop |
|---|---|
| Core | Docker desktop sandboxes (XFCE, Chrome, VS Code, Obsidian) |
| UX | OpenWorker chat + live screen stream + operator fleet view |
| Agents | OpenWorker — intent router (chat / browser / desktop / playbook) |
| Tools | MCP-style registry (`desktop_click`, `run_playbook`, etc.) |
| Automation | JSON playbooks + interval scheduler + Markdown skills |
| Remote agents | Sandbox container = disposable body; sessions on FastAPI control plane |
| Stack | Python FastAPI + vanilla web client |

Tagline: *Open source desktop agent.*

---

## Side-by-side

```
BUZZ                              OPENDESKTOP
────                              ───────────
Team chat + git + workflows       Full GUI desktop + vision loop
Agents as channel members         OpenWorker as chat agent
Nostr signed events               SQLite sessions + action telemetry
Coding agents (ACP + MCP)         Computer-use agents (vision + desktop)
Rust relay is source of truth     FastAPI + Docker sandboxes
Dev teams, incidents, patches     Music PR, lead gen, cross-app RPA
```

---

## Where we overlap

Both treat the **agent identity** as separate from the **compute body**:

- Buzz: keypair + relay history; K8s pod is replaceable ([VISION_REMOTE_AGENTS.md](https://github.com/block/buzz/blob/main/VISION_REMOTE_AGENTS.md))
- OpenDesktop: session memory + vault; Docker sandbox is replaceable

Both have **workflow automation**:

- Buzz: YAML workflows with message/schedule/webhook triggers
- OpenDesktop: JSON playbooks + scheduler + skill triggers

Both expose **agents to messaging**:

- Buzz: native channels, @mentions, `buzz-cli`
- OpenDesktop: Discord/Telegram via gateway dispatch

---

## Where we differentiate (don't compete)

| Buzz owns | OpenDesktop owns |
|---|---|
| Team communication substrate | Visible desktop computer-use |
| Nostr identity + audit + search | Live screen streaming |
| Git patches, CI, code review in-channel | Cross-app GUI automation (forms, legacy UIs) |
| Dev-team incident/branch-as-room stories | Music industry vertical playbooks |
| ACP coding agent harness | Vision observe→act loop on real OS |

**Buzz agents code in repos. OpenWorker works in apps that don't have APIs.**

---

## Infrastructure worth borrowing from Buzz

### 1. Relay-as-workspace pattern → strengthen our gateway

Buzz: all channels flow through one relay with session keys and signed events.

OpenDesktop already has `gateway.dispatch()` — extend toward Buzz's model:

- Channel-scoped session keys (`discord:…`, `telegram:…`, `web:…`)
- Unified audit log for agent actions (even if not full Nostr yet)

### 2. YAML workflow triggers → align playbooks

Buzz workflow triggers:

```yaml
trigger:
  on: message_posted | reaction_added | schedule | webhook
steps:
  - action: send_message | invoke_agent | ...
```

OpenDesktop can add Buzz-compatible trigger shapes to playbooks or a `workflows/` YAML layer alongside JSON fleet playbooks.

### 3. ACP/MCP harness → OpenWorker as Buzz's computer-use body

`buzz-acp` bridges @mentions → coding agents via ACP.

**Shipped:** `connectors/mcp_server.py` exposes OpenDesktop tools over stdio MCP, including:

| Tool | Purpose |
|---|---|
| `openworker_chat` | Full OpenWorker intent routing — chat, browser research, or desktop automation |
| `desktop_click` / `desktop_type` / `desktop_screenshot` | Direct sandbox control |
| `run_playbook` | Declarative campaign playbooks |
| `list_sandboxes` | Fleet status |

Buzz agents call `openworker_chat` when they need a real browser or GUI — coding MCP tools (`buzz-dev-mcp`) stay for repo work.

```json
{
  "mcpServers": {
    "opendesktop": {
      "command": "python",
      "args": ["connectors/mcp_server.py"],
      "env": { "OPENDESKTOP_API_URL": "http://localhost:8000" }
    }
  }
}
```

OpenWorker becomes the **remote body** for non-coding Buzz tasks — same pattern as Buzz remote agents, but desktop-shaped.

### 4. `buzz-cli` JSON in/out → `openworker-cli`

Buzz's agent-first CLI: JSON in, JSON out, no TUI required.

Ship `openworker` CLI:

```bash
openworker chat "Research UK radio pluggers"
openworker playbook run pb_music_pr_discovery --prompt "..."
openworker sandbox screenshot --machine sbx_abc
```

### 5. Signed audit chain → action log integrity

Buzz uses `buzz-audit` hash-chain for tamper-evident logs.

OpenDesktop action telemetry could add hash-chained entries for compliance-sensitive agency workflows.

### 6. Agent directory + job board

Buzz has an Agents surface (directory, jobs). OpenDesktop could publish OpenWorker capabilities as agent profile events if we integrate with Buzz relay.

---

## Integration path (not a fork)

```
Buzz channel @OpenWorker
        ↓
   buzz-acp (or custom harness)
        ↓
   MCP: opendesktop-tools
        ↓
   OpenDesktop API → sandbox + vision loop
        ↓
   Results posted back to Buzz channel (signed events)
```

Buzz stays the **workspace**. OpenDesktop stays the **hands**.

---

## What not to copy

- Full Nostr relay rewrite — wrong stack for our wedge; integrate via API/events instead
- Git/NIP-34 patch flow — unless expanding into dev-team use cases
- Rust monorepo migration — Python/FastAPI is fine for sandbox orchestration
- Competing as team chat — Slack replacement is Buzz's game

---

## Positioning summary

| | Block Buzz | OpenDesktop + OpenWorker |
|---|---|---|
| Analogy | Slack + Forge + agents on Nostr | Self-hosted E2B Desktop + chat |
| User | Engineering teams | Music PR, agencies, indie ops |
| Agent job | Code, review, triage incidents | Browse, research, fill forms, run campaigns |
| Moat | Protocol + community + Block | Vertical playbooks + visible desktop |

**One-liner:** Buzz is where the team talks. OpenDesktop is what the agent does when the task needs a real screen.

---

## Agent system alignment

OpenDesktop is designed as a **legible control stack** for AI agents:

| Buzz concept | OpenDesktop equivalent |
|--------------|------------------------|
| Nostr relay (source of truth) | Control plane (sessions + audit) |
| Remote agent body (K8s pod) | Sandbox (`machine_id`) |
| `buzz-dev-mcp` (code tools) | MCP sandbox tools + `openworker_chat` |
| YAML workflows | `workflows/*.yaml` + playbooks |
| `buzz-cli` JSON I/O | `openworker` CLI + REST envelopes |

**Agent cold start on Buzz:**

1. Load OpenDesktop MCP server
2. Call `openworker_chat` (or read `agent/manifest.yaml` from repo)
3. Orient: `GET /health` via MCP proxy
4. Observe: `ws/actions`, not screenshots

Full agent ontology: [AGENT_SYSTEM.md](AGENT_SYSTEM.md)
