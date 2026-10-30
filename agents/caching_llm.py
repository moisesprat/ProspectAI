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

Claude Haiku 5.5 (MODEL-01; decisions D-01, D-02, D-03)
-------------------------------------------------------
Moving every agent to ``claude-haiku-5-5`` needs four things this module owns,
because crewai 1.12.2 (and anthropic ~=0.73.0) are pinned and cannot be upgraded:

1. Structured-output allow-list. crewai only uses Anthropic native structured
   outputs for model ids in ``NATIVE_STRUCTURED_OUTPUT_MODELS`` (it stops at
   Haiku 4.5). For any other model it overwrites ``tools`` with a forced
   ``structured_output`` tool, which silently removes every real tool from the
   tool-using agents. ``_ensure_native_structured_outputs`` appends the Haiku 5.5
   id to that tuple at import time, so Haiku 5.5 keeps its real tools and gets
   ``output_format`` plus the structured-outputs beta header.
2. No sampling parameters. Haiku 5.5 rejects non-default ``temperature``,
   ``top_p`` and ``top_k``, so ``_prepare_completion_params`` strips them from
   every request (D-02).
3. Explicit thinking. Haiku 5.5 turns adaptive thinking on by default, so each
   agent states ``thinking: off`` (``{"type": "disabled"}``) or ``thinking: low``
   (``{"type": "adaptive"}`` plus ``output_config.effort = "low"``) in
   ``agents.yaml`` (D-03). ``budget_tokens`` is never sent (Haiku 5.5 rejects it).
