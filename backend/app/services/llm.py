"""
llm.py — Shared Groq LLM client wrapper.

Centralises every model call so that:
  - Thinking/reasoning is disabled where the model supports it. This prevents
    chain-of-thought from leaking into the answer AND stops reasoning tokens
    from burning the tiny free-tier OTPM budget (which caused 429 errors).
  - Every call is capped by `settings.llm_max_tokens` (kept under OTPM limits).
  - Transient failures / 429 rate limits are retried with exponential backoff.
"""

import time
from typing import Optional

from groq import (
    APIConnectionError,
    APITimeoutError,
    Groq,
    InternalServerError,
    RateLimitError,
)

from app.config import settings


_client = Groq(api_key=settings.groq_api_key)

_RETRYABLE = (
    RateLimitError,
    InternalServerError,
    APIConnectionError,
    APITimeoutError,
)
_MAX_RETRIES = 4

# Only qwen3-family models accept reasoning_effort="none" on Groq.
# gpt-oss* only accepts low|medium|high; compound/allam reject it entirely.
_QWEN_NONE = ("qwen",)


def _supports_reasoning_none(model: str) -> bool:
    """True only for models that accept reasoning_effort='none' (qwen3 family)."""
    m = model.lower()
    return any(key in m for key in _QWEN_NONE)


def _retry_delay(attempt: int, exception: Exception) -> float:
    """Seconds to wait before the next attempt. Honours Retry-After when present."""
    headers = getattr(exception, "headers", None)
    if headers is not None:
        try:
            retry_after = headers.get("retry-after")
        except Exception:
            retry_after = None
        if retry_after:
            try:
                return min(float(retry_after), 30.0)
            except (TypeError, ValueError):
                pass
    return min(2 ** attempt, 30.0)


def complete_chat(
    *,
    system: str,
    user: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.1,
    response_format: Optional[dict] = None,
) -> str:
    """
    Run a single chat completion and return the assistant message content.

    - Sets reasoning_effort="none" on reasoning-capable models so thinking is
      disabled at the API (not stripped afterward with brittle regexes).
    - Caps output at settings.llm_max_tokens unless max_tokens is given.
    - Retries 429 / 5xx / connection errors with exponential backoff.
    """
    kwargs: dict = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens or settings.llm_max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if _supports_reasoning_none(settings.groq_model):
        kwargs["reasoning_effort"] = "none"

    last_err: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = _client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return (content or "").strip()
        except _RETRYABLE as e:
            last_err = e
            if attempt >= _MAX_RETRIES:
                break
            delay = _retry_delay(attempt, e)
            print(
                f"[LLM] Retrying Groq call ({attempt + 1}/{_MAX_RETRIES}) "
                f"after {delay:.1f}s: {e}"
            )
            time.sleep(delay)

    assert last_err is not None
    raise last_err