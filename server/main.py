"""
OpenDesktop Engine - API Server
Real sandbox management with WebSocket screenshot streaming and autonomous agents.
"""
import os
import asyncio
import json
import time
import base64
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request, Header
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .sandbox_factory import sandbox_manager
from .orchestrator import orchestrator
from . import memory
from .chat_service import chat_service
from .persona import get_greeting, load_persona
from .playbook_executor import list_playbooks
from .config import AUTO_PROVISION_FLEET, SANDBOX_MODE, SCHEDULER_ENABLED
from .workerhub import get_workerhub_catalog
from .audit import init_audit, list_audit, verify_chain
from .skills import list_skills_catalog
from .tools import list_tools, call_tool
from .gateway import dispatch as gateway_dispatch
from .scheduler import init_schedules, create_schedule, list_schedules, scheduler_loop
from .runtime import verify_api_token, can_set_api_key
from .health import get_health
from .workflow_loader import load_workflow_files
from .agent_api import (
    agent_orient,
    agent_plan,
    load_manifest,
    new_trace_id,
    envelope_chat_response,
)
from . import workers as workers_mod
from . import artifacts as artifacts_mod
from .routines import (
    create_routine,
    list_routines,
    get_routine,
    pause_routine,
    resume_routine,
    delete_routine,
)
from . import groups as groups_mod


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        # machine_id -> list of WebSocket connections for screenshot streaming
        self.stream_connections: dict[str, list[WebSocket]] = {}
        # WebSocket connections for action events
        self.action_connections: list[WebSocket] = []

    async def connect_stream(self, websocket: WebSocket, machine_id: str):
        await websocket.accept()
        if machine_id not in self.stream_connections:
            self.stream_connections[machine_id] = []
        self.stream_connections[machine_id].append(websocket)

    def disconnect_stream(self, websocket: WebSocket, machine_id: str):
        if machine_id in self.stream_connections:
            if websocket in self.stream_connections[machine_id]:
                self.stream_connections[machine_id].remove(websocket)

    async def connect_action(self, websocket: WebSocket):
        await websocket.accept()
        self.action_connections.append(websocket)

    def disconnect_action(self, websocket: WebSocket):
        if websocket in self.action_connections:
            self.action_connections.remove(websocket)

    async def broadcast_action(self, machine_id: str, event: dict):
        """Broadcast an action event to all connected action WebSocket clients."""
        if "type" not in event:
            event["type"] = "action"
        # Update Worker current_action from thought / action stream
        try:
            thought = event.get("thought") or event.get("action_type") or event.get("message")
            if thought:
                for w in workers_mod.list_workers():
                    if w.get("preferred_machine_id") == machine_id or (
                        w.get("presence") in ("working", "thinking") and not w.get("preferred_machine_id")
                    ):
                        workers_mod.set_current_action(w["id"], str(thought)[:160])
                        event["worker_id"] = w["id"]
                        break
        except Exception:
            pass
        text = json.dumps(event)
        dead = []
        for ws in self.action_connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_action(ws)


manager = ConnectionManager()

# Background tasks for screenshot streaming
streaming_tasks: dict[str, asyncio.Task] = {}


async def stream_screenshots_loop(machine_id: str):
    """Background coroutine that fetches screenshots and pushes to connected WebSocket clients."""
    while True:
        clients = manager.stream_connections.get(machine_id, [])
        if not clients:
            await asyncio.sleep(0.5)
            continue

        # Get screenshot from remote sandbox
        screenshot_b64 = await sandbox_manager.get_screenshot_base64(machine_id)
        if not screenshot_b64:
            await asyncio.sleep(1)
            continue

        # Send to all connected clients as JSON with base64 data
        msg = json.dumps({"type": "frame", "data": screenshot_b64})
        dead = []
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            manager.disconnect_stream(ws, machine_id)

        await asyncio.sleep(0.2)  # ~5 FPS


def ensure_streaming(machine_id: str):
    """Ensure a screenshot streaming task is running for a machine."""
    if machine_id not in streaming_tasks or streaming_tasks[machine_id].done():
        streaming_tasks[machine_id] = asyncio.create_task(
            stream_screenshots_loop(machine_id)
        )