4. Effort. anthropic 0.73's ``messages.create`` has no ``output_config``
   parameter, so ``_EffortInterceptor`` merges ``{"effort": ...}`` into the JSON
   body at the HTTP transport (crewai's ``interceptor`` hook).

Thinking and effort are gated by model: a model that does not support adaptive
thinking (for example an ``AGENT_*_MODEL`` override to Haiku 4.5) gets neither,
so the package stays valid while a deployment still pins an older model.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from crewai import LLM
from crewai.llms.hooks.base import BaseInterceptor
from crewai.llms.providers.anthropic import completion as _crewai_anthropic
from crewai.llms.providers.anthropic.completion import AnthropicCompletion

logger = logging.getLogger(__name__)


_SONNET_OPUS_MIN_TOKENS = 1024
_HAIKU_MIN_TOKENS = 2048
_MAX_BREAKPOINTS = 4
_CHARS_PER_TOKEN_ESTIMATE = 4
_EXTENDED_TTL_BETA_HEADER = "extended-cache-ttl-2025-04-11"

_HAIKU_55 = "claude-haiku-5-5"
_ADAPTIVE_THINKING_MODELS = (_HAIKU_55,)
_SAMPLING_KEYS = ("temperature", "top_p", "top_k")
THINKING_MODES = ("off", "low")
_LOW_EFFORT = "low"


def _ensure_native_structured_outputs() -> None:
    """Append the Haiku 5.5 id to crewai's native structured-output allow-list.

    crewai reads the module global at call time, so rebinding the attribute is
    enough. Fails loudly if a crewai change moved or retyped the constant.
    """
    current = getattr(_crewai_anthropic, "NATIVE_STRUCTURED_OUTPUT_MODELS", None)
    if not isinstance(current, tuple) or not all(isinstance(m, str) for m in current):
        raise RuntimeError(
            "crewai no longer exposes NATIVE_STRUCTURED_OUTPUT_MODELS as a tuple of str; "
            "update agents/caching_llm.py (MODEL-01 allow-list patch)"
        )
    if _HAIKU_55 not in current:
        _crewai_anthropic.NATIVE_STRUCTURED_OUTPUT_MODELS = (*current, _HAIKU_55)


_ensure_native_structured_outputs()


def supports_adaptive_thinking(model: str) -> bool:
    """True when `model` accepts the adaptive-thinking / effort request shape."""
    lowered = model.lower()
    return any(m in lowered for m in _ADAPTIVE_THINKING_MODELS)


def _conversation_has_tool_turn(messages: Any) -> bool:
    """True once any message carries a tool call or tool result, in crewai's
    OpenAI-style shape or Anthropic content blocks."""
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "tool" or message.get("tool_calls"):
            return True
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result"):
                    return True
    return False


class _EffortInterceptor(BaseInterceptor[httpx.Request, httpx.Response]):
    """Merge ``output_config.effort`` into outbound Messages request bodies.

    anthropic 0.73 cannot express ``output_config`` through ``messages.create``
    (and crewai passes ``extra_body`` itself on the structured-output path), so
    the field is added to the JSON body at the transport layer.
    """

    def __init__(self, effort: str) -> None:
        self._effort = effort

    def _rewrite(self, request: httpx.Request) -> httpx.Request:
        if request.method != "POST" or not request.url.path.endswith("/v1/messages"):
            return request
        try:
            body = json.loads(request.content)
        except (httpx.RequestNotRead, ValueError):
            return request
        if not isinstance(body, dict):
            return request
        output_config = body.get("output_config")
        output_config = dict(output_config) if isinstance(output_config, dict) else {}
        output_config["effort"] = self._effort
        body["output_config"] = output_config
        content = json.dumps(body).encode()
        headers = httpx.Headers(request.headers)
        headers["content-length"] = str(len(content))
        return httpx.Request(
            request.method,
            request.url,
            headers=headers,
            content=content,
            extensions=request.extensions,
        )

    def on_outbound(self, message: httpx.Request) -> httpx.Request:
        return self._rewrite(message)

    def on_inbound(self, message: httpx.Response) -> httpx.Response:
        return message

    async def aon_outbound(self, message: httpx.Request) -> httpx.Request:
        return self._rewrite(message)

    async def aon_inbound(self, message: httpx.Response) -> httpx.Response:
        return message


class AnthropicCachingCompletion(AnthropicCompletion):
    """`AnthropicCompletion` with prompt-caching markers injected automatically.

    Also tracks `cache_creation_input_tokens` per LLM instance — CrewAI's
    upstream `_extract_anthropic_token_usage` discards this field, so it would
    otherwise be invisible. Exposed via `self._token_usage["cache_creation_tokens"]`
    for `ExecutionTracker` to snapshot/delta around each phase.
    """

    def __init__(
        self,
        *args: Any,
        cache_ttl: str = "5m",
        thinking_mode: str = "off",
        **kwargs: Any,
    ) -> None:
        if thinking_mode not in THINKING_MODES:
            raise ValueError(
                f"thinking_mode must be one of {', '.join(THINKING_MODES)}; got {thinking_mode!r}"
            )
        model = kwargs.get("model") or (args[0] if args else "")
        if supports_adaptive_thinking(model):
            if thinking_mode == "low":
                kwargs.setdefault("thinking", {"type": "adaptive"})
                kwargs.setdefault("interceptor", _EffortInterceptor(_LOW_EFFORT))
            else:
                kwargs.setdefault("thinking", {"type": "disabled"})
        else:
            logger.debug("model %r does not support adaptive thinking; thinking/effort not sent", model)
        super().__init__(*args, **kwargs)
        self._cache_ttl = cache_ttl
        self._thinking_mode = thinking_mode
        self._token_usage["cache_creation_tokens"] = 0

    def _prepare_completion_params(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Strip sampling keys (Haiku 5.5 rejects non-default values, D-02) and
        any ``budget_tokens`` thinking field (rejected by Haiku 5.5)."""
        params = super()._prepare_completion_params(*args, **kwargs)
        for key in _SAMPLING_KEYS:
            params.pop(key, None)
        thinking = params.get("thinking")
        if isinstance(thinking, dict) and "budget_tokens" in thinking:
            params["thinking"] = {k: v for k, v in thinking.items() if k != "budget_tokens"}
        self._force_first_tool_call(params)
        return params

    def _force_first_tool_call(self, params: dict[str, Any]) -> None:
        """Require a tool call on the first turn of a thinking-off Haiku 5.5 request.

        Haiku 5.5 given tools plus a native structured-output schema can answer
        straight from the schema without calling any tool (first live canary,
        market_analysis: one LLM call, zero tool calls), which yields model-invented
        numbers. ``tool_choice: any`` is only sent until a tool result is in the
        conversation, so the model can still finish with its answer afterwards. The
        API rejects a forced tool choice with thinking enabled, so adaptive-thinking
        phases are left alone; a ``tool_choice`` crewai already set is kept.
        """
        if not supports_adaptive_thinking(self.model) or self._thinking_mode != "off":
            return
        if not params.get("tools") or params.get("tool_choice"):
            return
        if _conversation_has_tool_turn(params.get("messages")):
            return
        params["tool_choice"] = {"type": "any"}

    @staticmethod
    def _extract_anthropic_token_usage(response: Any) -> dict[str, Any]:
        usage_dict = AnthropicCompletion._extract_anthropic_token_usage(response)
        if hasattr(response, "usage") and response.usage:
            usage_dict["cache_creation_input_tokens"] = (
                getattr(response.usage, "cache_creation_input_tokens", 0) or 0
            )
        return usage_dict

    def _track_token_usage_internal(self, usage_data: dict[str, Any]) -> None:
        super()._track_token_usage_internal(usage_data)
        self._token_usage["cache_creation_tokens"] += (
            usage_data.get("cache_creation_input_tokens", 0) or 0
        )

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
    thinking: str = "off",
    **kwargs: Any,
) -> Any:
    """Factory that returns an Anthropic LLM with prompt caching, or a vanilla
    `crewai.LLM` for non-Anthropic providers (Ollama, OpenAI, etc.).

    Args:
        model: Full crewai model id, e.g. "anthropic/claude-sonnet-4-6".
        cache_ttl: "5m" (default, no surcharge) or "1h" (25% write surcharge,
            useful when the same prefix is reused across runs within an hour).
        thinking: "off" (default) or "low" -- the per-agent thinking mode from
            agents.yaml (D-03). Applied only to models that support adaptive
            thinking; ignored for other Anthropic models and other providers.
        **kwargs: Forwarded to the underlying LLM constructor. Sampling
            parameters (temperature, top_p, top_k) are dropped (D-02).
    """
    for key in _SAMPLING_KEYS:
        kwargs.pop(key, None)
    prefix, sep, model_part = model.partition("/")
    if sep and prefix in ("anthropic", "claude"):
        if cache_ttl == "1h":
            extra_headers = kwargs.pop("extra_headers", {}) or {}
            extra_headers.setdefault("anthropic-beta", _EXTENDED_TTL_BETA_HEADER)
            kwargs["extra_headers"] = extra_headers
        return AnthropicCachingCompletion(
            model=model_part, cache_ttl=cache_ttl, thinking_mode=thinking, **kwargs
        )
    return LLM(model=model, **kwargs)
