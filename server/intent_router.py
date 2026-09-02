"""
Intent router — decides whether to chat or spin up desktop automation.
"""
import json
import os
import re
from typing import Literal, Optional

import aiohttp

from .config import CHAT_API_KEY, CHAT_API_URL, CHAT_MODEL

IntentType = Literal["chat", "browser", "research", "automate", "playbook"]

ROUTER_PROMPT = """Classify the user's message into exactly one intent:

- chat: general questions, greetings, planning, clarification — no web or desktop needed
- browser: simple web lookup, quick facts, "what is X" — can use search snippets without a desktop
- research: deep web research needing a real browser desktop (multiple sites, extraction, reports)
- automate: fill forms, click through apps, RPA, sign up, data entry on a desktop
- playbook: user mentions a named workflow (web research, lead gen, music PR, RPA)

Respond with ONLY JSON:
{"intent": "chat|browser|research|automate|playbook", "playbook_id": "pb_..." or null, "task_prompt": "refined task or null"}

If intent is playbook, set playbook_id to one of: pb_web_research, pb_data_entry_rpa, pb_lead_gen_campaign, pb_music_pr_discovery
"""


async def classify_intent(message: str, history: Optional[list] = None) -> dict:
    """Fast LLM classification; falls back to keyword heuristics."""
    api_key = os.getenv("CHAT_API_KEY") or os.getenv("VISION_API_KEY") or CHAT_API_KEY
    if not api_key:
        return _heuristic_classify(message)

    messages = [{"role": "system", "content": ROUTER_PROMPT}]
    if history:
        for m in history[-6:]:
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": os.getenv("CHAT_MODEL", CHAT_MODEL),
        "messages": messages,
        "max_tokens": 150,
        "temperature": 0,
    }

    url = os.getenv("CHAT_API_URL", CHAT_API_URL)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return _heuristic_classify(message)
                data = await resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                return _parse_router_response(text, message)
    except Exception as e:
        print(f"[Router] LLM classify failed: {e}")
        return _heuristic_classify(message)


def _parse_router_response(text: str, original_message: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return _heuristic_classify(original_message)


def _heuristic_classify(message: str) -> dict:
    lower = message.lower()

    playbook_map = {
        "music pr": "pb_music_pr_discovery",
        "lead gen": "pb_lead_gen_campaign",
        "rpa": "pb_data_entry_rpa",
        "data entry": "pb_data_entry_rpa",
        "web research": "pb_web_research",
    }
    for phrase, pb_id in playbook_map.items():
        if phrase in lower:
            return {"intent": "playbook", "playbook_id": pb_id, "task_prompt": message}

    simple_lookup = ["what is", "who is", "when did", "how much", "define ", "quick"]
    if any(w in lower for w in simple_lookup) and not any(w in lower for w in ["fill", "submit", "sign up", "automate"]):
        return {"intent": "browser", "playbook_id": None, "task_prompt": message}

    action_words = [
        "research", "find", "search", "look up", "browse", "open",
        "fill", "submit", "sign up", "download", "scrape", "automate",
        "go to", "navigate", "click", "export",
    ]
    if any(w in lower for w in action_words):
        intent = "automate" if any(w in lower for w in ["fill", "submit", "sign up", "automate", "click"]) else "research"
        return {"intent": intent, "playbook_id": None, "task_prompt": message}

    return {"intent": "chat", "playbook_id": None, "task_prompt": None}
