#!/usr/bin/env python3
"""
OpenWorker CLI — JSON in, JSON out. Agent-first interface to OpenDesktop.

  openworker orient
  openworker plan "Research UK radio pluggers"
  openworker chat "Research UK radio pluggers"
  openworker wait sess_abc
  openworker playbook run pb_music_pr_discovery --prompt "indie rock"
"""
import argparse
import json
import os
import sys
import time

import requests

API_URL = os.getenv("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", "")


def headers():
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


def _url(api_url: str, path: str) -> str:
    return f"{api_url.rstrip('/')}{path}"


def out(data, exit_code: int = 0):
    print(json.dumps(data, indent=2))
    sys.exit(exit_code)


def cmd_orient(args):
    r = requests.get(_url(args.api_url, "/api/v1/agent/orient"), headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def cmd_plan(args):
    payload = {"message": args.message}
    if args.session:
        payload["session_id"] = args.session
    if args.force_intent:
        payload["force_intent"] = args.force_intent
    r = requests.post(_url(args.api_url, "/api/v1/agent/plan"), json=payload, headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def cmd_session_create(args):
    payload = {"persona_id": args.persona or "openworker"}
    if getattr(args, "worker", None):
        payload["worker_id"] = args.worker
    r = requests.post(
        _url(args.api_url, "/api/v1/sessions"),
        json=payload,
        headers=headers(),
        timeout=30,
    )
    out(r.json(), 0 if r.ok else 1)


def cmd_workers_list(args):
    r = requests.get(_url(args.api_url, "/api/v1/workers"), headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def cmd_workers_get(args):
    r = requests.get(
        _url(args.api_url, f"/api/v1/workers/{args.worker_id}"),
        headers=headers(),
        timeout=30,
    )
    out(r.json(), 0 if r.ok else 1)


def cmd_workers_create(args):
    r = requests.post(
        _url(args.api_url, "/api/v1/workers"),
        json={
            "name": args.name,
            "avatar": args.avatar or "default",
            "role": args.role or "general",
            "persona_ref": args.persona or "openworker",
        },
        headers=headers(),
        timeout=30,
    )
    out(r.json(), 0 if r.ok else 1)


def cmd_chat(args):
    payload = {"message": args.message}
    if args.session:
        payload["session_id"] = args.session
    if getattr(args, "worker", None):
        payload["worker_id"] = args.worker
    if args.force_intent:
        payload["force_intent"] = args.force_intent
    r = requests.post(_url(args.api_url, "/api/v1/chat"), json=payload, headers=headers(), timeout=120)
    out(r.json(), 0 if r.ok else 1)


def cmd_wait(args):
    deadline = time.time() + args.timeout
    last = None
    while time.time() < deadline:
        r = requests.get(
            _url(args.api_url, f"/api/v1/sessions/{args.session_id}"),
            headers=headers(),
            timeout=30,
        )
        if not r.ok:
            out({"error": r.text, "status_code": r.status_code}, 1)
        last = r.json()
        status = last.get("session", {}).get("status")
        if status in ("idle", "error"):
            code = 0 if status == "idle" else 1
            out({"session_id": args.session_id, "status": status, "session": last}, code)
        time.sleep(args.interval)
    out({"error": "timeout", "session_id": args.session_id, "last": last}, 1)


def cmd_playbook_run(args):
    r = requests.post(
        _url(args.api_url, "/api/v1/playbooks/run"),
        json={"playbook_id": args.playbook_id, "prompt": args.prompt},
        headers=headers(),
        timeout=30,
    )
    out(r.json(), 0 if r.ok else 1)


def cmd_skills_list(args):
    r = requests.get(_url(args.api_url, "/api/v1/skills"), headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def cmd_sandboxes_list(args):
    r = requests.get(_url(args.api_url, "/api/v1/machines"), headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def cmd_workerhub(args):
    r = requests.get(_url(args.api_url, "/api/v1/workerhub"), headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def cmd_manifest(args):
    r = requests.get(_url(args.api_url, "/api/v1/agent/manifest"), headers=headers(), timeout=30)
    out(r.json(), 0 if r.ok else 1)


def main():
    parser = argparse.ArgumentParser(prog="openworker", description="OpenWorker CLI for OpenDesktop")
    parser.add_argument("--api-url", default=API_URL, dest="api_url", help="OpenDesktop API base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    orient = sub.add_parser("orient", help="System snapshot — health, machines, sessions, hub")
    orient.set_defaults(func=cmd_orient)

    plan = sub.add_parser("plan", help="Dry-run intent/tier classification")
    plan.add_argument("message", help="Message to classify")
    plan.add_argument("--session", help="Optional session for history context")
    plan.add_argument("--force-intent", dest="force_intent", help="Override intent")
    plan.set_defaults(func=cmd_plan)

    chat = sub.add_parser("chat", help="Send a message to OpenWorker (enveloped JSON)")
    chat.add_argument("message", help="User message")
    chat.add_argument("--session", help="Existing session ID")
    chat.add_argument("--worker", help="Worker ID (creates chat under worker if no session)")
    chat.add_argument("--force-intent", dest="force_intent", help="Override intent")
    chat.set_defaults(func=cmd_chat)

    wait = sub.add_parser("wait", help="Poll session until idle or error")
    wait.add_argument("session_id", help="Session ID to wait on")
    wait.add_argument("--timeout", type=int, default=300, help="Max seconds (default 300)")
    wait.add_argument("--interval", type=float, default=3.0, help="Poll interval seconds")
    wait.set_defaults(func=cmd_wait)

    manifest = sub.add_parser("manifest", help="Load agent manifest JSON")
    manifest.set_defaults(func=cmd_manifest)

    workers = sub.add_parser("workers", help="Worker roster")
    workers_sub = workers.add_subparsers(dest="workers_cmd", required=True)
    wl = workers_sub.add_parser("list", help="List Workers")
    wl.set_defaults(func=cmd_workers_list)
    wg = workers_sub.add_parser("get", help="Get Worker detail")
    wg.add_argument("worker_id")
    wg.set_defaults(func=cmd_workers_get)
    wc = workers_sub.add_parser("create", help="Create a Worker")
    wc.add_argument("name")
    wc.add_argument("--avatar", default="default")
    wc.add_argument("--role", default="general")
    wc.add_argument("--persona", default="openworker")
    wc.set_defaults(func=cmd_workers_create)

    sess = sub.add_parser("session", help="Session management")
    sess_sub = sess.add_subparsers(dest="session_cmd", required=True)
    create = sess_sub.add_parser("create", help="Create a new session")
    create.add_argument("--persona", default="openworker")
    create.add_argument("--worker", help="Worker ID")
    create.set_defaults(func=cmd_session_create)

    pb = sub.add_parser("playbook", help="Run playbooks")
    pb_sub = pb.add_subparsers(dest="playbook_cmd", required=True)
    run = pb_sub.add_parser("run", help="Run a playbook")
    run.add_argument("playbook_id", help="Playbook ID e.g. pb_web_research")
    run.add_argument("--prompt", required=True, help="Campaign goal")
    run.set_defaults(func=cmd_playbook_run)

    skills = sub.add_parser("skills", help="List skills")
    skills_sub = skills.add_subparsers(dest="skills_cmd", required=True)
    skills_list = skills_sub.add_parser("list")
    skills_list.set_defaults(func=cmd_skills_list)

    sandboxes = sub.add_parser("sandboxes", help="List sandbox machines")
    sb_sub = sandboxes.add_subparsers(dest="sandboxes_cmd", required=True)
    sb_list = sb_sub.add_parser("list")
    sb_list.set_defaults(func=cmd_sandboxes_list)

    hub = sub.add_parser("hub", help="WorkerHub catalog")
    hub.set_defaults(func=cmd_workerhub)

    args = parser.parse_args()
    if not hasattr(args, "api_url"):
        args.api_url = API_URL
    args.func(args)


if __name__ == "__main__":
    main()
