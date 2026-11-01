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

Claude 5.5 models (MODEL-01; decisions D-01, D-02, D-03)
--------------------------------------------------------
Haiku 5.5 and Sonnet 5.5 need a few things this module owns, because crewai 1.12.2
(and anthropic ~=0.73.0) are pinned and cannot be upgraded. Every per-model rule
lives in ONE place, the ``MODEL_SHAPES`` capability table below (one row per model);
to support another model, add a row. Nothing else in this file matches on a model name
except the cache thresholds.

1. Structured-output allow-list. crewai only uses Anthropic native structured
   outputs for model ids in ``NATIVE_STRUCTURED_OUTPUT_MODELS`` (it stops at the 4.5
   models). For any other model it overwrites ``tools`` with a forced
   ``structured_output`` tool, which silently removes every real tool from the
   tool-using agents and, on Sonnet 5.5, sends a forced tool choice the API rejects.
   ``_ensure_native_structured_outputs`` appends the fragment of every table row that
   wants the native path to that tuple at import time, so a 5.5 model keeps its real
   tools and gets ``output_format`` plus the structured-outputs beta header.
2. No sampling parameters. The 5.5 models reject non-default ``temperature``,
   ``top_p`` and ``top_k``, so ``_prepare_completion_params`` strips them from every
   request (D-02).
3. Explicit thinking. Haiku 5.5 turns adaptive thinking on by default, so each agent
   states ``thinking: off`` or ``thinking: low`` in ``agents.yaml`` (D-03). Low is
   ``{"type": "adaptive"}`` plus ``output_config.effort = "low"`` on both models. Off
   is the row's wire value: ``{"type": "disabled"}`` on Haiku 5.5, and
   ``{"type": "between_tools"}`` on Sonnet 5.5 (thinking disabled is a 400 there).
   ``budget_tokens`` is never sent.
