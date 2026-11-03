"""Unit tests for the Anthropic prompt-caching wrapper."""
import json

import pytest
from pydantic import BaseModel

from agents import caching_llm
from agents.caching_llm import AnthropicCachingCompletion, make_caching_llm, model_shape
from tests.test_llm_request_shape import has_cache_control, install_capture


def _long_text(chars: int) -> str:
    return "x" * chars


@pytest.fixture
def sonnet():
    return AnthropicCachingCompletion(
        model="claude-sonnet-4-6", api_key="test-key", prompt_caching="on"
    )


@pytest.fixture
def haiku():
    return AnthropicCachingCompletion(
        model="claude-haiku-4-5-20251001", api_key="test-key", prompt_caching="on"
    )


def test_long_user_message_gets_cache_control(sonnet):
    messages = [{"role": "user", "content": _long_text(5000)}]
    formatted, _system = sonnet._format_messages_for_anthropic(messages)
    block = formatted[0]["content"][0]
    assert block["type"] == "text"
    assert block["cache_control"] == {"type": "ephemeral"}


def test_short_message_left_alone(sonnet):
    messages = [{"role": "user", "content": "hi"}]
    formatted, _system = sonnet._format_messages_for_anthropic(messages)
    assert formatted[0]["content"] == "hi"


def test_long_system_message_wrapped(sonnet):
    messages = [
        {"role": "system", "content": _long_text(5000)},
        {"role": "user", "content": "hi"},
    ]
    _formatted, system = sonnet._format_messages_for_anthropic(messages)
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_haiku_higher_threshold_skips_sub_2048(haiku):
    # 5000 chars ≈ 1250 tokens — above Sonnet min, below Haiku min (2048)
    messages = [{"role": "user", "content": _long_text(5000)}]
    formatted, _ = haiku._format_messages_for_anthropic(messages)
    assert formatted[0]["content"] == _long_text(5000)


