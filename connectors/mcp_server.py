#!/usr/bin/env python3
"""
OpenDesktop MCP server (stdio) — exposes sandbox tools for Buzz agents and other MCP clients.

Usage:
  OPENDESKTOP_API_URL=http://localhost:8000 python connectors/mcp_server.py

Configure in Goose/Codex MCP settings as a stdio server.
"""
import asyncio
import json
import os
import sys

# Minimal MCP JSON-RPC over stdio (tools/list + tools/call)
API_URL = os.getenv("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.getenv("OPENDESKTOP_API_TOKEN", "")


def _headers():
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


async def api_get(path: str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}{path}", headers=_headers()) as resp:
            return await resp.json()


async def api_post(path: str, body: dict):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}{path}", json=body, headers=_headers()) as resp:
            return await resp.json()


async def handle_request(req: dict) -> dict:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "opendesktop", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        data = await api_get("/api/v1/tools")
        tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in data.get("tools", [])
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        data = await api_post("/api/v1/tools/call", {"name": name, "arguments": arguments})
        text = json.dumps(data.get("result", data), indent=2)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": False},
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


async def main():
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())

    while True:
        line = await reader.readline()
        if not line:
            break
        line = line.decode().strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = await handle_request(req)
            if resp is not None:
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
            writer.write((json.dumps(err) + "\n").encode())
            await writer.drain()


if __name__ == "__main__":
    asyncio.run(main())
