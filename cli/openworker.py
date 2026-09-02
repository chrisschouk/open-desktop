#!/usr/bin/env python3
"""
OpenWorker CLI — JSON in, JSON out. Agent-first interface to OpenDesktop.

  openworker chat "Research UK radio pluggers"
  openworker chat "follow up" --session sess_abc
  openworker playbook run pb_music_pr_discovery --prompt "indie rock"
  openworker skills list
  openworker sandboxes list
"""
import argparse
import json
import os
import sys

import requests

API_URL = os.getenv("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", "")


def headers(api_url: str = API_URL):
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


def _url(api_url: str, path: str) -> str:
    return f"{api_url.rstrip('/')}{path}"


def out(data: dict, exit_code: int = 0):
    print(json.dumps(data, indent=2))
    sys.exit(exit_code)


def cmd_chat(args):
    payload = {"message": args.message}
    if args.session:
        payload["session_id"] = args.session
    r = requests.post(_url(args.api_url, "/api/v1/chat"), json=payload, headers=headers(), timeout=120)
    out(r.json(), 0 if r.ok else 1)


def cmd_session_create(args):
    r = requests.post(
        _url(args.api_url, "/api/v1/sessions"),
        json={"persona_id": args.persona or "openworker"},
        headers=headers(),
        timeout=30,
    )
    out(r.json(), 0 if r.ok else 1)


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


def main():
    parser = argparse.ArgumentParser(prog="openworker", description="OpenWorker CLI for OpenDesktop")
    parser.add_argument("--api-url", default=API_URL, dest="api_url", help="OpenDesktop API base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Send a message to OpenWorker")
    chat.add_argument("message", help="User message")
    chat.add_argument("--session", help="Existing session ID")
    chat.set_defaults(func=cmd_chat)

    sess = sub.add_parser("session", help="Session management")
    sess_sub = sess.add_subparsers(dest="session_cmd", required=True)
    create = sess_sub.add_parser("create", help="Create a new session")
    create.add_argument("--persona", default="openworker")
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