def test_haiku_caches_when_above_2048(haiku):
    messages = [{"role": "user", "content": _long_text(10000)}]
    formatted, _ = haiku._format_messages_for_anthropic(messages)
    assert formatted[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_breakpoint_budget_capped_at_four(sonnet):
    # 1 system + 6 long user messages — only 4 should be wrapped total
    messages = [{"role": "system", "content": _long_text(5000)}]
    messages += [{"role": "user", "content": _long_text(5000)} for _ in range(6)]
    formatted, system = sonnet._format_messages_for_anthropic(messages)
    wrapped_users = sum(1 for m in formatted if isinstance(m.get("content"), list))
    system_wrapped = 1 if isinstance(system, list) else 0
    assert wrapped_users + system_wrapped == 4


def test_extended_ttl_adds_ttl_field():
    llm = AnthropicCachingCompletion(
        model="claude-sonnet-4-6", api_key="test-key", cache_ttl="1h", prompt_caching="on"
    )
    messages = [{"role": "user", "content": _long_text(5000)}]
    formatted, _ = llm._format_messages_for_anthropic(messages)
    assert formatted[0]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_factory_returns_caching_class_for_anthropic():
    llm = make_caching_llm(model="anthropic/claude-sonnet-4-6", api_key="test-key")
    assert isinstance(llm, AnthropicCachingCompletion)


def test_factory_returns_vanilla_llm_for_ollama():
    llm = make_caching_llm(model="ollama/qwen3.5:9b", base_url="http://localhost:11434")
    assert not isinstance(llm, AnthropicCachingCompletion)


# ─── Thinking-block responses (MODEL-01, D-03) ────────────────────────────────

class _Answer(BaseModel):
    ticker: str
    note: str


_ANSWER_JSON = json.dumps({"ticker": "AAA", "note": "ok"})
_THINKING_FIRST = [
    {"type": "thinking", "thinking": "", "signature": "s"},
    {"type": "text", "text": _ANSWER_JSON},
]


@pytest.fixture
def thinking_low():
    return make_caching_llm(
        model="anthropic/claude-haiku-5-5", api_key="test-key", thinking="low"
    )


@pytest.mark.asyncio
async def test_thinking_first_response_parses(thinking_low):
    transport = install_capture(thinking_low, _THINKING_FIRST)
    result = await thinking_low.acall(
        [{"role": "user", "content": "hi"}], response_model=_Answer
    )
    assert isinstance(result, _Answer)
    assert result.ticker == "AAA"
    assert transport.requests[0]["body"]["thinking"] == {"type": "adaptive"}


@pytest.mark.asyncio
async def test_thinking_first_plain_text(thinking_low):
    install_capture(thinking_low, _THINKING_FIRST)
    result = await thinking_low.acall([{"role": "user", "content": "hi"}])
    assert result == _ANSWER_JSON


@pytest.mark.asyncio
async def test_cache_markers_with_thinking():
    llm = make_caching_llm(
        model="anthropic/claude-haiku-5-5", api_key="test-key", thinking="low",
        prompt_caching="on",
    )
    transport = install_capture(llm, _THINKING_FIRST)
    await llm.acall(
        [{"role": "user", "content": _long_text(10000)}], response_model=_Answer
    )
    body = transport.requests[0]["body"]
    assert body["thinking"] == {"type": "adaptive"}
    block = body["messages"][0]["content"][0]
    assert block["cache_control"] == {"type": "ephemeral"}


# ─── Capability table (plan 02-25) ─────────────────────────────────────────────

def test_model_shape_rows():
    haiku_row = model_shape("claude-haiku-5-5")
    assert haiku_row is not None and haiku_row.thinking_off == {"type": "disabled"}
    assert haiku_row.forced_tool_choice and haiku_row.native_structured_output
    sonnet_row = model_shape("claude-sonnet-5-5")
    assert sonnet_row is not None and sonnet_row.thinking_off == {"type": "between_tools"}
    assert not sonnet_row.forced_tool_choice and sonnet_row.native_structured_output
    assert model_shape("anthropic/claude-sonnet-5-5-20261101") is sonnet_row
    assert model_shape("CLAUDE-SONNET-5-5") is sonnet_row


def test_model_shape_is_none_for_other_models():
    for other in ("claude-sonnet-5", "claude-sonnet-4-6", "claude-haiku-4-5-20251001", ""):
        assert model_shape(other) is None, other
        assert not caching_llm.supports_adaptive_thinking(other), other


def test_ensure_native_structured_outputs_is_idempotent_and_keeps_crewai_entries():
    from crewai.llms.providers.anthropic import completion

    before = completion.NATIVE_STRUCTURED_OUTPUT_MODELS
    caching_llm._ensure_native_structured_outputs()
    caching_llm._ensure_native_structured_outputs()
    after = completion.NATIVE_STRUCTURED_OUTPUT_MODELS
    assert after == before
    assert len(after) == len(set(after))
    for entry in ("claude-haiku-4-5", "claude-opus-4-5", "claude-sonnet-4-5"):
        assert entry in after
    for row in caching_llm.MODEL_SHAPES:
        assert after.count(row.fragment) == 1


# ─── Prompt caching switch (quick 261103-urg) ──────────────────────────────────

@pytest.mark.parametrize("model", ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"])
def test_prompt_caching_default_class_adds_no_markers(model):
    llm = AnthropicCachingCompletion(model=model, api_key="test-key")
    formatted, system = llm._format_messages_for_anthropic(
        [
            {"role": "system", "content": _long_text(10000)},
            {"role": "user", "content": _long_text(10000)},
        ]
    )
    assert isinstance(system, str)
    assert isinstance(formatted[0]["content"], str)


@pytest.mark.asyncio
async def test_prompt_caching_default_factory_sends_no_marker_and_no_ttl_header():
    llm = make_caching_llm(
        "anthropic/claude-haiku-5-5", api_key="test-key", cache_ttl="1h"
    )
    assert "extended-cache-ttl" not in repr(llm.additional_params)
    transport = install_capture(llm)
    await llm.acall(
        [{"role": "user", "content": _long_text(10000)}], response_model=_Answer
    )
    shot = transport.requests[0]
    assert not has_cache_control(shot["body"])
    assert "extended-cache-ttl" not in shot["beta"]


@pytest.mark.asyncio
async def test_prompt_caching_on_with_1h_restores_ttl_header_and_marker():
    llm = make_caching_llm(
        "anthropic/claude-haiku-5-5", api_key="test-key", cache_ttl="1h",
        prompt_caching="on",
    )
    assert (
        llm.additional_params["extra_headers"]["anthropic-beta"]
        == "extended-cache-ttl-2025-04-11"
    )
    transport = install_capture(llm)
    await llm.acall(
        [{"role": "user", "content": _long_text(10000)}], response_model=_Answer
    )
    block = transport.requests[0]["body"]["messages"][0]["content"][0]
    assert block["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_prompt_caching_invalid_value_raises():
    with pytest.raises(ValueError, match="prompt_caching"):
        AnthropicCachingCompletion(
            model="claude-sonnet-4-6", api_key="test-key", prompt_caching="maybe"
        )
    with pytest.raises(ValueError, match="prompt_caching"):
        make_caching_llm(
            "anthropic/claude-haiku-5-5", api_key="test-key", prompt_caching=True
        )


def test_prompt_caching_ignored_for_ollama():
    llm = make_caching_llm(
        "ollama/qwen3.5:9b", base_url="http://localhost:11434", prompt_caching="on"
    )
    assert not isinstance(llm, AnthropicCachingCompletion)
    assert "prompt_caching" not in repr(getattr(llm, "additional_params", {}))
