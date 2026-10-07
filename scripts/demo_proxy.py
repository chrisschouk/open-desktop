#!/usr/bin/env python3
"""Single-port demo proxy: static client + /api + /ws → backend."""
from __future__ import annotations

import asyncio
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import httpx

CLIENT = Path(__file__).resolve().parent.parent / "client"
API = "http://127.0.0.1:8000"
WS_API = "ws://127.0.0.1:8000"

app = FastAPI()


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_api(path: str, request: Request):
    url = f"{API}/api/{path}"
    if request.url.query:
        url += f"?{request.url.query}"
    body = await request.body()
    # Drop Cloudflare client-IP headers so the API still treats this as local
    # (key saves are localhost-only without OPENDESKTOP_API_TOKEN).
    drop = {"host", "content-length", "x-forwarded-for", "x-real-ip", "cf-connecting-ip"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in drop}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.request(request.method, url, content=body, headers=headers)
    out_headers = {
        k: v
        for k, v in r.headers.items()
        if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
    }
    return Response(content=r.content, status_code=r.status_code, headers=out_headers)


@app.websocket("/ws/{path:path}")
async def proxy_ws(websocket: WebSocket, path: str):
    await websocket.accept()
    import websockets

    upstream = f"{WS_API}/ws/{path}"
    try:
        async with websockets.connect(upstream) as remote:
            async def client_to_server():
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if "text" in msg:
                            await remote.send(msg["text"])
                        elif "bytes" in msg:
                            await remote.send(msg["bytes"])
                except WebSocketDisconnect:
                    pass

            async def server_to_client():
                try:
                    async for message in remote:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception:
                    pass

            await asyncio.gather(client_to_server(), server_to_client())
    except Exception:
        await websocket.close()


@app.get("/")
async def index():
    return FileResponse(CLIENT / "index.html")


app.mount("/", StaticFiles(directory=str(CLIENT), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8890)
