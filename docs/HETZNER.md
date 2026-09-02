# Hetzner remote sandbox

Run desktop automation on your existing Hetzner VPS while keeping the OpenWorker API on your laptop (or another host). No local Docker required.

---

## Overview

```
Your machine (API)  ──SSH──►  Hetzner VPS (Docker sandboxes)
     :8000                         :6500+ VNC, :9500+ daemon
```

Set `SANDBOX_MODE=remote` and point `HETZNER_HOST` at your VPS IP. OpenDesktop provisions sandboxes over SSH.

---

## 1. Prepare the VPS

SSH into your Hetzner box and install Docker:

```bash
ssh root@YOUR_VPS_IP
curl -fsSL https://get.docker.com | sh
```

Open firewall ports for sandbox containers (adjust if you use ufw):

```bash
# VNC/noVNC (6500–6599) and agent daemon (9500–9599) — widen if you run many sandboxes
ufw allow 6500:6599/tcp
ufw allow 9500:9599/tcp
ufw allow 22/tcp
ufw enable
```

Build the sandbox image **on the VPS** (clone the repo or copy `sandbox-engine/`):

```bash
git clone https://github.com/chrisschouk/open-desktop.git
cd open-desktop
docker build -t opendesktop-sandbox:latest -f sandbox-engine/Dockerfile.sandbox sandbox-engine/
docker images | grep opendesktop-sandbox
```

---

## 2. SSH config on your API machine

Add to `~/.ssh/config`:

```
Host hetzner
  HostName YOUR_VPS_IP
  User root
  IdentityFile ~/.ssh/id_ed25519
```

Test:

```bash
ssh hetzner docker info
```

---

## 3. Configure `.env` on your API machine

```bash
SANDBOX_MODE=remote
SANDBOX_ENABLED=true
HETZNER_HOST=YOUR_VPS_IP
SSH_HOST_ALIAS=hetzner
SANDBOX_IMAGE=opendesktop-sandbox:latest

OPENROUTER_API_KEY=sk-or-v1-...
CHAT_MODEL=deepseek/deepseek-v4-flash
VISION_MODEL=google/gemini-2.0-flash-001
```

Start the API:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. Verify

```bash
curl http://localhost:8000/api/v1/health | jq '.sandbox_available, .sandbox_mode, .hetzner_host'
```

Expect `sandbox_available: true` and `sandbox_mode: "remote"`.

Provision a test sandbox:

```bash
curl -X POST http://localhost:8000/api/v1/machines \
  -H "Content-Type: application/json" \
  -d '{"name": "Hetzner-Test"}'
```

---

## No VPS yet? Browser-only mode

If you only want chat + web research (no desktop):

```bash
SANDBOX_ENABLED=false
OPENROUTER_API_KEY=sk-or-v1-...
```

Desktop intents (`research`, `automate`, `playbook`) automatically downgrade to **browser research** (T1) instead of failing.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `sandbox_available: false`, `HETZNER_HOST not set` | Set `HETZNER_HOST` in `.env` |
| SSH permission denied | Check `~/.ssh/config`, keys, and `ssh hetzner docker info` |
| Image not found on VPS | Rebuild `opendesktop-sandbox:latest` on the VPS |
| Sandbox stuck `starting` | Open ports 6500–6599 and 9500–9599 on the VPS firewall |
| Force desktop anyway | Pass `force_intent=research` — skips auto-downgrade |

See also [API_KEYS.md](API_KEYS.md) and [QUICKSTART.md](QUICKSTART.md).
