"""
OpenDesktop - Sandbox manager factory.
Uses local Docker by default; remote SSH mode for VPS deployments.
"""
import os
from typing import Union

from .config import SANDBOX_MODE, HETZNER_HOST

_manager = None


def get_sandbox_manager():
    global _manager
    if _manager is not None:
        return _manager

    mode = SANDBOX_MODE
    if mode == "remote" or (mode != "local" and HETZNER_HOST):
        from .docker_manager import RemoteDockerManager
        _manager = RemoteDockerManager()
        print(f"[Sandbox] Remote mode → {HETZNER_HOST or 'SSH host'}")
    else:
        from .local_docker_manager import LocalDockerManager
        _manager = LocalDockerManager()
        print("[Sandbox] Local Docker mode")

    return _manager


# Back-compat alias used across the codebase
sandbox_manager = get_sandbox_manager()
