"""
Gemini Flash access for Version 3.

All AI in V3 (AI players, library narration, typed-command understanding)
goes through Gemini Flash with "thinking" switched off for speed. The game
rules themselves stay in Python: Gemini proposes, Python validates.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # for gemini_model.py
from gemini_model import resolve_model  # noqa: E402

_client = None
_client_loaded = False
_THINKING_MODE: dict[str, int] = {}
_cooldown_until = 0.0          # after a 429, skip Gemini until then (callers use their offline rules)
_cooldown_daily = False        # True when the daily free quota (not the per-minute one) is used up


class RateLimited(RuntimeError):
    """Raised instead of calling Gemini while the free-tier rate limit cools down."""


def _is_daily(exc) -> bool:
    return "PerDay" in str(exc)


def _retry_delay(exc) -> float:
    """How long to wait: per-minute limits are short (capped at 2 min); a used-up daily
    quota is honoured in full (up to a day), so we don't keep asking for nothing."""
    m = re.search(r"retryDelay\W+(\d+)", str(exc))
    if not m:
        return 30.0
    wait = float(m.group(1))
    return min(86400.0, wait) if _is_daily(exc) else min(120.0, max(5.0, wait))


def _rate_guard(call):
    """Wrap generate_content: after a 429, fail fast (no request) until the wait is over.
    Every caller already falls back to rules on an exception, so the game keeps running."""
    def guarded(*args, **kwargs):
        global _cooldown_until, _cooldown_daily
        wait = _cooldown_until - time.time()
        if wait > 0:
            raise RateLimited(f"Gemini rate limit: cooling down for {wait:.0f}s more")
        for pause in (1.5, 3.0, None):
            try:
                return call(*args, **kwargs)
            except Exception as exc:
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    _cooldown_until = time.time() + _retry_delay(exc)
                    _cooldown_daily = _is_daily(exc)
                    raise
                # "503 UNAVAILABLE / high demand" is Google's servers being busy for a moment:
                # wait briefly and try again (twice), then let the caller use its rules.
                if pause is None or not ("503" in str(exc) or "UNAVAILABLE" in str(exc)):
                    raise
                time.sleep(pause)
    return guarded


def cooling_down() -> float:
    """Seconds left before Gemini is tried again (0 if it isn't rate-limited)."""
    return max(0.0, _cooldown_until - time.time())


def daily_quota_used_up() -> bool:
    """True while the wait is for the daily free quota (resets once a day)."""
    return _cooldown_daily and cooling_down() > 0


def get_client():
    """One Gemini client per process, or None without an API key (offline mode).
    The client is shared by V3's AI players and the V2 parser/narrator, so the
    rate-limit guard covers every call."""
    global _client, _client_loaded
    if not _client_loaded:
        _client_loaded = True
        key = os.getenv("GEMINI_API_KEY")
        if key and not key.startswith("your-"):
            from google import genai
            from google.genai import types
            # 20 s limit per request: an overloaded server can otherwise hang for minutes
            # (then the caller's rules take over, as for any other failure).
            _client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=20_000))
            _client.models.generate_content = _rate_guard(_client.models.generate_content)
    return _client


def flash_model(client) -> str:
    """Gemini Flash (GEMINI_MODEL if set and available, else the newest Flash)."""
    return resolve_model(client)


def generate(client, prompt: str, system: str | None = None, temperature: float = 0.5,
             max_tokens: int = 200, as_json: bool = False) -> str:
    """Call Gemini Flash with thinking switched off (with fallbacks for models
    that don't support turning it off)."""
    from google.genai import types
    model = flash_model(client)
    options = [
        {"thinking_config": types.ThinkingConfig(thinking_budget=0)},
        {"thinking_config": types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL)},
        {},
    ]
    extra = {"response_mime_type": "application/json"} if as_json else {}
    start = _THINKING_MODE.get(model, 0)
    last = None
    for i in range(start, len(options)):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system, temperature=temperature,
                                                   max_output_tokens=max_tokens, **extra, **options[i]))
            _THINKING_MODE[model] = i
            return (resp.text or "").strip()
        except Exception as exc:
            last = exc
            # Newer models (e.g. gemini-3.5-flash-lite) reject thinking_budget=0 with a bare
            # 400 INVALID_ARGUMENT that doesn't mention "thinking", so try the next setting
            # for that too. Other errors (quota, network, bad key) stop here.
            msg = str(exc).lower()
            if isinstance(exc, RateLimited) or ("thinking" not in msg and "invalid_argument" not in msg):
                break
    raise last


def generate_json(client, prompt: str, system: str | None = None, max_tokens: int = 250) -> dict:
    raw = generate(client, prompt, system, temperature=0, max_tokens=max_tokens, as_json=True)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
    return json.loads(raw)
