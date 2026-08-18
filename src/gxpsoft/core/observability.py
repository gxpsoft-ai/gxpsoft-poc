"""Centralized Langfuse observability and OpenTelemetry tracing integration."""

import os
from typing import Any, Callable, Dict, Optional
from dotenv import load_dotenv

# Load environment variables if present
load_dotenv()

DEFAULT_LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000"))

try:
    from langfuse import Langfuse, observe, get_client
    _HAS_LANGFUSE = True
except ImportError:
    _HAS_LANGFUSE = False
    observe = lambda *args, **kwargs: (lambda f: f)  # No-op fallback
    get_client = lambda: None
    Langfuse = None


_langfuse_instance: Optional[Any] = None


def get_langfuse_client() -> Optional[Any]:
    """Returns the singleton Langfuse client initialized with local host http://localhost:3000."""
    global _langfuse_instance
    if _langfuse_instance is not None:
        return _langfuse_instance

    if not _HAS_LANGFUSE:
        return None

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", DEFAULT_LANGFUSE_HOST)

    if public_key and secret_key:
        try:
            _langfuse_instance = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host
            )
        except Exception:
            _langfuse_instance = None
    return _langfuse_instance


def flush_langfuse() -> None:
    """Flushes buffered Langfuse traces to http://localhost:3000."""
    try:
        client = get_langfuse_client()
        if client and hasattr(client, "flush"):
            client.flush()
    except Exception:
        pass


__all__ = [
    "DEFAULT_LANGFUSE_HOST",
    "flush_langfuse",
    "get_langfuse_client",
    "observe",
]
