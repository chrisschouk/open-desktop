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
from .audit import append_audit
from .sandbox_status import get_sandbox_status, should_fallback_desktop


class ChatService:
    async def handle_message(
        self,
        session_id: str,
        message: str,
        broadcast_action: Optional[Callable] = None,
        trace_id: Optional[str] = None,
        force_intent: Optional[str] = None,
    ) -> dict:
        session = memory.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.get("status") == "working":
            reply = "Still working on the previous task — I'll update you when it's done."
            memory.add_message(session_id, "assistant", reply, {
                "intent": "busy", "status": "working", "trace_id": trace_id,
            })
            return {
                "session_id": session_id,
                "intent": "busy",
                "reply": reply,
                "status": "working",
                "trace_id": trace_id,
            }

        memory.add_message(session_id, "user", message, {"trace_id": trace_id} if trace_id else None)
        history = memory.get_messages(session_id)
        persona_id = session.get("persona_id", "openworker")

        matched_skills = match_skills(message)
        skill_playbook = matched_skills[0].get("playbook_id") if matched_skills else None

        if force_intent and force_intent in ("chat", "browser", "research", "automate", "playbook"):
            intent = force_intent
            classification = {
                "intent": intent,
                "playbook_id": skill_playbook,
                "task_prompt": message,
                "forced": True,
            }
        else:
            classification = await classify_intent(message, history)
            intent = classification.get("intent") or "chat"
            if intent not in ("chat", "browser", "research", "automate", "playbook"):
                intent = "chat"
            if skill_playbook and intent in ("research", "playbook", "automate"):
                intent = "playbook"
                classification["playbook_id"] = skill_playbook

        if trace_id:
            append_audit("chat_route", {
                "trace_id": trace_id,
                "session_id": session_id,
                "intent": intent,
                "playbook_id": classification.get("playbook_id"),
                "forced": bool(force_intent),
            })

        sandbox_status = await get_sandbox_status()
        fallback = False
        original_intent = None
        if should_fallback_desktop(intent, force_intent, sandbox_status):
            original_intent = intent
            fallback = True
            intent = "browser"
            classification["intent"] = "browser"
            classification["fallback"] = True
            classification["original_intent"] = original_intent
            if trace_id:
                append_audit("chat_fallback", {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "original_intent": original_intent,
                    "fallback_intent": "browser",
                    "reason": sandbox_status.get("reason"),
                })

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
                "trace_id": trace_id,
            }

        if intent == "browser":
            reply = await browser_research(message, persona_id)
            if fallback:
                prefix = (
                    "Desktop sandbox isn't available right now "
                    f"({sandbox_status.get('reason', 'unavailable')}) — "
                    "running browser research instead.\n\n"
                )
                reply = prefix + reply
            meta = {
                "intent": "browser",
                "status": "idle",
                "trace_id": trace_id,
            }
            if fallback:
                meta["fallback"] = True
                meta["original_intent"] = original_intent
            memory.add_message(session_id, "assistant", reply, meta)
            memory.update_session(session_id, status="idle")
            result = {
                "session_id": session_id,
                "intent": "browser",
                "reply": reply,
                "status": "idle",
                "trace_id": trace_id,
            }
            if fallback:
                result["fallback"] = True
                result["original_intent"] = original_intent
            return result

        task_prompt = classification.get("task_prompt") or message
        playbook_id = classification.get("playbook_id") or skill_playbook
        skill_ctx = skills_context_for_message(message)
        if skill_ctx:
            task_prompt = f"{skill_ctx}\n\n{task_prompt}"

        ack = await self._build_ack(intent, task_prompt, playbook_id)
        if not memory.try_acquire_session(session_id):
            reply = "Still working on the previous task — I'll update you when it's done."
            memory.add_message(session_id, "assistant", reply, {"intent": "busy", "status": "working"})
            return {
                "session_id": session_id,
                "intent": "busy",
                "reply": reply,
                "status": "working",
                "trace_id": trace_id,
            }

        memory.add_message(session_id, "assistant", ack, {
            "intent": intent,
            "playbook_id": playbook_id,
            "status": "working",
            "trace_id": trace_id,
        })
        memory.update_session(session_id, playbook_id=playbook_id)

        asyncio.create_task(
            self._run_task(session_id, intent, task_prompt, playbook_id, broadcast_action, trace_id)
        )

        return {
            "session_id": session_id,
            "intent": intent,
            "reply": ack,
            "status": "working",
            "playbook_id": playbook_id,
            "skills": [s["id"] for s in matched_skills],
            "trace_id": trace_id,
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
        trace_id: Optional[str] = None,
    ):
        try:
            await hooks.emit("before_agent_run", {
                "session_id": session_id,
                "intent": intent,
                "playbook_id": playbook_id,
                "trace_id": trace_id,
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

            if trace_id:
                append_audit("chat_complete", {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "intent": intent,
                    "status": result.get("status"),
                    "machine_id": result.get("machine_id"),
                })

            await hooks.emit("after_agent_run", {
                "session_id": session_id,
                "result": result,
                "trace_id": trace_id,
            })

            summary = result.get("summary", result.get("status", "Task finished"))
            memory.add_message(session_id, "assistant", f"Done. {summary}", {
                "intent": intent,
                "status": "completed",
                "result": result,
                "trace_id": trace_id,
                "machine_id": result.get("machine_id"),
            })
            memory.update_session(session_id, status="idle")
        except Exception as e:
            if trace_id:
                append_audit("chat_error", {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "error": str(e),
                })
            memory.add_message(session_id, "assistant", f"Hit an error: {e}", {
                "status": "error", "trace_id": trace_id,
            })
            memory.update_session(session_id, status="error")


chat_service = ChatService()
