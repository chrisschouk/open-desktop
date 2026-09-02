"""
OpenWorker chat service — routes chat vs desktop automation.
"""
import asyncio
from typing import Callable, Optional

from . import memory
from .chat_agent import chat_reply
from .intent_router import classify_intent
from .persona import get_greeting
from .playbook_executor import run_playbook
from .sandbox_factory import sandbox_manager
from .agent_runner import agent_runner
from .orchestrator import orchestrator


class ChatService:
    async def handle_message(
        self,
        session_id: str,
        message: str,
        broadcast_action: Optional[Callable] = None,
    ) -> dict:
        session = memory.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        memory.add_message(session_id, "user", message)
        history = memory.get_messages(session_id)
        persona_id = session.get("persona_id", "openworker")

        classification = await classify_intent(message, history)
        intent = classification.get("intent", "chat")

        if intent == "chat":
            reply = await chat_reply(message, history[:-1], persona_id)
            memory.add_message(session_id, "assistant", reply, {"intent": "chat"})
            memory.update_session(session_id, status="idle")
            return {
                "session_id": session_id,
                "intent": "chat",
                "reply": reply,
                "status": "idle",
            }

        # Action intents — acknowledge then run in background
        task_prompt = classification.get("task_prompt") or message
        playbook_id = classification.get("playbook_id")

        ack = await self._build_ack(intent, task_prompt, playbook_id)
        memory.add_message(session_id, "assistant", ack, {
            "intent": intent,
            "playbook_id": playbook_id,
            "status": "working",
        })
        memory.update_session(session_id, status="working", playbook_id=playbook_id)

        asyncio.create_task(
            self._run_task(session_id, intent, task_prompt, playbook_id, broadcast_action)
        )

        return {
            "session_id": session_id,
            "intent": intent,
            "reply": ack,
            "status": "working",
            "playbook_id": playbook_id,
        }

    async def _build_ack(self, intent: str, task: str, playbook_id: Optional[str]) -> str:
        if intent == "playbook" and playbook_id:
            return (
                f"On it — spinning up a desktop and running the **{playbook_id}** playbook. "
                f"You can watch the live screen in the panel. I'll update you when it's done."
            )
        if intent == "research":
            return (
                "Got it — I'll open a browser in an isolated desktop and research that for you. "
                "Watch the live feed; I'll report back when I'm done."
            )
        return (
            "Understood — spinning up a desktop sandbox to handle that. "
            "You'll see the screen stream update as I work."
        )

    async def _run_task(
        self,
        session_id: str,
        intent: str,
        task_prompt: str,
        playbook_id: Optional[str],
        broadcast_action: Optional[Callable],
    ):
        try:
            if intent == "playbook" and playbook_id:
                result = await run_playbook(
                    playbook_id, task_prompt, sandbox_manager, agent_runner, broadcast_action
                )
            else:
                machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
                if machines:
                    machine_id = machines[0]["id"]
                else:
                    machine_data = await sandbox_manager.create_sandbox(name="OpenWorker Agent")
                    machine_id = machine_data["id"]
                    await asyncio.sleep(8)

                memory.update_session(session_id, machine_id=machine_id)
                result = await orchestrator.run_single_task(
                    machine_id, task_prompt, broadcast_action
                )

            summary = result.get("summary", result.get("status", "Task finished"))
            memory.add_message(session_id, "assistant", f"Done. {summary}", {
                "intent": intent,
                "status": "completed",
                "result": result,
            })
            memory.update_session(session_id, status="idle")
        except Exception as e:
            memory.add_message(session_id, "assistant", f"Hit an error: {e}", {"status": "error"})
            memory.update_session(session_id, status="error")


chat_service = ChatService()
