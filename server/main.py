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


class CreateSessionRequest(BaseModel):
    persona_id: Optional[str] = "openworker"


class GatewayDispatchRequest(BaseModel):
    channel: str
    channel_id: str
    message: str
    user_id: Optional[str] = None
    persona_id: Optional[str] = "openworker"


class CreateScheduleRequest(BaseModel):
    name: str
    prompt: str
    interval_seconds: int = 86400
    playbook_id: Optional[str] = None


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}


# ── REST Endpoints ────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize DB, scheduler, and optionally provision default fleet."""
    memory.init_db()
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
    session = memory.create_session(persona_id=req.persona_id or "openworker")
    persona = load_persona(session["persona_id"])
    greeting = get_greeting(session["persona_id"])
    memory.add_message(session["id"], "assistant", greeting, {"intent": "greeting"})
    return {
        "session": session,
        "persona": {"id": persona.get("id"), "name": persona.get("name")},
        "greeting": greeting,
    }


@app.get("/api/v1/sessions")
def list_sessions():
    return {"sessions": memory.list_sessions()}


@app.get("/api/v1/sessions/{session_id}")
def get_session_detail(session_id: str):
    session = memory.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": session,
        "messages": memory.get_messages(session_id),
    }


@app.post("/api/v1/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    if req.session_id:
        session = memory.get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = req.session_id
    else:
        session = memory.create_session(persona_id=req.persona_id or "openworker")
        session_id = session["id"]

    result = await chat_service.handle_message(
        session_id, req.message, manager.broadcast_action
    )
    return result


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
async def gateway_dispatch_endpoint(req: GatewayDispatchRequest, authorization: Optional[str] = Header(None)):
    """Unified entry for Discord, Telegram, and other channel adapters."""
    if not verify_api_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await gateway_dispatch(
        req.channel,
        req.channel_id,
        req.message,
        req.user_id,
        req.persona_id or "openworker",
        manager.broadcast_action,
    )


@app.get("/api/v1/schedules")
def get_schedules():
    return {"schedules": list_schedules()}


@app.post("/api/v1/schedules")
def post_schedule(req: CreateScheduleRequest):
    sched = create_schedule(req.name, req.prompt, req.interval_seconds, req.playbook_id)
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
