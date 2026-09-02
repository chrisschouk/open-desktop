"""
Browser-light research — fast web lookup without vision sandbox (cheap tier).
"""
import re
from html import unescape
from typing import Optional

import aiohttp

from .chat_agent import chat_reply
from .skills import skills_context_for_message


async def _fetch_ddg_snippets(query: str, max_results: int = 5) -> str:
    """Fetch search result snippets from DuckDuckGo HTML (no API key)."""
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "OpenDesktop-OpenWorker/1.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={"q": query},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text()
    except Exception as e:
        print(f"[BrowserResearch] Search failed: {e}")
        return ""

    snippets = []
    for block in re.findall(r'class="result__snippet"[^>]*>([^<]+)', html):
        text = unescape(re.sub(r"<[^>]+>", "", block)).strip()
        if text:
            snippets.append(text)
        if len(snippets) >= max_results:
            break

    titles = re.findall(r'class="result__a"[^>]*>([^<]+)', html)
    lines = []
    for i, snippet in enumerate(snippets):
        title = unescape(titles[i]).strip() if i < len(titles) else f"Result {i+1}"
        lines.append(f"- **{title}**: {snippet}")
    return "\n".join(lines)


async def browser_research(task: str, persona_id: str = "openworker") -> str:
    """
    Cheap research path: web snippets + chat LLM synthesis. No desktop sandbox.
    """
    snippets = await _fetch_ddg_snippets(task)
    skill_ctx = skills_context_for_message(task)

    if not snippets:
        prompt = (
            f"{skill_ctx}\n\nUser research task: {task}\n\n"
            "No live search results were retrieved. Answer from general knowledge "
            "but clearly state what you could not verify live."
        )
        return await chat_reply(prompt, [], persona_id)

    prompt = (
        f"{skill_ctx}\n\n"
        f"User research task: {task}\n\n"
        f"Live web snippets:\n{snippets}\n\n"
        "Synthesize a concise, actionable answer. Cite which snippets you used. "
        "If the snippets are thin, say what's missing and suggest a full desktop research run."
    )
    return await chat_reply(prompt, [], persona_id)
