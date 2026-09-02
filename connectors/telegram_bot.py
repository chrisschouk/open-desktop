#!/usr/bin/env python3
"""
OpenWorker Telegram connector — routes through the OpenDesktop gateway.

Usage:
  export TELEGRAM_BOT_TOKEN=...
  export OPENDESKTOP_API_URL=http://localhost:8000
  python connectors/telegram_bot.py
"""
import os
import asyncio
import aiohttp

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_URL = os.getenv("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
API_BASE = f"https://api.telegram.org/bot{TOKEN}"
API_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", "")


def _headers():
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


async def dispatch(chat_id: str, user_id: str, message: str) -> dict:
    payload = {
        "channel": "telegram",
        "channel_id": chat_id,
        "user_id": user_id,
        "message": message,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/api/v1/gateway/dispatch",
            json=payload,
            headers=_headers(),
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            return await resp.json()


async def send_message(chat_id: str, text: str):
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{API_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
        )


async def poll_updates(offset: int = 0):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/getUpdates",
            params={"offset": offset, "timeout": 30},
            timeout=aiohttp.ClientTimeout(total=35),
        ) as resp:
            data = await resp.json()
            return data.get("result", [])


async def main():
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN")
        return
    print(f"OpenWorker Telegram → OpenDesktop gateway ({API_URL})")
    offset = 0
    while True:
        try:
            updates = await poll_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message") or update.get("edited_message")
                if not msg or "text" not in msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                user_id = str(msg["from"]["id"])
                text = msg["text"].strip()
                if not text:
                    continue
                result = await dispatch(chat_id, user_id, text)
                await send_message(chat_id, result.get("reply", "…"))
                if result.get("status") == "working":
                    await send_message(chat_id, "Desktop sandbox running — check OpenDesktop for live screen.")
        except Exception as e:
            print(f"[Telegram] Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
