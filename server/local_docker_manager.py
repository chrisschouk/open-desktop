"""
Local Docker sandbox manager — runs sandboxes on the host Docker daemon.
Default mode for open-source self-hosting.
"""
import os
import time
import uuid
import base64
import asyncio
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .config import SANDBOX_IMAGE, LOCAL_DOCKER_HOST

VNC_PORT_START = 6500
DAEMON_PORT_START = 9500


@dataclass
class SandboxInfo:
    id: str
    name: str
    container_name: str
    vnc_port: int
    daemon_port: int
    status: str = "starting"
    created_at: float = field(default_factory=time.time)
    width: int = 1280
    height: int = 800

    @property
    def daemon_host(self) -> str:
        # When server runs in Docker, reach host sandboxes via host.docker.internal
        if os.path.exists("/.dockerenv"):
            return LOCAL_DOCKER_HOST
        return "127.0.0.1"

    @property
    def daemon_url(self) -> str:
        return f"http://{self.daemon_host}:{self.daemon_port}"

    @property
    def vnc_url(self) -> str:
        return f"http://{self.daemon_host}:{self.vnc_port}/vnc.html"

    @property
    def vnc_ws_url(self) -> str:
        return f"ws://{self.daemon_host}:{self.vnc_port}/websockify"

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


class LocalDockerManager:
    """Manages sandbox containers via local Docker CLI."""

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

    async def _docker_exec(self, *args: str) -> tuple:
        proc = await asyncio.create_subprocess_exec(
            "docker", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def create_sandbox(
        self, name: Optional[str] = None, width: int = 1280, height: int = 800
    ) -> dict:
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

        rc, stdout, stderr = await self._docker_exec(
            "run", "-d",
            "--name", container_name,
            "-p", f"{vnc_port}:6080",
            "-p", f"{daemon_port}:8000",
            "-e", f"SCREEN_WIDTH={width}",
            "-e", f"SCREEN_HEIGHT={height}",
            "--memory=1g", "--cpus=1",
            SANDBOX_IMAGE,
        )

        if rc == 0:
            info.status = "starting"
            asyncio.create_task(self._wait_for_healthy(sandbox_id))
        else:
            info.status = "error"
            print(f"[LocalDocker] Failed to create {sandbox_id}: {stderr}")

        return info.to_dict()

    async def _wait_for_healthy(self, sandbox_id: str, timeout: int = 60):
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{info.daemon_url}/health",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as resp:
                        if resp.status == 200:
                            info.status = "running"
                            print(f"[LocalDocker] {sandbox_id} is healthy")
                            return
            except Exception:
                pass
            await asyncio.sleep(2)

        info.status = "unhealthy"
        print(f"[LocalDocker] {sandbox_id} failed health check")

    async def stop_sandbox(self, sandbox_id: str) -> bool:
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return False
        await self._docker_exec("stop", info.container_name)
        info.status = "stopped"
        return True

    async def start_sandbox(self, sandbox_id: str) -> bool:
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return False
        await self._docker_exec("start", info.container_name)
        info.status = "starting"
        asyncio.create_task(self._wait_for_healthy(sandbox_id))
        return True

    async def destroy_sandbox(self, sandbox_id: str) -> bool:
        info = self.sandboxes.get(sandbox_id)
        if not info:
            return False
        await self._docker_exec("rm", "-f", info.container_name)
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
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{info.daemon_url}/action",
                    json=action,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return await resp.json()
        except Exception as e:
            print(f"[LocalDocker] Action failed for {sandbox_id}: {e}")
            return None

    async def execute_bash(self, sandbox_id: str, command: str) -> Optional[dict]:
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{info.daemon_url}/bash",
                    json={"command": command},
                    timeout=aiohttp.ClientTimeout(total=35),
                ) as resp:
                    return await resp.json()
        except Exception as e:
            print(f"[LocalDocker] Bash failed: {e}")
            return None

    async def get_screenshot(self, sandbox_id: str, format: str = "jpeg") -> Optional[bytes]:
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status not in ("running", "starting"):
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{info.daemon_url}/screenshot?format={format}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            print(f"[LocalDocker] Screenshot failed: {e}")
        return None

    async def get_screenshot_base64(self, sandbox_id: str) -> Optional[str]:
        data = await self.get_screenshot(sandbox_id)
        if data:
            return base64.b64encode(data).decode("ascii")
        return None

    async def get_cursor_position(self, sandbox_id: str) -> Optional[dict]:
        info = self.sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{info.daemon_url}/cursor",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    return await resp.json()
        except Exception:
            return None
