"""Anthropic prompt-caching wrapper.

Subclasses `crewai.llms.providers.anthropic.completion.AnthropicCompletion`
and overrides `_format_messages_for_anthropic` to attach
`cache_control: {"type": "ephemeral"}` markers on the system block and on
long user messages. Anthropic then serves repeated prefixes from its prompt
cache, cutting input-token cost ~90% on cache reads.

Why a subclass (not a `crewai.LLM` subclass): in crewai 1.12.2 `LLM(...)` is
a `__new__` factory that dispatches to per-provider classes
(`AnthropicCompletion`, `OpenAICompatibleCompletion`, ...). Subclassing `LLM`
therefore has no effect at runtime — the override has to live on the actual
provider class.

Anthropic cache thresholds (minimum cacheable tokens):
    - Sonnet / Opus: 1024
    - Haiku:         2048

Anthropic allows at most 4 cache_control breakpoints per request.
"""
from __future__ import annotations

from typing import Any

from crewai import LLM
from crewai.llms.providers.anthropic.completion import AnthropicCompletion


_SONNET_OPUS_MIN_TOKENS = 1024
_HAIKU_MIN_TOKENS = 2048
_MAX_BREAKPOINTS = 4
_CHARS_PER_TOKEN_ESTIMATE = 4
_EXTENDED_TTL_BETA_HEADER = "extended-cache-ttl-2025-04-11"


class AnthropicCachingCompletion(AnthropicCompletion):
    """`AnthropicCompletion` with prompt-caching markers injected automatically."""

    def __init__(self, *args: Any, cache_ttl: str = "5m", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cache_ttl = cache_ttl

    def _min_cache_tokens(self) -> int:
        return _HAIKU_MIN_TOKENS if "haiku" in self.model.lower() else _SONNET_OPUS_MIN_TOKENS

    def _is_long_enough(self, text: str) -> bool:
        return len(text) >= self._min_cache_tokens() * _CHARS_PER_TOKEN_ESTIMATE

    def _cache_control(self) -> dict[str, Any]:
        cc: dict[str, Any] = {"type": "ephemeral"}
        if self._cache_ttl == "1h":
            cc["ttl"] = "1h"
        return cc

    def _wrap_text(self, text: str) -> list[dict[str, Any]]:
        return [{"type": "text", "text": text, "cache_control": self._cache_control()}]

    def _format_messages_for_anthropic(
        self, messages: str | list[Any]
    ) -> tuple[list[Any], Any]:
        formatted_messages, system_message = super()._format_messages_for_anthropic(messages)

        budget = _MAX_BREAKPOINTS

        if isinstance(system_message, str) and self._is_long_enough(system_message):
            system_message = self._wrap_text(system_message)
            budget -= 1

        for msg in formatted_messages:
            if budget <= 0:
                break
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and self._is_long_enough(content):
                msg["content"] = self._wrap_text(content)
                budget -= 1

        return formatted_messages, system_message


def make_caching_llm(
    model: str,
    *,
    cache_ttl: str = "5m",
    **kwargs: Any,
) -> Any:
    """Factory that returns an Anthropic LLM with prompt caching, or a vanilla
    `crewai.LLM` for non-Anthropic providers (Ollama, OpenAI, etc.).

    Args:
        model: Full crewai model id, e.g. "anthropic/claude-sonnet-4-6".
        cache_ttl: "5m" (default, no surcharge) or "1h" (25% write surcharge,
            useful when the same prefix is reused across runs within an hour).
        **kwargs: Forwarded to the underlying LLM constructor.
    """
    prefix, sep, model_part = model.partition("/")
    if sep and prefix in ("anthropic", "claude"):
        if cache_ttl == "1h":
            extra_headers = kwargs.pop("extra_headers", {}) or {}
            extra_headers.setdefault("anthropic-beta", _EXTENDED_TTL_BETA_HEADER)
            kwargs["extra_headers"] = extra_headers
        return AnthropicCachingCompletion(model=model_part, cache_ttl=cache_ttl, **kwargs)
    return LLM(model=model, **kwargs)