4. No forced tool choice on Sonnet 5.5. A tool choice of type ``any`` or ``tool`` is a
   400 there, so ``_prepare_completion_params`` drops one for a model whose row says
   so (this also covers crewai's own single-tool forcing); ``auto`` and ``none`` stay.
5. Effort. anthropic 0.73's ``messages.create`` has no ``output_config`` parameter,
   so ``_EffortInterceptor`` merges ``{"effort": ...}`` into the JSON body at the HTTP
   transport (crewai's ``interceptor`` hook).
6. Refusals. A response with ``stop_reason`` refusal is an HTTP 200 with no usable
   content; the structured-output call then yields no valid model object, so the
   Flow's validation and bounded retry reject it. The category (never any content)
   is logged.

Thinking and effort are gated by model: a model with no table row (for example an
``AGENT_*_MODEL`` override to Haiku 4.5, or Sonnet 5) gets neither, so the package
stays valid while a deployment still pins another model.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
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

_SAMPLING_KEYS = ("temperature", "top_p", "top_k")
THINKING_MODES = ("off", "low")
_LOW_EFFORT = "low"
_FORCED_TOOL_CHOICE_TYPES = ("any", "tool")
_REFUSAL_CATEGORY_MAX_CHARS = 40


@dataclass(frozen=True)
class ModelShape:
    """What one model accepts on the wire (the one capability table row).

    ``fragment``: lower-case id fragment matched inside the model id.
    ``adaptive_thinking``: takes ``{"type": "adaptive"}`` plus ``output_config.effort``.
    ``thinking_off``: the thinking value that means "off" (a dict), or None to send nothing.
    ``native_structured_output``: belongs in crewai's native structured-output allow-list.
    ``forced_tool_choice``: the API accepts a tool choice of type ``any`` or ``tool``.
    """

    fragment: str
    adaptive_thinking: bool
    thinking_off: dict[str, Any] | None
    native_structured_output: bool
    forced_tool_choice: bool


# One row per model, first match wins. Adding a model is adding a row here.
MODEL_SHAPES: tuple[ModelShape, ...] = (
    # Haiku 5.5: the 1.10.x behaviour. Thinking off is the disabled value; a forced
    # tool choice is accepted (used on the first turn of thinking-off tool phases).
    # Source: live runs of 1.10.x and 1.11.x (D-01, D-02, D-03).
    ModelShape(
        fragment="claude-haiku-5-5",
        adaptive_thinking=True,
        thinking_off={"type": "disabled"},
        native_structured_output=True,
        forced_tool_choice=True,
    ),
    # Sonnet 5.5: from the claude-api skill's migration guide, "Migrating to Claude
    # Sonnet 5.5", read 2026-11-01 (documentation, confirmed live only by the smoke
    # script scripts/smoke_sonnet55.py of plan 02-26). Thinking of type disabled is a
    # 400, the lowest setting is between_tools. A forced tool choice (any or tool) is a
    # 400, so native structured output is required: crewai's fallback forces a
    # structured_output tool. Matching is by fragment, so claude-sonnet-5 (Sonnet 5)
    # and claude-sonnet-4-6 match nothing.
    ModelShape(
        fragment="claude-sonnet-5-5",
        adaptive_thinking=True,
        thinking_off={"type": "between_tools"},
        native_structured_output=True,
        forced_tool_choice=False,
    ),
)


def model_shape(model: str) -> ModelShape | None:
    """The capability row whose fragment is in ``model`` (case-insensitive), else None."""
    lowered = (model or "").lower()
    for row in MODEL_SHAPES:
        if row.fragment in lowered:
            return row
    return None


def _ensure_native_structured_outputs() -> None:
    """Append the fragment of every table row that wants the native path to crewai's
    structured-output allow-list (idempotent).

    crewai reads the module global at call time, so rebinding the attribute is
    enough. Fails loudly if a crewai change moved or retyped the constant.
    """
    current = getattr(_crewai_anthropic, "NATIVE_STRUCTURED_OUTPUT_MODELS", None)
    if not isinstance(current, tuple) or not all(isinstance(m, str) for m in current):
        raise RuntimeError(
            "crewai no longer exposes NATIVE_STRUCTURED_OUTPUT_MODELS as a tuple of str; "
            "update agents/caching_llm.py (MODEL-01 allow-list patch)"
        )
    missing = tuple(
        row.fragment
        for row in MODEL_SHAPES
        if row.native_structured_output and row.fragment not in current
    )
    if missing:
        _crewai_anthropic.NATIVE_STRUCTURED_OUTPUT_MODELS = (*current, *missing)


_ensure_native_structured_outputs()


def supports_adaptive_thinking(model: str) -> bool:
    """True when `model` accepts the adaptive-thinking / effort request shape."""
    row = model_shape(model)
    return row is not None and row.adaptive_thinking


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


def _refusal_category(response: Any) -> str:
    """The refusal category of a response, read defensively and cut short. Never the
    explanation text or any content (stop_details is a dict on the SDK object, may be
    absent)."""
    details = getattr(response, "stop_details", None)
    category = details.get("category") if isinstance(details, dict) else getattr(details, "category", None)
    if not isinstance(category, str) or not category:
        return "unknown"
    return category[:_REFUSAL_CATEGORY_MAX_CHARS]


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
        row = model_shape(model)
        if row is not None and row.adaptive_thinking:
            if thinking_mode == "low":
                kwargs.setdefault("thinking", {"type": "adaptive"})
                kwargs.setdefault("interceptor", _EffortInterceptor(_LOW_EFFORT))
            elif row.thinking_off is not None:
                kwargs.setdefault("thinking", dict(row.thinking_off))
        else:
            logger.debug("model %r does not support adaptive thinking; thinking/effort not sent", model)
        super().__init__(*args, **kwargs)
        self._cache_ttl = cache_ttl
        self._thinking_mode = thinking_mode
        self._token_usage["cache_creation_tokens"] = 0

    def _prepare_completion_params(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Strip sampling keys (the 5.5 models reject non-default values, D-02) and
        any ``budget_tokens`` thinking field (rejected by the 5.5 models)."""
        params = super()._prepare_completion_params(*args, **kwargs)
        for key in _SAMPLING_KEYS:
            params.pop(key, None)
        thinking = params.get("thinking")
        if isinstance(thinking, dict) and "budget_tokens" in thinking:
            params["thinking"] = {k: v for k, v in thinking.items() if k != "budget_tokens"}
        self._drop_rejected_tool_choice(params)
        self._force_first_tool_call(params)
        return params

    def _drop_rejected_tool_choice(self, params: dict[str, Any]) -> None:
        """Drop a forced tool choice (type ``any`` or ``tool``) for a model whose table
        row says the API rejects it (Sonnet 5.5). This covers crewai's own single-tool
        forcing as well as ours; ``auto`` and ``none`` are kept, and a model with no
        row is left alone."""
        row = model_shape(self.model)
        if row is None or row.forced_tool_choice:
            return
        choice = params.get("tool_choice")
        if isinstance(choice, dict) and choice.get("type") in _FORCED_TOOL_CHOICE_TYPES:
            del params["tool_choice"]

    def _force_first_tool_call(self, params: dict[str, Any]) -> None:
        """Require a tool call on the first turn of a thinking-off request, for a model
        whose table row accepts a forced tool choice (Haiku 5.5, never Sonnet 5.5).

        Haiku 5.5 given tools plus a native structured-output schema can answer
        straight from the schema without calling any tool (first live canary,
        market_analysis: one LLM call, zero tool calls), which yields model-invented
        numbers. ``tool_choice: any`` is only sent until a tool result is in the
        conversation, so the model can still finish with its answer afterwards. The
        API rejects a forced tool choice with thinking enabled, so adaptive-thinking
        phases are left alone; a ``tool_choice`` crewai already set is kept.
        """
        row = model_shape(self.model)
        if row is None or not row.adaptive_thinking or not row.forced_tool_choice:
            return
        if self._thinking_mode != "off":
            return
        if not params.get("tools") or params.get("tool_choice"):
            return
        if _conversation_has_tool_turn(params.get("messages")):
            return
        params["tool_choice"] = {"type": "any"}

    @staticmethod
    def _extract_anthropic_token_usage(response: Any) -> dict[str, Any]:
        usage_dict = AnthropicCompletion._extract_anthropic_token_usage(response)
        if getattr(response, "stop_reason", None) == "refusal":
            logger.warning(
                "Anthropic response refused (stop_reason=refusal, category=%s); "
                "no answer is published from it",
                _refusal_category(response),
            )
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
