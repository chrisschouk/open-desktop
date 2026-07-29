# OpenDesktop Developer Quickstart

Provision persistent desktop sandboxes and automate workflows using the OpenDesktop API and `open_desktop` Python SDK.

---

## Step 1: Launch Server & Client

Start the OpenDesktop REST API server:
```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the frontend web client:
```bash
cd client
python3 -m http.server 8888
```

---

## Step 2: Provision a Cloud Sandbox Machine

Create a machine container via the REST API:
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
session = open_desktop.Session(machine, job_name="B2B Market Research")

# Execute automation methods
session.open_url("https://www.google.com")
session.fill_form({"q": "OpenDesktop Infrastructure"})

# Capture screen buffer
screenshot_bytes = session.see()

session.finish()
```

---

## Step 4: Run Declarative Playbook Campaign

Launch a fleet playbook programmatically:
```bash
curl -X POST http://localhost:8000/api/v1/playbooks/run \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_id": "pb_web_research",
    "prompt": "Research 10 competitors for a B2B SaaS platform and write summary report to Obsidian Vault"
  }'
```
