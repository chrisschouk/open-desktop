"""
Lifecycle hooks — observe or gate agent runs (OpenClaw-inspired, minimal).
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional

HookHandler = Callable[[dict], Awaitable[Optional[dict]]]

_registry: Dict[str, List[HookHandler]] = {
    "before_agent_run": [],
    "after_agent_run": [],
    "before_tool_call": [],
    "after_tool_call": [],
}


def on(hook_name: str, handler: HookHandler):
    if hook_name not in _registry:
        _registry[hook_name] = []
    _registry[hook_name].append(handler)


async def emit(hook_name: str, payload: dict) -> dict:
    """Run hooks in order; handlers may mutate/return payload. Return False in payload to block."""
    data = dict(payload)
    for handler in _registry.get(hook_name, []):
        try:
            result = await handler(data)
            if result is not None:
                data = result
            if data.get("_block"):
                return data
        except Exception as e:
            print(f"[Hooks] {hook_name} handler error: {e}")
    return data


async def _log_hook(payload: dict) -> dict:
    step = payload.get("step", "-")
    action = payload.get("action_type", payload.get("hook", ""))
    print(f"[Hook] {action} step={step}")
    return payload


# Default observability hook
on("before_agent_run", _log_hook)
on("after_agent_run", _log_hook)
