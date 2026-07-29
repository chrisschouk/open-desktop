"""
OpenDesktop - LLM-Driven Computer Agent
Uses OpenRouter (Hermes 3 / GPT-4o) to observe screenshots and decide actions.
"""
import os
import json
import asyncio
import base64
import aiohttp
from typing import Optional, Callable, List

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Use a vision-capable model
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

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
  - Hermes Desktop: `cd /home/agent/Projects/hermes-desktop && node index.js &`
  - Claude Code CLI: `claude` or `npx @anthropic-ai/claude-code`
- To type in a field: first click on the field, then use type action.
- For URLs: click the address bar, select all (ctrl+a), then type the URL, then press Return.
- Work step by step. One action per response.
- When the task is fully complete, use the "done" action.

Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.
You may include a "thought" field to explain your reasoning:
{"thought": "I see the desktop icon for VS Code, double-clicking it to launch", "action": "double_click", "x": 60, "y": 140}
"""


class LLMAgentRunner:
    """
    Drives a sandbox using an LLM that observes screenshots and issues actions.
    """

    def __init__(self):
        self.conversation_history: List[dict] = []
        self.max_steps = 25
        self.step_count = 0

    async def _call_llm(self, screenshot_b64: str, user_message: str = "") -> dict:
        """Send screenshot to LLM and get next action."""
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT}
        ]

        # Add conversation history (last 6 exchanges to keep context manageable)
        for msg in self.conversation_history[-12:]:
            messages.append(msg)

        # Current turn with screenshot
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

        # Auto-detect API endpoint & headers based on key format
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or OPENROUTER_API_KEY
        
        if api_key.startswith("sk-proj-") or (api_key.startswith("sk-") and not api_key.startswith("sk-or-") and not api_key.startswith("sk-ant-")):
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        else:
            url = OPENROUTER_URL
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://opendesktop.chrisscho.uk",
                "X-Title": "OpenDesktop Agent",
            }
            model = os.getenv("LLM_MODEL", LLM_MODEL)

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
                        print(f"[LLMAgent] API error {resp.status}: {error_text}")
                        if resp.status == 401:
                            return {"action": "done", "summary": "Invalid API key (401). Please check your key."}
                        return {"action": "done", "summary": f"LLM API error: {resp.status}"}

                    data = await resp.json()
                    response_text = data["choices"][0]["message"]["content"].strip()

                    # Store in history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response_text
                    })

                    # Parse JSON response
                    return self._parse_action(response_text)

        except Exception as e:
            print(f"[LLMAgent] LLM call failed: {e}")
            return {"action": "done", "summary": f"LLM call failed: {str(e)}"}

    def _parse_action(self, text: str) -> dict:
        """Extract JSON action from LLM response."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```" in text:
            for block in text.split("```"):
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    continue

        # Try finding JSON object in text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        print(f"[LLMAgent] Could not parse action from: {text[:200]}")
        return {"action": "done", "summary": "Could not parse LLM response"}

    async def run_task(
        self,
        sandbox_id: str,
        prompt: str,
        sandbox_manager,
        broadcast_action: Optional[Callable] = None
    ):
        """
        Main agent loop: observe → think → act → repeat.
        """
        self.step_count = 0
        self.conversation_history = []

        # Add user task to history
        self.conversation_history.append({
            "role": "user",
            "content": f"Your task: {prompt}"
        })

        # Broadcast task start
        if broadcast_action:
            await broadcast_action(sandbox_id, {
                "type": "agent_event",
                "step": 0,
                "thought": f"Starting task: {prompt}",
                "action_type": "task_start",
                "agent": "Hermes Agent",
                "machine_id": sandbox_id,
            })

        while self.step_count < self.max_steps:
            self.step_count += 1

            # 1. Observe - take screenshot
            screenshot_b64 = await sandbox_manager.get_screenshot_base64(sandbox_id)
            if not screenshot_b64:
                print(f"[LLMAgent] No screenshot for {sandbox_id}, waiting...")
                await asyncio.sleep(2)
                continue

            # 2. Think - ask LLM what to do
            context = f"Step {self.step_count}/{self.max_steps}. Task: {prompt}"
            action = await self._call_llm(screenshot_b64, context)

            thought = action.get("thought", "")
            action_type = action.get("action", "unknown")

            print(f"[LLMAgent] Step {self.step_count}: {action_type} - {thought}")

            # 3. Broadcast to frontend
            if broadcast_action:
                await broadcast_action(sandbox_id, {
                    "type": "action",
                    "step": self.step_count,
                    "thought": thought or f"Executing: {action_type}",
                    "action_type": action_type,
                    "agent": "Hermes Agent",
                    "machine_id": sandbox_id,
                    "details": {k: v for k, v in action.items()
                                if k not in ("thought", "action")},
                })

            # 4. Check for completion
            if action_type == "done":
                summary = action.get("summary", "Task completed")
                if broadcast_action:
                    await broadcast_action(sandbox_id, {
                        "type": "action",
                        "step": self.step_count,
                        "thought": f"✅ {summary}",
                        "action_type": "done",
                        "agent": "Hermes Agent",
                        "machine_id": sandbox_id,
                    })
                return {"status": "completed", "summary": summary, "steps": self.step_count}

            # 5. Act - execute action in sandbox
            if action_type == "bash":
                result = await sandbox_manager.execute_bash(
                    sandbox_id, action.get("command", "echo 'no command'")
                )
            else:
                result = await sandbox_manager.execute_action(sandbox_id, action)

            # Store result in history for context
            if result:
                self.conversation_history.append({
                    "role": "user",
                    "content": f"Action result: {json.dumps(result)}"
                })

            # Brief pause to let the UI update
            await asyncio.sleep(1.5)

        # Max steps reached
        if broadcast_action:
            await broadcast_action(sandbox_id, {
                "type": "action",
                "step": self.step_count,
                "thought": "⚠️ Maximum steps reached. Task may be incomplete.",
                "action_type": "max_steps",
                "agent": "Hermes Agent",
                "machine_id": sandbox_id,
            })

        return {"status": "max_steps_reached", "steps": self.step_count}


# Global singleton
agent_runner = LLMAgentRunner()
