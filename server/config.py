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
SKILLS_DIR = Path(os.getenv("OPENDESKTOP_SKILLS_DIR", Path(__file__).resolve().parent.parent / "skills"))

# Connectors
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
SANDBOX_MODE = os.getenv("SANDBOX_MODE", "local").lower()  # local | remote
HETZNER_HOST = os.getenv("HETZNER_HOST", "")
SSH_HOST_ALIAS = os.getenv("SSH_HOST_ALIAS", "hetzner")
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "opendesktop-sandbox:latest")
AUTO_PROVISION_FLEET = os.getenv("AUTO_PROVISION_FLEET", "false").lower() == "true"
LOCAL_DOCKER_HOST = os.getenv("LOCAL_DOCKER_HOST", "host.docker.internal")

# LLM providers
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Single-key shortcuts (OpenRouter recommended — one key for chat + desktop)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
API_KEY = os.getenv("API_KEY", "").strip()
_master_key = OPENROUTER_API_KEY or API_KEY

CHAT_API_KEY = (
    os.getenv("CHAT_API_KEY", "").strip()
    or os.getenv("VISION_API_KEY", "").strip()
    or _master_key
)
VISION_API_KEY = (
    os.getenv("VISION_API_KEY", "").strip()
    or os.getenv("CHAT_API_KEY", "").strip()
    or _master_key
)

_using_openrouter = bool(OPENROUTER_API_KEY) or (
    CHAT_API_KEY.startswith("sk-or-") if CHAT_API_KEY else False
)
_default_url = OPENROUTER_API_URL if _using_openrouter else OPENAI_API_URL
_default_model = "openai/gpt-4o-mini" if _using_openrouter else "gpt-4o-mini"

CHAT_API_URL = os.getenv("CHAT_API_URL", _default_url)
CHAT_MODEL = os.getenv("CHAT_MODEL", _default_model)

VISION_API_URL = os.getenv("VISION_API_URL", _default_url)
VISION_MODEL = os.getenv("VISION_MODEL", _default_model)

# Agent limits
MAX_VISION_STEPS = int(os.getenv("MAX_VISION_STEPS", "25"))
DEFAULT_PERSONA = os.getenv("DEFAULT_PERSONA", "openworker")

# Ensure data dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
VAULT_PATH.mkdir(parents=True, exist_ok=True)


def apply_llm_api_key(key: str) -> None:
    """Set chat + vision keys in-process (UI paste or admin endpoint)."""
    key = key.strip()
    os.environ["CHAT_API_KEY"] = key
    os.environ["VISION_API_KEY"] = key
    if key.startswith("sk-or-"):
        os.environ["OPENROUTER_API_KEY"] = key
        os.environ.setdefault("CHAT_API_URL", OPENROUTER_API_URL)
        os.environ.setdefault("VISION_API_URL", OPENROUTER_API_URL)
        os.environ.setdefault("CHAT_MODEL", "openai/gpt-4o-mini")
        os.environ.setdefault("VISION_MODEL", "openai/gpt-4o-mini")


def llm_provider_label() -> str:
    key = os.getenv("CHAT_API_KEY") or os.getenv("VISION_API_KEY") or CHAT_API_KEY
    if os.getenv("OPENROUTER_API_KEY") or (key and key.startswith("sk-or-")):
        return "openrouter"
    if key and key.startswith("sk-proj-"):
        return "openai"
    return "custom" if key else "none"
