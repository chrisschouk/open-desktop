#!/usr/bin/env python3
"""
OpenWorker Discord connector — routes through the OpenDesktop gateway.

Usage:
  export DISCORD_BOT_TOKEN=...
  export OPENDESKTOP_API_URL=http://localhost:8000
  python connectors/discord_bot.py
"""
import os
import aiohttp

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("Install discord.py: pip install discord.py")
    raise

API_URL = os.getenv("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
API_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", "")


def _headers():
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def dispatch(channel_id: str, message: str, user_id: str) -> dict:
    payload = {
        "channel": "discord",
        "channel_id": channel_id,
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


@bot.event
async def on_ready():
    print(f"OpenWorker Discord → OpenDesktop gateway ({API_URL})")


@bot.command(name="worker")
async def worker_cmd(ctx, *, prompt: str = ""):
    if not prompt:
        await ctx.reply("Usage: `!worker <your task or question>`")
        return
    await ctx.trigger_typing()
    try:
        result = await dispatch(str(ctx.channel.id), prompt, str(ctx.author.id))
        reply = result.get("reply", "No response")
        embed = discord.Embed(description=reply[:4000], color=0x3b82f6)
        embed.set_author(name="OpenWorker")
        embed.set_footer(text=f"Intent: {result.get('intent', '—')} | {result.get('status', '')}")
        await ctx.reply(embed=embed)
        if result.get("status") == "working":
            await ctx.send("Desktop sandbox running — check OpenDesktop for the live screen.")
    except Exception as e:
        await ctx.reply(f"Gateway error: {e}")


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
            try:
                result = await dispatch(str(message.channel.id), text, str(message.author.id))
                await message.reply(result.get("reply", "…")[:2000])
            except Exception as e:
                await message.reply(f"OpenWorker error: {e}")
        return
    await bot.process_commands(message)


def main():
    if not TOKEN:
        print("Set DISCORD_BOT_TOKEN")
        return
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
