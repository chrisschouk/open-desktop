"""
MCP-style tool registry — sandbox and playbook tools exposed to agents/connectors.
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional

ToolHandler = Callable[..., Awaitable[Any]]

_tools: Dict[str, dict] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict,
    handler: ToolHandler,
):
    _tools[name] = {
        "name": name,
        "description": description,
        "inputSchema": parameters,
        "handler": handler,
    }


def list_tools() -> List[dict]:
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        }
        for t in _tools.values()
    ]


async def call_tool(name: str, arguments: dict) -> Any:
    tool = _tools.get(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    return await tool["handler"](**arguments)


def _register_builtin_tools():
    from .sandbox_factory import sandbox_manager
    from .playbook_executor import run_playbook, list_playbooks
    from .agent_runner import agent_runner

    async def desktop_screenshot(machine_id: str) -> dict:
        b64 = await sandbox_manager.get_screenshot_base64(machine_id)
        return {"machine_id": machine_id, "has_image": bool(b64)}

    async def desktop_click(machine_id: str, x: int, y: int) -> dict:
        return await sandbox_manager.execute_action(machine_id, {"action": "click", "x": x, "y": y}) or {}

    async def desktop_type(machine_id: str, text: str) -> dict:
        return await sandbox_manager.execute_action(machine_id, {"action": "type", "text": text}) or {}

    async def list_sandboxes() -> dict:
        return {"machines": sandbox_manager.list_sandboxes()}

    async def run_playbook_tool(playbook_id: str, prompt: str) -> dict:
        return await run_playbook(playbook_id, prompt, sandbox_manager, agent_runner, None)

    register_tool(
        "desktop_screenshot",
        "Capture a JPEG screenshot from an OpenDesktop sandbox machine.",
        {
            "type": "object",
            "properties": {"machine_id": {"type": "string"}},
            "required": ["machine_id"],
        },
        desktop_screenshot,
    )
    register_tool(
        "desktop_click",
        "Left-click at screen coordinates in a sandbox.",
        {
            "type": "object",
            "properties": {
                "machine_id": {"type": "string"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["machine_id", "x", "y"],
        },
        desktop_click,
    )
    register_tool(
        "desktop_type",
        "Type text into the focused field in a sandbox.",
        {
            "type": "object",
            "properties": {
                "machine_id": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["machine_id", "text"],
        },
        desktop_type,
    )
    register_tool(
        "list_sandboxes",
        "List all OpenDesktop sandbox machines and their status.",
        {"type": "object", "properties": {}},
        list_sandboxes,
    )
    register_tool(
        "run_playbook",
        "Run a declarative OpenDesktop playbook by ID.",
        {
            "type": "object",
            "properties": {
                "playbook_id": {"type": "string"},
                "prompt": {"type": "string"},
            },
            "required": ["playbook_id", "prompt"],
        },
        run_playbook_tool,
    )


_register_builtin_tools()
