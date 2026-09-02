#!/usr/bin/env python3
"""
OpenWorker Discord connector — run alongside the OpenDesktop server.

Usage:
  export DISCORD_BOT_TOKEN=...
  export OPENDESKTOP_API_URL=http://localhost:8000
  python connectors/discord_bot.py
"""
import os
import asyncio
import aiohttp

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("Install discord.py: pip install discord.py")
    raise

API_URL = os.getenv("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# channel_id -> session_id mapping
sessions: dict[int, str] = {}


async def chat_with_openworker(session_id: str | None, message: str) -> dict:
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/api/v1/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            return await resp.json()


@bot.event
async def on_ready():
    print(f"OpenWorker Discord bot logged in as {bot.user}")


@bot.command(name="worker")
async def worker_cmd(ctx, *, prompt: str = ""):
    """Talk to OpenWorker: !worker research UK indie radio pluggers"""
    if not prompt:
        await ctx.reply("Usage: `!worker <your task or question>`")
        return

    await ctx.trigger_typing()
    channel_id = ctx.channel.id
    session_id = sessions.get(channel_id)

    try:
        result = await chat_with_openworker(session_id, prompt)
        sessions[channel_id] = result.get("session_id", session_id)
        reply = result.get("reply", "No response")
        status = result.get("status", "idle")

        embed = discord.Embed(description=reply[:4000], color=0x3b82f6)
        embed.set_author(name="OpenWorker", icon_url=bot.user.display_avatar.url)
        embed.set_footer(text=f"Status: {status} | Intent: {result.get('intent', '—')}")
        await ctx.reply(embed=embed)

        if status == "working":
            await ctx.send(
                "Desktop sandbox is running — check the OpenDesktop dashboard for the live screen feed."
            )
    except Exception as e:
        await ctx.reply(f"Couldn't reach OpenDesktop API at `{API_URL}`: {e}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user.mentioned_in(message) and not message.mention_everyone:
        text = message.content
        for mention in message.mentions:
            text = text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
        text = text.strip()
        if text:
            await message.channel.trigger_typing()
            session_id = sessions.get(message.channel.id)
            try:
                result = await chat_with_openworker(session_id, text)
                sessions[message.channel.id] = result.get("session_id", session_id)
                await message.reply(result.get("reply", "…")[:2000])
            except Exception as e:
                await message.reply(f"OpenWorker error: {e}")
        return

    await bot.process_commands(message)


def main():
    if not TOKEN:
        print("Set DISCORD_BOT_TOKEN environment variable")
        return
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
