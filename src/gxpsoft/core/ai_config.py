"""Centralized Pydantic AI model configuration and provider resolution."""

import os
import urllib.request
from typing import Any, Optional, Union
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "muse-glimmer")
DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _get_root_ollama_url(url: str) -> str:
    """Strips trailing slashes and /v1 suffix to reach root Ollama server."""
    base = url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def is_ollama_online(base_url: str = DEFAULT_OLLAMA_BASE_URL, timeout: float = 1.0) -> bool:
    """Checks if a local Ollama server is responding and live LLM execution is active."""
    # If running in pytest without explicit live LLM flag, avoid multi-minute inference per test
    if os.getenv("PYTEST_CURRENT_TEST") and os.getenv("GXP_USE_LIVE_LLM") != "1":
        return False

    try:
        root_url = _get_root_ollama_url(base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL))
        req = urllib.request.Request(f"{root_url}/api/version", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_agent_model(
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Model:
    """Returns the configured Pydantic AI model for Ollama (muse-glimmer)."""
    selected_model = model_name or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    raw_base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    
    # Ensure URL ends with /v1 for OpenAI compatibility
    root_base = _get_root_ollama_url(raw_base_url)
    v1_url = f"{root_base}/v1"

    # Use OpenAIChatModel with OpenAIProvider pointing to Ollama's /v1 endpoint
    provider = OpenAIProvider(
        base_url=v1_url,
        api_key=os.getenv("OLLAMA_API_KEY", "ollama")
    )
    return OpenAIChatModel(selected_model, provider=provider)
