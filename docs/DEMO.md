# Music PR Discovery — Golden Demo Path

The flagship OpenWorker workflow for indie artists and small PR agencies: find UK radio pluggers and playlist curators without wasting your Sunday on spreadsheets.

**Playbook:** `pb_music_pr_discovery` (5 template steps, single-sandbox execution today)

---

## Prerequisites

```bash
./scripts/bootstrap.sh
```

Add to `.env`:

```bash
CHAT_API_KEY=sk-...
VISION_API_KEY=sk-...
```

Start the stack:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
# another terminal
cd client && python3 -m http.server 8888
```

---

## Path A — OpenWorker Chat (recommended hero demo)

1. Open http://localhost:8888 → **OpenWorker Chat**
2. Click chip **「UK radio pluggers」** or paste:

   > Research 10 UK indie radio pluggers and playlist curators for an upcoming rock release. Focus on BBC Radio 6 Music, Absolute Radio, and community stations. Save findings as a structured list with contact notes.

3. Watch:
   - Intent routes to **research** or **playbook**
   - Sandbox provisions automatically
   - **Live Desktop** panel streams the agent screen
   - **Action Stream** shows vision steps

4. When complete, session status returns to **Ready**

---

## Path B — Campaign template (Operator tab)

1. Switch to **Operator Fleet**
2. Select **Music PR Discovery (5 steps · single sandbox)**
3. Paste the same prompt
4. Click **Run Campaign Template**
5. Action stream shows `playbook_step_planned` for each JSON step, then vision loop

---

## Path C — CLI (Buzz / automation friendly)

```bash
openworker chat "Find 10 UK indie radio pluggers for a rock release"
openworker playbook run pb_music_pr_discovery \
  --prompt "UK indie rock release — radio pluggers and SubmitHub curators"
```

---

## Path D — One-shot script

```bash
./scripts/demo_music_pr.sh
```

Runs health check → session → chat message → polls until idle. JSON output for CI or Buzz hooks.

---

## Path E — Buzz MCP

Configure `connectors/mcp_server.py` in your Buzz agent harness, then:

```json
{
  "name": "openworker_chat",
  "arguments": {
    "message": "Run music PR discovery for UK indie rock — 10 radio pluggers"
  }
}
```

See [BUZZ.md](BUZZ.md).

---

## What “success” looks like

| Signal | Where |
|--------|--------|
| `intent: playbook` or `research` | Chat response metadata |
| Sandbox `running` | Live Desktop / `GET /api/v1/machines` |
| Action events | Chat side panel or `ws://localhost:8000/ws/actions` |
| Session `idle` | Chat status badge |
| Audit entries | `GET /api/v1/audit` |

---

## Recording a hero clip

1. Run Path A with a real API key
2. Screen-record: chat prompt → live desktop → action stream → completion message
3. Keep it under 90 seconds — show the pain point (“find pluggers”) and the hands (desktop actually working)

Suggested opener: *"Stop wasting 15 hours a week on contact research — tell OpenWorker what you need."*

---

## Scheduled weekly run

`workflows/weekly_music_pr.yaml` auto-imports on server start (604800s interval). Disable with `SCHEDULER_ENABLED=false` if you only want manual runs.