# FastAPI App
app = FastAPI(
    title="OpenDesktop",
    version="2.1.0",
    description="Open source desktop agent platform. OpenWorker chat + sandbox automation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ──────────────────────────────────

class CreateMachineRequest(BaseModel):
    name: Optional[str] = None
    template: Optional[str] = "medium"
    width: Optional[int] = 1280
    height: Optional[int] = 800

class MachineActionRequest(BaseModel):
    action: str
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    command: Optional[str] = None
    button: Optional[str] = "left"

class RunPlaybookRequest(BaseModel):
    playbook_id: Optional[str] = None
    prompt: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    persona_id: Optional[str] = "openworker"
    worker_id: Optional[str] = None
    force_intent: Optional[str] = None
    trace_id: Optional[str] = None


class PlanRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    force_intent: Optional[str] = None


class CreateSessionRequest(BaseModel):
    persona_id: Optional[str] = "openworker"
    worker_id: Optional[str] = None


class GatewayDispatchRequest(BaseModel):
    channel: str
    channel_id: str
    message: str
    user_id: Optional[str] = None
    persona_id: Optional[str] = "openworker"
    force_intent: Optional[str] = None
    trace_id: Optional[str] = None


class CreateWorkerRequest(BaseModel):
    name: str
    avatar: Optional[str] = "default"
    role: Optional[str] = "general"
    persona_ref: Optional[str] = "openworker"


class UpdateWorkerRequest(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None
    persona_ref: Optional[str] = None
    preferred_machine_id: Optional[str] = None
    presence: Optional[str] = None
    current_action: Optional[str] = None
    memory: Optional[dict] = None


class CreateRoutineRequest(BaseModel):
    name: str
    prompt: str
    interval_seconds: int = 86400
    playbook_id: Optional[str] = None
    worker_id: Optional[str] = None


class CreateArtifactRequest(BaseModel):
    title: str
    kind: Optional[str] = "file"
    text: Optional[str] = None
    session_id: Optional[str] = None
    mime_type: Optional[str] = None
    meta: Optional[dict] = None


class CreateGroupRequest(BaseModel):
    name: str
    worker_ids: List[str]
    coordinator_id: Optional[str] = None


class CreateScheduleRequest(BaseModel):
    name: str
    prompt: str
    interval_seconds: int = 86400
    playbook_id: Optional[str] = None
    worker_id: Optional[str] = None


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}


# ── REST Endpoints ────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize DB, workers, scheduler, and optionally provision default fleet."""
    memory.init_db()
    workers_mod.init_workers()
    artifacts_mod.init_artifacts()
    groups_mod.init_groups()
    init_audit()
    init_schedules()
    if hasattr(sandbox_manager, "reconcile_from_docker"):
        await sandbox_manager.reconcile_from_docker()
    imported = load_workflow_files()
    if imported:
        print(f"[Startup] Loaded {len(imported)} workflow(s) from workflows/")
    if SCHEDULER_ENABLED:
        asyncio.create_task(scheduler_loop(manager.broadcast_action))
        print("[Startup] Scheduler enabled")
    if not AUTO_PROVISION_FLEET:
        print("[Startup] AUTO_PROVISION_FLEET=false — skipping default machines")
        return
    fleet = [
        ("Agent Machine #1", 1280, 800),
        ("Agent Machine #2", 1280, 800),
    ]
    for name, w, h in fleet:
        try:
            data = await sandbox_manager.create_sandbox(name=name, width=w, height=h)
            print(f"[Startup] Provisioned {name} → {data['id']}")
        except Exception as e:
            print(f"[Startup] Failed to provision {name}: {e}")


@app.get("/")
def root():
    return {
        "platform": "OpenDesktop",
        "agent": "OpenWorker",
        "version": "2.1.0",
        "status": "online",
        "sandbox_mode": SANDBOX_MODE,
        "tagline": "Open source desktop agent",
    }


@app.get("/api/v1/health")
async def health_check():
    return await get_health()


# ── Agent-native API (Phase B) ────────────────────────

@app.get("/api/v1/agent/orient")
async def agent_orient_endpoint():
    return await agent_orient()


@app.get("/api/v1/agent/manifest")
def agent_manifest_endpoint():
    return load_manifest()


@app.post("/api/v1/agent/plan")
async def agent_plan_endpoint(req: PlanRequest):
    return await agent_plan(req.message, req.session_id, req.force_intent)


@app.get("/api/v1/machines")
def list_machines():
    return {"machines": sandbox_manager.list_sandboxes()}


@app.post("/api/v1/machines")
async def create_machine(req: CreateMachineRequest):
    machine_data = await sandbox_manager.create_sandbox(
        name=req.name, width=req.width or 1280, height=req.height or 800
    )
    return {"status": "success", "machine": machine_data}


@app.get("/api/v1/machines/{machine_id}")
def get_machine(machine_id: str):
    mach = sandbox_manager.get_sandbox(machine_id)
    if not mach:
        raise HTTPException(status_code=404, detail="Machine not found")
    return {"machine": mach}


@app.post("/api/v1/machines/{machine_id}/start")
async def start_machine(machine_id: str):
    ok = await sandbox_manager.start_sandbox(machine_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Machine not found")
    return {"status": "started", "machine_id": machine_id}


@app.post("/api/v1/machines/{machine_id}/stop")
async def stop_machine(machine_id: str):
    ok = await sandbox_manager.stop_sandbox(machine_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Machine not found")
    return {"status": "stopped", "machine_id": machine_id}


@app.delete("/api/v1/machines/{machine_id}")
async def delete_machine(machine_id: str):
    ok = await sandbox_manager.destroy_sandbox(machine_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Machine not found")
    # Cancel streaming task
    if machine_id in streaming_tasks:
        streaming_tasks[machine_id].cancel()
        del streaming_tasks[machine_id]
    return {"status": "destroyed", "machine_id": machine_id}


@app.post("/api/v1/machines/{machine_id}/actions")
async def execute_action(machine_id: str, action: MachineActionRequest):
    result = await sandbox_manager.execute_action(machine_id, action.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Machine not found or not running")
    await manager.broadcast_action(machine_id, {
        "type": "action",
        "action_type": action.action,
        "machine_id": machine_id,
        "result": result,
    })
    return {"status": "success", "result": result}


@app.get("/api/v1/machines/{machine_id}/screenshot")
async def get_screenshot(machine_id: str):
    img_bytes = await sandbox_manager.get_screenshot(machine_id)
    if not img_bytes:
        raise HTTPException(status_code=404, detail="Machine not found or not running")
    return Response(content=img_bytes, media_type="image/jpeg")


class SetApiKeyRequest(BaseModel):
    api_key: str

@app.post("/api/v1/keys/set")
async def set_api_key(
    req: SetApiKeyRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    if not can_set_api_key(request, authorization):
        raise HTTPException(
            status_code=403,
            detail="API keys can only be set from localhost/LAN or with OPENDESKTOP_API_TOKEN",
        )
    from .config import apply_llm_api_key
    apply_llm_api_key(req.api_key)
    return {"status": "success", "message": "API key updated successfully!"}


# ── OpenWorker Chat API ───────────────────────────────

@app.post("/api/v1/sessions")
async def create_session(req: CreateSessionRequest):
    workers_mod.ensure_default_worker()
    worker_id = req.worker_id or workers_mod.DEFAULT_WORKER_ID
    worker = workers_mod.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    persona_id = req.persona_id or worker.get("persona_ref") or "openworker"
    session = memory.create_session(persona_id=persona_id, worker_id=worker_id)
    persona = load_persona(session["persona_id"])
    greeting = get_greeting(session["persona_id"])
    memory.add_message(session["id"], "assistant", greeting, {"intent": "greeting"}, kind="text")
    return {
        "session": session,
        "worker": worker,
        "persona": {"id": persona.get("id"), "name": persona.get("name")},
        "greeting": greeting,
    }


@app.get("/api/v1/sessions")
def list_sessions(worker_id: Optional[str] = None):
    return {"sessions": memory.list_sessions(worker_id=worker_id)}


@app.get("/api/v1/sessions/{session_id}")
def get_session_detail(session_id: str):
    session = memory.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    worker = None
    if session.get("worker_id"):
        worker = workers_mod.get_worker(session["worker_id"])
    return {
        "session": session,
        "worker": worker,
        "messages": memory.get_messages(session_id),
    }


@app.post("/api/v1/chat")
async def chat(req: ChatRequest, request: Request, background_tasks: BackgroundTasks):
    workers_mod.ensure_default_worker()
    if req.session_id:
        session = memory.get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = req.session_id
    else:
        worker_id = req.worker_id or workers_mod.DEFAULT_WORKER_ID
        worker = workers_mod.get_worker(worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        session = memory.create_session(
            persona_id=req.persona_id or worker.get("persona_ref") or "openworker",
            worker_id=worker_id,
        )
        session_id = session["id"]

    trace_id = req.trace_id or new_trace_id()
    result = await chat_service.handle_message(
        session_id,
        req.message,
        manager.broadcast_action,
        trace_id=trace_id,
        force_intent=req.force_intent,
    )
    base = str(request.base_url).rstrip("/")
    return envelope_chat_response(result, trace_id, base)


# ── Workers ───────────────────────────────────────────

@app.get("/api/v1/workers")
def get_workers():
    workers_mod.ensure_default_worker()
    return {"workers": workers_mod.list_workers(), "limit": workers_mod.MAX_WORKERS}


@app.post("/api/v1/workers")
def post_worker(req: CreateWorkerRequest):
    workers_mod.ensure_default_worker()
    try:
        worker = workers_mod.create_worker(
            name=req.name,
            avatar=req.avatar or "default",
            role=req.role or "general",
            persona_ref=req.persona_ref or "openworker",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "created", "worker": worker}


@app.get("/api/v1/workers/{worker_id}")
def get_worker_detail(worker_id: str):
    worker = workers_mod.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return {
        "worker": worker,
        "chats": workers_mod.list_worker_chats(worker_id),
        "routines": list_routines(worker_id),
        "artifacts": artifacts_mod.list_artifacts(worker_id=worker_id, limit=20),
    }


@app.patch("/api/v1/workers/{worker_id}")
def patch_worker(worker_id: str, req: UpdateWorkerRequest):
    if not workers_mod.get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    fields = req.model_dump(exclude_none=True)
    try:
        worker = workers_mod.update_worker(worker_id, **fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"worker": worker}


@app.post("/api/v1/workers/{worker_id}/chats")
async def create_worker_chat(worker_id: str):
    if not workers_mod.get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    try:
        session = workers_mod.create_chat_for_worker(worker_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    persona = load_persona(session["persona_id"])
    greeting = get_greeting(session["persona_id"])
    memory.add_message(session["id"], "assistant", greeting, {"intent": "greeting"}, kind="text")
    # Seed routine-first empty-state hint as event
    memory.add_message(
        session["id"],
        "assistant",
        "Work can start from a prompt, a Routine, or another Worker — not only from chat.",
        {"intent": "hint"},
        kind="event",
    )
    return {
        "session": session,
        "worker": workers_mod.get_worker(worker_id),
        "persona": {"id": persona.get("id"), "name": persona.get("name")},
        "greeting": greeting,
    }


@app.get("/api/v1/workers/{worker_id}/routines")
def get_worker_routines(worker_id: str):
    if not workers_mod.get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    return {"routines": list_routines(worker_id)}


@app.post("/api/v1/workers/{worker_id}/routines")
def post_worker_routine(worker_id: str, req: CreateRoutineRequest):
    if not workers_mod.get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    routine = create_routine(
        name=req.name,
        prompt=req.prompt,
        interval_seconds=req.interval_seconds,
        playbook_id=req.playbook_id,
        worker_id=worker_id,
    )
    # Event in latest chat
    chats = memory.list_sessions(limit=1, worker_id=worker_id)
    if chats:
        memory.add_message(
            chats[0]["id"],
            "assistant",
            f"Created Routine · {req.name}",
            {"routine_id": routine["id"], "intent": "routine_created"},
            kind="event",
        )
        memory.add_message(
            chats[0]["id"],
            "assistant",
            req.name,
            {
                "widget": "routine",
                "routine_id": routine["id"],
                "interval_seconds": req.interval_seconds,
                "prompt": req.prompt,
            },
            kind="widget",
        )
    return {"status": "created", "routine": routine}


@app.post("/api/v1/routines/{routine_id}/pause")
def post_pause_routine(routine_id: str):
    r = pause_routine(routine_id)
    if not r:
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"routine": r}


@app.post("/api/v1/routines/{routine_id}/resume")
def post_resume_routine(routine_id: str):
    r = resume_routine(routine_id)
    if not r:
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"routine": r}


@app.delete("/api/v1/routines/{routine_id}")
def delete_routine_endpoint(routine_id: str):
    if not delete_routine(routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"status": "deleted", "id": routine_id}


@app.get("/api/v1/artifacts")
def get_artifacts(worker_id: Optional[str] = None):
    return {"artifacts": artifacts_mod.list_artifacts(worker_id=worker_id)}


@app.post("/api/v1/workers/{worker_id}/artifacts")
def post_artifact(worker_id: str, req: CreateArtifactRequest):
    if not workers_mod.get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    art = artifacts_mod.create_artifact(
        worker_id=worker_id,
        title=req.title,
        kind=req.kind or "file",
        session_id=req.session_id,
        text=req.text,
        mime_type=req.mime_type,
        meta=req.meta,
    )
    return {"status": "created", "artifact": art}


@app.get("/api/v1/artifacts/{artifact_id}")
def get_artifact_detail(artifact_id: str):
    art = artifacts_mod.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"artifact": art}


@app.get("/api/v1/groups")
def get_groups():
    return {"groups": groups_mod.list_groups(), "max_workers_per_group": groups_mod.MAX_WORKERS_PER_GROUP}


@app.post("/api/v1/groups")
def post_group(req: CreateGroupRequest):
    try:
        group = groups_mod.create_group_chat(
            name=req.name,
            worker_ids=req.worker_ids,
            coordinator_id=req.coordinator_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "created", "group": group}


@app.get("/api/v1/groups/{group_id}")
def get_group_detail(group_id: str):
    group = groups_mod.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    session = memory.get_session(group["session_id"])
    messages = memory.get_messages(group["session_id"]) if session else []
    return {"group": group, "session": session, "messages": messages}


@app.get("/api/v1/personas")
def get_personas():
    from pathlib import Path
    from .config import PERSONAS_DIR
    personas = []
    for path in PERSONAS_DIR.glob("*.yaml"):
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        personas.append({
            "id": data.get("id", path.stem),
            "name": data.get("name"),
            "tagline": data.get("tagline"),
            "description": data.get("description"),
        })
    return {"personas": personas}


@app.get("/api/v1/playbooks")
def get_playbooks():
    return {"playbooks": list_playbooks()}


@app.get("/api/v1/skills")
def get_skills():
    return {"skills": list_skills_catalog()}


@app.get("/api/v1/tools")
def get_tools():
    return {"tools": list_tools()}


@app.get("/api/v1/workerhub")
def workerhub_catalog():
    return get_workerhub_catalog()


@app.get("/api/v1/audit")
def get_audit_log():
    return {"entries": list_audit(), "chain": verify_chain()}


@app.post("/api/v1/tools/call")
async def invoke_tool(req: ToolCallRequest, authorization: Optional[str] = Header(None)):
    if not verify_api_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        result = await call_tool(req.name, req.arguments)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/gateway/dispatch")
async def gateway_dispatch_endpoint(
    req: GatewayDispatchRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Unified entry for Discord, Telegram, and other channel adapters."""
    if not verify_api_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    trace_id = req.trace_id or new_trace_id()
    result = await gateway_dispatch(
        req.channel,
        req.channel_id,
        req.message,
        req.user_id,
        req.persona_id or "openworker",
        manager.broadcast_action,
        trace_id=trace_id,
        force_intent=req.force_intent,
    )
    base = str(request.base_url).rstrip("/")
    return envelope_chat_response(result, trace_id, base)


@app.get("/api/v1/schedules")
def get_schedules():
    return {"schedules": list_schedules()}


@app.post("/api/v1/schedules")
def post_schedule(req: CreateScheduleRequest):
    sched = create_schedule(
        req.name,
        req.prompt,
        req.interval_seconds,
        req.playbook_id,
        worker_id=req.worker_id,
    )
    return {"status": "created", "schedule": sched}


# ── Playbooks / Orchestration ─────────────────────────

@app.post("/api/v1/playbooks/run")
async def run_playbook_endpoint(req: RunPlaybookRequest, background_tasks: BackgroundTasks):
    from .playbook_executor import run_playbook as execute_playbook
    from .agent_runner import agent_runner

    playbook_id = req.playbook_id or "pb_web_research"

    background_tasks.add_task(
        execute_playbook,
        playbook_id,
        req.prompt,
        sandbox_manager,
        agent_runner,
        manager.broadcast_action,
    )

    return {
        "status": "started",
        "playbook_id": playbook_id,
        "prompt": req.prompt,
    }


@app.post("/api/v1/orchestrate")
async def run_fleet(req: RunPlaybookRequest, background_tasks: BackgroundTasks):
    """Run a multi-machine fleet campaign."""
    background_tasks.add_task(
        orchestrator.run_fleet_campaign,
        req.prompt,
        manager.broadcast_action,
    )
    return {
        "status": "fleet_started",
        "prompt": req.prompt,
    }


# ── WebSocket Endpoints ──────────────────────────────

@app.websocket("/ws/stream/{machine_id}")
async def websocket_stream(websocket: WebSocket, machine_id: str):
    """Stream live screenshots from a sandbox machine to the browser."""
    await manager.connect_stream(websocket, machine_id)
    ensure_streaming(machine_id)
    try:
        while True:
            # Keep connection alive, client doesn't send data
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_stream(websocket, machine_id)
    except Exception:
        manager.disconnect_stream(websocket, machine_id)


@app.websocket("/ws/actions")
async def websocket_actions(websocket: WebSocket):
    """Stream real-time agent action events to the browser."""
    await manager.connect_action(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_action(websocket)
    except Exception:
        manager.disconnect_action(websocket)


# ── Run ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
