"""
OpenDesktop Engine - API Server
Real sandbox management with WebSocket screenshot streaming and LLM-driven agents.
"""
import os
import asyncio
import json
import time
import base64
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .docker_manager import sandbox_manager
from .orchestrator import orchestrator


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
    title="OpenDesktop Engine",
    version="2.0.0",
    description="Real cloud desktops for AI agents. Powered by Docker + LLM vision.",
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


# ── REST Endpoints ────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Provision default fleet machines on startup."""
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
        "platform": "OpenDesktop Engine",
        "version": "2.0.0",
        "status": "online",
        "mode": "remote-docker",
        "vps": "Hetzner (46.225.66.39)",
    }


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


class SetKeyRequest(BaseModel):
    api_key: str

@app.post("/api/v1/keys/set")
def set_api_key(req: SetKeyRequest):
    key = req.api_key.strip()
    if key.startswith("sk-or-"):
        os.environ["OPENROUTER_API_KEY"] = key
    elif key.startswith("sk-"):
        os.environ["OPENAI_API_KEY"] = key
    else:
        os.environ["OPENROUTER_API_KEY"] = key
    return {"status": "success", "message": "API key updated successfully!"}


# ── Playbooks / Orchestration ─────────────────────────

@app.post("/api/v1/playbooks/run")
async def run_playbook(req: RunPlaybookRequest, background_tasks: BackgroundTasks):
    machines = [m for m in sandbox_manager.list_sandboxes() if m.get("status") == "running"]
    if machines:
        machine_id = machines[0]["id"]
    else:
        machine_data = await sandbox_manager.create_sandbox(name="Agent Machine")
        machine_id = machine_data["id"]
        # Wait briefly for startup
        await asyncio.sleep(5)

    # Run agent in background
    background_tasks.add_task(
        orchestrator.run_single_task,
        machine_id,
        req.prompt,
        manager.broadcast_action,
    )

    return {
        "status": "started",
        "machine_id": machine_id,
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
