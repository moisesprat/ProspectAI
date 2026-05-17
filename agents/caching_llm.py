"""Anthropic prompt-caching wrapper around `crewai.LLM`.

Injects `cache_control: {"type": "ephemeral"}` markers on long system/user
messages so Anthropic can serve them from its prompt cache on subsequent calls
within the same TTL window. Non-Anthropic models are passed through unchanged.

Anthropic cache minimums (tokens):
    - Sonnet / Opus: 1024
    - Haiku:         2048

Anthropic allows at most 4 cache_control breakpoints per request, so we cap
markers at 4 across system + user messages.
"""
from __future__ import annotations

from typing import Any

from crewai import LLM


_SONNET_OPUS_MIN_TOKENS = 1024
_HAIKU_MIN_TOKENS = 2048
_MAX_BREAKPOINTS = 4
_CHARS_PER_TOKEN_ESTIMATE = 4
_EXTENDED_TTL_BETA_HEADER = "extended-cache-ttl-2025-04-11"


class CachingLLM(LLM):
    """`crewai.LLM` subclass that annotates long messages with Anthropic cache_control.

    Args:
        *args, **kwargs: Forwarded to `crewai.LLM`.
        cache_ttl: "5m" (default, no surcharge) or "1h" (25% write surcharge,
            useful when the same prefix is reused across runs within an hour).
    """

    def __init__(self, *args: Any, cache_ttl: str = "5m", **kwargs: Any) -> None:
        if cache_ttl == "1h":
            extra_headers = kwargs.pop("extra_headers", {}) or {}
            extra_headers.setdefault("anthropic-beta", _EXTENDED_TTL_BETA_HEADER)
            kwargs["extra_headers"] = extra_headers
        super().__init__(*args, **kwargs)
        self._cache_ttl = cache_ttl

    def _min_cache_tokens(self) -> int:
        return _HAIKU_MIN_TOKENS if "haiku" in self.model.lower() else _SONNET_OPUS_MIN_TOKENS

    def _is_long_enough(self, text: str) -> bool:
        return len(text) >= self._min_cache_tokens() * _CHARS_PER_TOKEN_ESTIMATE

    def _wrap_with_cache(self, text: str) -> list[dict[str, Any]]:
        block: dict[str, Any] = {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}
        if self._cache_ttl == "1h":
            block["cache_control"]["ttl"] = "1h"
        return [block]

    def _inject_cache_control(self, messages: list[Any]) -> list[Any]:
        if not self.is_anthropic:
            return messages

        budget = _MAX_BREAKPOINTS
        result: list[Any] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if (
                budget > 0
                and role in ("system", "user")
                and isinstance(content, str)
                and self._is_long_enough(content)
            ):
                result.append({**msg, "content": self._wrap_with_cache(content)})
                budget -= 1
            else:
                result.append(msg)
        return result

    def _format_messages_for_provider(
        self, messages: list[Any]
    ) -> list[Any]:
        formatted = super()._format_messages_for_provider(messages)
        return self._inject_cache_control(formatted)
