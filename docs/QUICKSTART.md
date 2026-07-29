# OpenDesktop Developer Quickstart

Learn how to provision a persistent desktop machine and automate tasks using the `open_desktop` Python SDK in under 5 minutes.

---

## Step 1: Install & Launch Engine

Start the OpenDesktop REST server on port 8000:
```bash
python3 server/main.py
```

---

## Step 2: Provision a Cloud Machine

Create a machine using the `medium` template:
```bash
curl -X POST http://localhost:8000/api/v1/machines \
  -H "Content-Type: application/json" \
  -d '{"name": "Research-Worker-01", "template": "medium"}'
```

---

## Step 3: Operate Machine via Python SDK

```python
import open_desktop

# Connect to cloud desktop sandbox
machine = open_desktop.Machine("mach_01", api_key="sk_live_opendesktop_...")
session = open_desktop.Session(machine, job_name="B2B Research Task")

# Execute higher-order flow helpers
session.open_url("https://www.google.com")
session.fill_form({"q": "OpenDesktop Digital Employee OS"})

# Capture screen screenshot
screenshot_bytes = session.see()

# Finish session
session.finish()
```

---

## Step 4: Run a Declarative Multi-Machine Fleet Playbook

Launch a 4-machine fleet campaign programmatically:
```bash
curl -X POST http://localhost:8000/api/v1/playbooks/run \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_id": "pb_web_research",
    "prompt": "Research 10 competitors for a B2B SaaS platform and write summary to Obsidian Vault"
  }'
```
