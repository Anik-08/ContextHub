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


_QWEN_NONE = ("qwen",)


def _supports_reasoning_none(model: str) -> bool:
    m = model.lower()
    return any(key in m for key in _QWEN_NONE)


def _retry_delay(attempt: int, exception: Exception) -> float:
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
