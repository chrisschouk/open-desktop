"""
OpenDesktop - Vision-Driven Computer Agent Engine
Observes desktop screenshots and executes computer control actions.
"""
import os
import json
import asyncio
import base64
import aiohttp
from typing import Optional, Callable, List

from .config import VISION_API_KEY, VISION_API_URL, VISION_MODEL, MAX_VISION_STEPS

AGENT_SYSTEM_PROMPT = """You are a computer-use AI agent operating a real Linux desktop.
You can see the screen via screenshots and control the computer with these actions:

AVAILABLE ACTIONS (respond with exactly one JSON object):
1. {"action": "click", "x": <int>, "y": <int>} - Click at screen coordinates
2. {"action": "double_click", "x": <int>, "y": <int>} - Double-click
3. {"action": "right_click", "x": <int>, "y": <int>} - Right-click
4. {"action": "type", "text": "<string>"} - Type text into the focused field
5. {"action": "press_key", "key": "<key>"} - Press a key (Return, Tab, Escape, ctrl+a, etc.)
6. {"action": "move", "x": <int>, "y": <int>} - Move mouse without clicking
7. {"action": "scroll", "amount": <int>} - Scroll (negative = down, positive = up)
8. {"action": "bash", "command": "<shell command>"} - Run a shell command
9. {"action": "done", "summary": "<what was accomplished>"} - Task complete

RULES:
- The screen resolution is 1280x800. Coordinates must be within this range.
- Always observe the screenshot carefully before acting.
- Click on visible desktop icons or UI elements by their coordinates, or use bash commands to launch apps:
  - Google Chrome: `google-chrome-stable --no-sandbox --disable-gpu http://google.com &`
  - VS Code: `code --no-sandbox --user-data-dir=/home/agent/.vscode-data &`
  - Obsidian: `obsidian --no-sandbox /home/agent/ObsidianVault &`
- To type in a field: first click on the field, then use type action.
- For URLs: click the address bar, select all (ctrl+a), then type the URL, then press Return.
- Work step by step. One action per response.
- When the task is fully complete, use the "done" action.

Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.
You may include a "thought" field to explain your reasoning:
{"thought": "I see the desktop icon for VS Code, double-clicking it to launch", "action": "double_click", "x": 60, "y": 140}
"""


class AgentRunner:
    """
    Drives a sandbox using a vision model that observes screenshots and issues actions.
    """

    def __init__(self):
        self.conversation_history: List[dict] = []
        self.max_steps = MAX_VISION_STEPS
        self.step_count = 0

    async def _call_vision_model(
        self,
        screenshot_b64: str,
        conversation_history: List[dict],
        user_message: str = "",
    ) -> dict:
        """Send screenshot to vision model and get next action."""
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT}
        ]

        for msg in conversation_history[-12:]:
            messages.append(msg)

        content = []
        if user_message:
            content.append({"type": "text", "text": user_message})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{screenshot_b64}"
            }
        })
        content.append({
            "type": "text",
            "text": "Based on what you see in this screenshot, what is your next action? Respond with a single JSON object."
        })

        messages.append({"role": "user", "content": content})

        api_key = (
            os.getenv("VISION_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("API_KEY")
            or VISION_API_KEY
        )
        
        if api_key.startswith("sk-proj-") or (api_key.startswith("sk-") and not api_key.startswith("sk-or-") and not api_key.startswith("sk-ant-")):
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            model = os.getenv("VISION_MODEL", VISION_MODEL)
        else:
            url = os.getenv("VISION_API_URL", VISION_API_URL)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/totalaudiopromo/open-desktop",
                "X-Title": "OpenDesktop OpenWorker",
            }
            model = os.getenv("VISION_MODEL", VISION_MODEL)

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.2,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"[AgentEngine] API error {resp.status}: {error_text}")
                        if resp.status == 401:
                            return {"action": "done", "summary": "Invalid API key (401). Please check your key."}
                        return {"action": "done", "summary": f"API error: {resp.status}"}

                    data = await resp.json()
                    response_text = data["choices"][0]["message"]["content"].strip()
                    return self._parse_action(response_text)

        except Exception as e:
            print(f"[AgentEngine] Vision call failed: {e}")
            return {"action": "done", "summary": f"Call failed: {str(e)}"}

    def _parse_action(self, text: str) -> dict:
        """Extract JSON action from model response."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```" in text:
            for block in text.split("```"):
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    continue

        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        print(f"[AgentEngine] Could not parse action from: {text[:200]}")
        return {"action": "done", "summary": "Could not parse response"}

    async def run_task(
        self,
        sandbox_id: str,
        prompt: str,
        sandbox_manager,
        broadcast_action: Optional[Callable] = None
    ):
        """
        Main agent loop: observe → think → act → repeat.
        Uses per-run conversation history so concurrent tasks do not collide.
        """
        step_count = 0
        conversation_history: List[dict] = [{
            "role": "user",
            "content": f"Your task: {prompt}"
        }]

        if broadcast_action:
            await broadcast_action(sandbox_id, {
                "type": "agent_event",
                "step": 0,
                "thought": f"Starting task: {prompt}",
                "action_type": "task_start",
                "agent": "Vision Agent",
                "machine_id": sandbox_id,
            })

        while step_count < self.max_steps:
            step_count += 1

            screenshot_b64 = await sandbox_manager.get_screenshot_base64(sandbox_id)
            if not screenshot_b64:
                print(f"[AgentEngine] No screenshot for {sandbox_id}, waiting...")
                await asyncio.sleep(2)
                continue

            context = f"Step {step_count}/{self.max_steps}. Task: {prompt}"
            action = await self._call_vision_model(screenshot_b64, conversation_history, context)
            conversation_history.append({
                "role": "assistant",
                "content": json.dumps(action),
            })

            thought = action.get("thought", "")
            action_type = action.get("action", "unknown")

            print(f"[AgentEngine] Step {step_count}: {action_type} - {thought}")

            if broadcast_action:
                await broadcast_action(sandbox_id, {
                    "type": "action",
                    "step": step_count,
                    "thought": thought or f"Executing: {action_type}",
                    "action_type": action_type,
                    "agent": "Vision Agent",
                    "machine_id": sandbox_id,
                    "details": {k: v for k, v in action.items()
                                if k not in ("thought", "action")},
                })

            if action_type == "done":
                summary = action.get("summary", "Task completed")
                if broadcast_action:
                    await broadcast_action(sandbox_id, {
                        "type": "action",
                        "step": step_count,
                        "thought": f"Completed: {summary}",
                        "action_type": "done",
                        "agent": "Vision Agent",
                        "machine_id": sandbox_id,
                    })
                return {"status": "completed", "summary": summary, "steps": step_count}

            # Execute action
            await sandbox_manager.execute_action(sandbox_id, action)
            await asyncio.sleep(1)

        if broadcast_action:
            await broadcast_action(sandbox_id, {
                "type": "action",
                "step": step_count,
                "thought": "Maximum steps reached. Task may be incomplete.",
                "action_type": "max_steps",
                "agent": "Vision Agent",
                "machine_id": sandbox_id,
            })

        return {"status": "max_steps_reached", "steps": step_count}


agent_runner = AgentRunner()
