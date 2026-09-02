"""
OpenDesktop Gateway — hub-and-spoke message routing for all channels.

Channel adapters (Discord, Telegram, Web) normalize messages here.
Session keys map external channels to OpenWorker chat sessions.
"""
from typing import Callable, Optional

from . import memory
from .chat_service import chat_service
from .persona import get_greeting, load_persona


def session_key(channel: str, channel_id: str, user_id: Optional[str] = None) -> str:
    """Stable key for routing: discord:guild:channel or telegram:chat:user."""
    parts = [channel, channel_id]
    if user_id:
        parts.append(user_id)
    return ":".join(parts)


def resolve_session(channel_key: str, persona_id: str = "openworker") -> str:
    """Get or create an OpenWorker session for a channel key."""
    existing = memory.get_channel_session(channel_key)
    if existing:
        return existing
    session = memory.create_session(persona_id=persona_id, channel_key=channel_key)
    greeting = get_greeting(persona_id)
    memory.add_message(session["id"], "assistant", greeting, {"intent": "greeting"})
    return session["id"]


async def dispatch(
    channel: str,
    channel_id: str,
    message: str,
    user_id: Optional[str] = None,
    persona_id: str = "openworker",
    broadcast_action: Optional[Callable] = None,
) -> dict:
    """
    Unified entry point for all connectors.
    Returns chat_service response with session_id attached.
    """
    key = session_key(channel, channel_id, user_id)
    session_id = resolve_session(key, persona_id)
    result = await chat_service.handle_message(session_id, message, broadcast_action)
    result["channel_key"] = key
    result["channel"] = channel
    return result
