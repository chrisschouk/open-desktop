"""
OpenDesktop - Remote Docker Sandbox Manager
Connects to Docker on a remote Hetzner VPS to manage real Linux desktop containers.
"""
import os
import io
import time
import uuid
import base64
import asyncio
import aiohttp
from typing import Dict, List, Optional
from PIL import Image
from dataclasses import dataclass, field


# Remote VPS configuration
HETZNER_HOST = os.getenv("HETZNER_HOST", "46.225.66.39")
SANDBOX_IMAGE = "opendesktop-sandbox:latest"

# Port ranges for sandbox containers (avoid 9200 ElasticSearch port)
VNC_PORT_START = 6500
DAEMON_PORT_START = 9500


@dataclass
class SandboxInfo:
    """Tracks a running sandbox container on the remote VPS."""
    id: str
    name: str
    container_name: str
    vnc_port: int       # noVNC WebSocket port on VPS
    daemon_port: int    # Agent daemon REST API port on VPS
    status: str = "starting"
    created_at: float = field(default_factory=time.time)
    width: int = 1280
    height: int = 800

    @property
    def daemon_url(self) -> str:
        return f"http://{HETZNER_HOST}:{self.daemon_port}"

    @property
    def vnc_url(self) -> str:
        return f"http://{HETZNER_HOST}:{self.vnc_port}/vnc.html"

    @property
    def vnc_ws_url(self) -> str:
        return f"ws://{HETZNER_HOST}:{self.vnc_port}/websockify"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "resolution": f"{self.width}x{self.height}",
            "created_at": self.created_at,
            "daemon_url": self.daemon_url,
            "vnc_url": self.vnc_url,
            "vnc_ws_url": self.vnc_ws_url,
        }


class RemoteDockerManager:
    """
    Manages sandbox containers on a remote Hetzner VPS via SSH + Docker CLI.
    Each sandbox is a full Linux desktop (Xvfb + XFCE + Chromium + x11vnc + noVNC)
    with a pyautogui-based agent daemon for programmatic control.
    """

    def __init__(self):
        self.sandboxes: Dict[str, SandboxInfo] = {}
        self._next_vnc_port = VNC_PORT_START
        self._next_daemon_port = DAEMON_PORT_START

    def _allocate_ports(self) -> tuple:
        vnc = self._next_vnc_port
        daemon = self._next_daemon_port
        self._next_vnc_port += 1
        self._next_daemon_port += 1
        return vnc, daemon

    async def _ssh_exec(self, command: str) -> tuple:
        """Execute a command on the remote VPS via SSH."""
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
            "hetzner", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def create_sandbox(self, name: Optional[str] = None,
                              width: int = 1280, height: int = 800) -> dict:
        sandbox_id = f"sbx_{uuid.uuid4().hex[:8]}"
        container_name = f"opendesktop-{sandbox_id}"
        sandbox_name = name or f"Machine-{sandbox_id}"
        vnc_port, daemon_port = self._allocate_ports()

        info = SandboxInfo(
            id=sandbox_id,
            name=sandbox_name,
            container_name=container_name,
            vnc_port=vnc_port,
            daemon_port=daemon_port,
            width=width,
            height=height,
        )
        self.sandboxes[sandbox_id] = info

        # Launch container on VPS
        docker_cmd = (
            f"docker run -d --name {container_name} "
            f"-p {vnc_port}:6080 "
            f"-p {daemon_port}:8000 "
            f"-e SCREEN_WIDTH={width} "
            f"-e SCREEN_HEIGHT={height} "
            f"--memory=1g --cpus=1 "
            f"{SANDBOX_IMAGE}"
        )

        rc, stdout, stderr = await self._ssh_exec(docker_cmd)
        if rc == 0:
            info.status = "starting"
            # Wait for the daemon to be ready
            asyncio.create_task(self._wait_for_healthy(sandbox_id))
        else:
            info.status = "error"
            print(f"[RemoteDocker] Failed to create {sandbox_id}: {stderr}")

        return info.to_dict()

    async def _wait_for_healthy(self, sandbox_id: str, timeout: int = 30):
        """Poll the agent daemon health endpoint until it responds."""
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{info.daemon_url}/health", timeout=aiohttp.ClientTimeout(total=3)
                    ) as resp:
                        if resp.status == 200:
                            info.status = "running"
                            print(f"[RemoteDocker] {sandbox_id} is healthy and running")
                            return
            except Exception:
                pass
            await asyncio.sleep(2)

        info.status = "unhealthy"
        print(f"[RemoteDocker] {sandbox_id} failed health check after {timeout}s")

    async def stop_sandbox(self, sandbox_id: str) -> bool:
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return False
        await self._ssh_exec(f"docker stop {info.container_name}")
        info.status = "stopped"
        return True

    async def start_sandbox(self, sandbox_id: str) -> bool:
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return False
        await self._ssh_exec(f"docker start {info.container_name}")
        info.status = "starting"
        asyncio.create_task(self._wait_for_healthy(sandbox_id))
        return True

    async def destroy_sandbox(self, sandbox_id: str) -> bool:
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return False
        await self._ssh_exec(f"docker rm -f {info.container_name}")
        del self.sandboxes[sandbox_id]
        return True

    def list_sandboxes(self) -> List[dict]:
        return [s.to_dict() for s in self.sandboxes.values()]

    def get_sandbox(self, sandbox_id: str) -> Optional[dict]:
        info = self.sandboxes.get(sandbox_id)
        return info.to_dict() if info else None

    def get_info(self, sandbox_id: str) -> Optional[SandboxInfo]:
        return self.sandboxes.get(sandbox_id)

    async def execute_action(self, sandbox_id: str, action: dict) -> Optional[dict]:
        """Forward an action to the sandbox's agent daemon."""
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{info.daemon_url}/action",
                    json=action,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            print(f"[RemoteDocker] Action failed for {sandbox_id}: {e}")
            return None

    async def execute_bash(self, sandbox_id: str, command: str) -> Optional[dict]:
        """Run a bash command inside the sandbox."""
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{info.daemon_url}/bash",
                    json={"command": command},
                    timeout=aiohttp.ClientTimeout(total=35)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            print(f"[RemoteDocker] Bash failed for {sandbox_id}: {e}")
            return None

    async def get_screenshot(self, sandbox_id: str, format: str = "jpeg") -> Optional[bytes]:
        """Fetch a screenshot from the sandbox's agent daemon."""
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status not in ("running", "starting"):
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{info.daemon_url}/screenshot?format={format}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            print(f"[RemoteDocker] Screenshot failed for {sandbox_id}: {e}")
        return None

    async def get_screenshot_base64(self, sandbox_id: str) -> Optional[str]:
        """Fetch screenshot as base64 string."""
        data = await self.get_screenshot(sandbox_id)
        if data:
            return base64.b64encode(data).decode("ascii")
        return None

    async def get_cursor_position(self, sandbox_id: str) -> Optional[dict]:
        """Get current cursor position from the sandbox."""
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{info.daemon_url}/cursor",
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    return await resp.json()
        except Exception:
            return None


# Global singleton
sandbox_manager = RemoteDockerManager()
