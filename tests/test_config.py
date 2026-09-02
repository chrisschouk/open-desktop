import os

import pytest


def test_openrouter_key_fills_both_roles(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.delenv("CHAT_API_KEY", raising=False)
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    import importlib
    import server.config as config

    importlib.reload(config)
    assert config.CHAT_API_KEY == "sk-or-v1-test"
    assert config.VISION_API_KEY == "sk-or-v1-test"
    assert config.CHAT_API_URL == config.OPENROUTER_API_URL
    assert config.llm_provider_label() == "openrouter"


def test_apply_llm_api_key_sets_openrouter_defaults(monkeypatch):
    import server.config as config

    config.apply_llm_api_key("sk-or-v1-from-ui")
    assert os.environ["CHAT_API_KEY"] == "sk-or-v1-from-ui"
    assert os.environ["VISION_API_KEY"] == "sk-or-v1-from-ui"
    assert os.environ["OPENROUTER_API_KEY"] == "sk-or-v1-from-ui"
