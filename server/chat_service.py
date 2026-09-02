"""
OpenWorker chat service — routes chat vs desktop automation.
"""
import asyncio
from typing import Callable, Optional

from . import memory
from .chat_agent import chat_reply
from .intent_router import classify_intent
from .playbook_executor import run_playbook
from .sandbox_factory import sandbox_manager
from .agent_runner import agent_runner
from .orchestrator import orchestrator
from .skills import match_skills, skills_context_for_message
from .browser_research import browser_research
from . import hooks
from .runtime import ensure_running_sandbox


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

        if session.get("status") == "working":
            reply = "Still working on the previous task — I'll update you when it's done."
            memory.add_message(session_id, "assistant", reply, {"intent": "busy", "status": "working"})
            return {
                "session_id": session_id,
                "intent": "busy",
                "reply": reply,
                "status": "working",
            }

        memory.add_message(session_id, "user", message)
        history = memory.get_messages(session_id)
        persona_id = session.get("persona_id", "openworker")

        # Skill match may force playbook intent
        matched_skills = match_skills(message)
        skill_playbook = matched_skills[0].get("playbook_id") if matched_skills else None

        classification = await classify_intent(message, history)
        intent = classification.get("intent") or "chat"
        if intent not in ("chat", "browser", "research", "automate", "playbook"):
            intent = "chat"
        if skill_playbook and intent in ("research", "playbook", "automate"):
            intent = "playbook"
            classification["playbook_id"] = skill_playbook

        if intent == "chat":
            skill_ctx = skills_context_for_message(message)
            enriched = f"{skill_ctx}\n\n{message}" if skill_ctx else message
            reply = await chat_reply(enriched, history[:-1], persona_id)
            memory.add_message(session_id, "assistant", reply, {"intent": "chat"})
            memory.update_session(session_id, status="idle")
            return {
                "session_id": session_id,
                "intent": "chat",
                "reply": reply,
                "status": "idle",
                "skills": [s["id"] for s in matched_skills],
            }

        if intent == "browser":
            reply = await browser_research(message, persona_id)
            memory.add_message(session_id, "assistant", reply, {"intent": "browser", "status": "idle"})
            memory.update_session(session_id, status="idle")
            return {
                "session_id": session_id,
                "intent": "browser",
                "reply": reply,
                "status": "idle",
            }

        task_prompt = classification.get("task_prompt") or message
        playbook_id = classification.get("playbook_id") or skill_playbook
        skill_ctx = skills_context_for_message(message)
        if skill_ctx:
            task_prompt = f"{skill_ctx}\n\n{task_prompt}"

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
            "skills": [s["id"] for s in matched_skills],
        }

    async def _build_ack(self, intent: str, task: str, playbook_id: Optional[str]) -> str:
        if intent == "playbook" and playbook_id:
            return (
                f"On it — spinning up a desktop and running the **{playbook_id}** playbook. "
                f"Watch the live screen in the panel. I'll update you when it's done."
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
            await hooks.emit("before_agent_run", {
                "session_id": session_id,
                "intent": intent,
                "playbook_id": playbook_id,
            })

            if intent == "playbook" and playbook_id:
                result = await run_playbook(
                    playbook_id, task_prompt, sandbox_manager, agent_runner, broadcast_action
                )
            else:
                machine_id = await ensure_running_sandbox(sandbox_manager, "OpenWorker Agent")
                memory.update_session(session_id, machine_id=machine_id)
                result = await orchestrator.run_single_task(
                    machine_id, task_prompt, broadcast_action
                )

            await hooks.emit("after_agent_run", {
                "session_id": session_id,
                "result": result,
            })

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
