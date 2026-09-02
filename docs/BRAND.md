# OpenDesktop Brand Architecture

## Names (locked)

| Name | What it is |
|---|---|
| **OpenDesktop** | Platform, engine, repo, infrastructure |
| **OpenWorker** | Conversational agent — chat UI, personas, connectors |

Tagline: **Open source desktop agent**

## Positioning

- **OpenClaw** — always-on personal operator on your machine
- **OpenHands** — autonomous software engineer
- **OpenDesktop** — self-hosted desktop agent you can *watch* do real work

One-liner: *OpenClaw talks. OpenHands codes. OpenDesktop works — on a screen you can see.*

## Vertical wedge

Music PR, lead gen, web research — packaged as **Skills** (Markdown) and **Playbooks** (JSON).

## Extension model (borrowed from OpenClaw)

| Layer | Format | Purpose |
|---|---|---|
| **Skills** | `skills/*/SKILL.md` | Teach OpenWorker how (triggers + instructions) |
| **Playbooks** | `playbooks/*.json` | Fleet orchestration steps |
| **Tools** | `GET /api/v1/tools` | MCP-style sandbox/playbook tools |
| **Connectors** | `connectors/*.py` | Discord, Telegram → gateway dispatch |

## Future: WorkerHub

Community registry for skills and playbooks (ClawHub-style, vertical-first).

## Related: Block Buzz

For comparison with [Block Buzz](https://github.com/block/buzz) (team workspace on Nostr) and integration opportunities, see [BUZZ.md](BUZZ.md).

Buzz = relay/workspace. OpenDesktop = desktop body for tasks that need a screen.
