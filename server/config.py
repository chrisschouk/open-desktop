"""
OpenDesktop configuration — env-driven, no hardcoded infrastructure.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
DATA_DIR = Path(os.getenv("OPENDESKTOP_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
VAULT_PATH = Path(os.getenv("OPENDESKTOP_VAULT_PATH", DATA_DIR / "vault"))
PERSONAS_DIR = Path(os.getenv("OPENDESKTOP_PERSONAS_DIR", Path(__file__).resolve().parent.parent / "personas"))

# Sandbox runtime
SANDBOX_MODE = os.getenv("SANDBOX_MODE", "local").lower()  # local | remote
HETZNER_HOST = os.getenv("HETZNER_HOST", "")
SSH_HOST_ALIAS = os.getenv("SSH_HOST_ALIAS", "hetzner")
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "opendesktop-sandbox:latest")
AUTO_PROVISION_FLEET = os.getenv("AUTO_PROVISION_FLEET", "false").lower() == "true"
LOCAL_DOCKER_HOST = os.getenv("LOCAL_DOCKER_HOST", "host.docker.internal")

# LLM — chat (fast) vs vision (computer-use)
CHAT_API_KEY = os.getenv("CHAT_API_KEY", os.getenv("VISION_API_KEY", os.getenv("API_KEY", "")))
CHAT_API_URL = os.getenv("CHAT_API_URL", os.getenv("VISION_API_URL", "https://api.openai.com/v1/chat/completions"))
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

VISION_API_KEY = os.getenv("VISION_API_KEY", os.getenv("API_KEY", ""))
VISION_API_URL = os.getenv("VISION_API_URL", "https://api.openai.com/v1/chat/completions")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")

# Agent limits
MAX_VISION_STEPS = int(os.getenv("MAX_VISION_STEPS", "25"))
DEFAULT_PERSONA = os.getenv("DEFAULT_PERSONA", "openworker")

# Connectors
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# Ensure data dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
VAULT_PATH.mkdir(parents=True, exist_ok=True)
