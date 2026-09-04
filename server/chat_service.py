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
from .workers import DEFAULT_WORKER_ID, set_presence, sync_presence_from_session
from .artifacts import create_artifact, artifact_ref_payload


class ChatService:
    def _worker_id(self, session: dict) -> str:
        return session.get("worker_id") or DEFAULT_WORKER_ID

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

        worker_id = self._worker_id(session)

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
                "worker_id": worker_id,
                "trace_id": trace_id,
            }

        memory.add_message(session_id, "user", message, {"trace_id": trace_id} if trace_id else None)
        history = memory.get_messages(session_id)
        persona_id = session.get("persona_id", "openworker")
        set_presence(worker_id, "thinking", current_action="Reading your message")

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

        if intent == "chat":
            skill_ctx = skills_context_for_message(message)
            enriched = f"{skill_ctx}\n\n{message}" if skill_ctx else message
            reply = await chat_reply(enriched, history[:-1], persona_id)
            memory.add_message(session_id, "assistant", reply, {"intent": "chat"}, kind="text")
            memory.update_session(session_id, status="idle")
            set_presence(worker_id, "idle", current_action=None)
            return {
                "session_id": session_id,
                "intent": "chat",
                "reply": reply,
                "status": "idle",
                "worker_id": worker_id,
                "skills": [s["id"] for s in matched_skills],
                "trace_id": trace_id,
            }

        if intent == "browser":
            reply = await browser_research(message, persona_id)
            memory.add_message(session_id, "assistant", reply, {
                "intent": "browser", "status": "idle", "trace_id": trace_id,
            }, kind="text")
            memory.update_session(session_id, status="idle")
            set_presence(worker_id, "idle", current_action=None)
            return {
                "session_id": session_id,
                "intent": "browser",
                "reply": reply,
                "status": "idle",
                "worker_id": worker_id,
                "trace_id": trace_id,
            }

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
        }, kind="text")
        memory.add_message(
            session_id,
            "assistant",
            "Desktop sandbox activating…",
            {"intent": intent, "computer": "status"},
            kind="computer_status",
        )
        memory.update_session(session_id, playbook_id=playbook_id)
        set_presence(worker_id, "working", current_action=ack[:120])

        asyncio.create_task(
            self._run_task(session_id, intent, task_prompt, playbook_id, broadcast_action, trace_id)
        )

        return {
            "session_id": session_id,
            "intent": intent,
            "reply": ack,
            "status": "working",
            "worker_id": worker_id,
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
                session = memory.get_session(session_id) or {}
                from .workers import update_worker
                update_worker(self._worker_id(session), preferred_machine_id=machine_id)
                memory.add_message(
                    session_id,
                    "assistant",
                    f"Computer online · `{machine_id}`",
                    {"machine_id": machine_id},
                    kind="computer_status",
                )
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
            session = memory.get_session(session_id) or {}
            worker_id = self._worker_id(session)
            memory.add_message(session_id, "assistant", f"Done. {summary}", {
                "intent": intent,
                "status": "completed",
                "result": result,
                "trace_id": trace_id,
                "machine_id": result.get("machine_id"),
            }, kind="text")
            art = create_artifact(
                worker_id=worker_id,
                title=f"Task result — {intent}",
                kind="report",
                session_id=session_id,
                text=str(summary),
                meta={"intent": intent, "machine_id": result.get("machine_id"), "trace_id": trace_id},
            )
            memory.add_message(
                session_id,
                "assistant",
                art["title"],
                metadata=artifact_ref_payload(art),
                kind="artifact_ref",
            )
            memory.update_session(session_id, status="idle")
            set_presence(worker_id, "done", current_action=None)
            sync_presence_from_session(session_id, tier="T2")
            set_presence(worker_id, "idle", current_action=None)
        except Exception as e:
            if trace_id:
                append_audit("chat_error", {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "error": str(e),
                })
            memory.add_message(session_id, "assistant", f"Hit an error: {e}", {
                "status": "error", "trace_id": trace_id,
            }, kind="event")
            memory.update_session(session_id, status="error")
            session = memory.get_session(session_id) or {}
            set_presence(self._worker_id(session), "blocked", current_action=str(e)[:120])


chat_service = ChatService()
