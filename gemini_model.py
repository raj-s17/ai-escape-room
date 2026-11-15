"""
Chooses a Gemini model that actually exists for the user's API key.

Google renames and retires Gemini models regularly, so a hard-coded model
name can suddenly fail with "404 NOT_FOUND". This helper asks the API which
models support generateContent, uses GEMINI_MODEL from .env if it is
available, and otherwise falls back to the newest general-purpose Flash model.
"""

from __future__ import annotations

import os

DEFAULT_MODEL = "gemini-2.5-flash"
_SKIP = ("image", "tts", "live", "audio", "embedding", "transcribe", "robotics", "omni", "lite", "exp")
_cache: dict[str, str] = {}


def available_models(client) -> list[str]:
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.removeprefix("models/"))
    return names


def resolve_model(client, preferred: str | None = None) -> str:
    preferred = preferred or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    if preferred in _cache:
        return _cache[preferred]
    try:
        names = available_models(client)
    except Exception:
        return preferred  # could not list models; just try the preferred one
    if not names or preferred in names:
        choice = preferred
    else:
        flash = [n for n in names if "flash" in n and not any(s in n for s in _SKIP)]
        stable = [n for n in flash if "preview" not in n] or flash
        choice = max(stable, key=_version_key) if stable else names[0]
    _cache[preferred] = choice
    return choice


def _version_key(name: str):
    """'gemini-3.5-flash' -> (3, 5) so newer versions sort higher."""
    import re
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
