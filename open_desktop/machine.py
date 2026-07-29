import time
import requests
import asyncio
from typing import Optional, Dict, Any, List

class Machine:
    """
    OpenDesktop Machine Client.
    Represents an isolated, persistent cloud desktop sandbox.
    """
    def __init__(self, machine_id: str, api_key: Optional[str] = None, base_url: str = "http://localhost:8000"):
        self.machine_id = machine_id
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def see_screen(self, format: str = "jpeg") -> bytes:
        """Capture high-resolution screenshot of the cloud machine display."""
        url = f"{self.base_url}/api/v1/machines/{self.machine_id}/screenshot?format={format}"
        res = requests.get(url, headers=self.headers, timeout=10)
        res.raise_for_status()
        return res.content

    def click_left(self, x: int, y: int) -> dict:
        """Perform a left mouse click at (x, y)."""
        url = f"{self.base_url}/api/v1/machines/{self.machine_id}/actions"
        payload = {"type": "click", "x": x, "y": y, "button": "left"}
        res = requests.post(url, json=payload, headers=self.headers, timeout=10)
        return res.json()

    def keyboard_type(self, text: str) -> dict:
        """Type text into active input field."""
        url = f"{self.base_url}/api/v1/machines/{self.machine_id}/actions"
        payload = {"type": "type", "text": text}
        res = requests.post(url, json=payload, headers=self.headers, timeout=10)
        return res.json()

    def run_shell(self, command: str) -> dict:
        """Run bash command inside the sandbox."""
        url = f"{self.base_url}/api/v1/machines/{self.machine_id}/actions"
        payload = {"type": "shell", "command": command}
        res = requests.post(url, json=payload, headers=self.headers, timeout=30)
        return res.json()

class Session:
    """
    OpenDesktop Session.
    Encapsulates a sequence of actions for a single job or agent task loop.
    Includes higher-order flow helpers (open_url, fill_form, run_playbook).
    """
    def __init__(self, machine: Machine, session_id: Optional[str] = None, job_name: str = "Agent Job"):
        self.machine = machine
        self.session_id = session_id or f"sess_{int(time.time())}"
        self.job_name = job_name
        self.status = "running"
        self.started_at = time.time()
        self.completed_at = None
        self.action_history: List[Dict[str, Any]] = []

    def see(self) -> bytes:
        return self.machine.see_screen()

    def act(self, action_type: str, **kwargs) -> dict:
        if action_type == "click":
            res = self.machine.click_left(kwargs.get("x", 0), kwargs.get("y", 0))
        elif action_type == "type":
            res = self.machine.keyboard_type(kwargs.get("text", ""))
        elif action_type == "shell":
            res = self.machine.run_shell(kwargs.get("command", ""))
        else:
            res = {"status": "executed", "action": action_type}
        
        event = {
            "timestamp": time.time(),
            "action": action_type,
            "args": kwargs,
            "result": res
        }
        self.action_history.append(event)
        return res

    def open_url(self, url: str) -> dict:
        """Higher-order helper: click address bar, type URL, and press Return."""
        self.act("click", x=300, y=96)
        self.act("type", text=url)
        return self.act("press", key="Return")

    def fill_form(self, fields: Dict[str, str]) -> dict:
        """Higher-order helper: multi-step form entry."""
        results = []
        for name, value in fields.items():
            res = self.act("type", text=value)
            results.append(res)
            self.act("press", key="Tab")
        return {"status": "form_filled", "fields_count": len(fields)}

    def run_playbook(self, playbook_id: str, prompt: str) -> dict:
        """Higher-order helper: dispatch declarative playbook campaign."""
        url = f"{self.machine.base_url}/api/v1/playbooks/run"
        res = requests.post(url, json={"playbook_id": playbook_id, "prompt": prompt}, headers=self.machine.headers, timeout=10)
        return res.json()

    def finish(self, status: str = "completed") -> dict:
        self.status = status
        self.completed_at = time.time()
        return {
            "session_id": self.session_id,
            "job_name": self.job_name,
            "status": self.status,
            "total_actions": len(self.action_history),
            "duration_sec": round(self.completed_at - self.started_at, 2)
        }

class AsyncSession:
    """Async variant for high-throughput asyncio loops."""
    def __init__(self, machine: Machine, session_id: Optional[str] = None):
        self.session = Session(machine, session_id)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        status = "failed" if exc_type else "completed"
        self.session.finish(status=status)

    async def see(self):
        return await asyncio.to_thread(self.session.see)

    async def act(self, action_type: str, **kwargs):
        return await asyncio.to_thread(self.session.act, action_type, **kwargs)
