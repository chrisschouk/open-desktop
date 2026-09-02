"""
OpenWorker chat agent — fast text LLM for conversation (no sandbox).
"""
import os
from typing import List, Optional

import aiohttp

from .config import CHAT_API_KEY, CHAT_API_URL, CHAT_MODEL
from .persona import get_system_prompt


async def chat_reply(
    message: str,
    history: Optional[List[dict]] = None,
    persona_id: str = "openworker",
) -> str:
    api_key = os.getenv("CHAT_API_KEY") or os.getenv("VISION_API_KEY") or CHAT_API_KEY
    if not api_key:
        return (
            "I need an API key to chat. Set CHAT_API_KEY or VISION_API_KEY in your "
            ".env file, or paste one in Settings."
        )

    messages = [{"role": "system", "content": get_system_prompt(persona_id)}]
    if history:
        for m in history:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": os.getenv("CHAT_MODEL", CHAT_MODEL),
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.7,
    }

    url = os.getenv("CHAT_API_URL", CHAT_API_URL)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/totalaudiopromo/open-desktop",
        "X-Title": "OpenDesktop OpenWorker",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    return f"Chat API error ({resp.status}). Check your API key and model settings."
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Couldn't reach the chat API: {e}"
