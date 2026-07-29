import os
import requests
from typing import Optional, Dict

DEFAULT_BASE_URL = os.getenv("ORGO_BASE_URL", "http://localhost:8000")

class Computer:
    def __init__(self, computer_id: Optional[str] = None, name: Optional[str] = "Orgo Computer", base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.computer_id = computer_id
        
        if not self.computer_id:
            # Provision new computer via API
            try:
                res = requests.post(f"{self.base_url}/api/v1/computers", json={"name": name})
                if res.status_code == 200:
                    data = res.json()["computer"]
                    self.computer_id = data["id"]
                    self.vnc_url = data.get("vnc_url")
                else:
                    self.computer_id = "cmp_default"
            except Exception:
                self.computer_id = "cmp_default"

    def left_click(self, x: int, y: int) -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/click", json={"x": x, "y": y, "button": "left"})
        return res.json()

    def right_click(self, x: int, y: int) -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/click", json={"x": x, "y": y, "button": "right"})
        return res.json()

    def double_click(self, x: int, y: int) -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/click", json={"x": x, "y": y, "clicks": 2})
        return res.json()

    def type(self, text: str) -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/type", json={"text": text})
        return res.json()

    def press(self, key: str) -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/press", json={"key": key})
        return res.json()

    def bash(self, command: str) -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/bash", json={"command": command})
        return res.json()

    def prompt(self, instruction: str, model: str = "nousresearch/hermes-3-llama-3.1-405b") -> dict:
        res = requests.post(f"{self.base_url}/api/v1/computers/{self.computer_id}/prompt", json={"prompt": instruction, "model": model})
        return res.json()

    def screenshot(self) -> bytes:
        res = requests.get(f"{self.base_url}/api/v1/computers/{self.computer_id}/screenshot")
        return res.content

    def shutdown(self) -> dict:
        res = requests.delete(f"{self.base_url}/api/v1/computers/{self.computer_id}")
        return res.json()
