"""Unit tests for the CachingLLM Anthropic prompt-caching wrapper."""
import pytest

from agents.caching_llm import CachingLLM


@pytest.fixture
def sonnet_llm():
    return CachingLLM(model="anthropic/claude-sonnet-4-6", api_key="test-key")


@pytest.fixture
def haiku_llm():
    return CachingLLM(model="anthropic/claude-haiku-4-5-20251001", api_key="test-key")


def _long_text(chars: int) -> str:
    return "x" * chars


def test_long_user_message_gets_cache_control(sonnet_llm):
    # Sonnet threshold is 1024 tokens ≈ 4096 chars
    messages = [
        {"role": "user", "content": _long_text(5000)},
    ]
    out = sonnet_llm._format_messages_for_provider(messages)
    block = out[0]["content"][0]
    assert block["type"] == "text"
    assert block["cache_control"] == {"type": "ephemeral"}


def test_short_message_left_alone(sonnet_llm):
    messages = [{"role": "user", "content": "hi"}]
    out = sonnet_llm._format_messages_for_provider(messages)
    assert out[0]["content"] == "hi"


def test_haiku_higher_threshold(haiku_llm):
    # 5000 chars ≈ 1250 tokens — above Sonnet min but below Haiku min (2048)
    messages = [{"role": "user", "content": _long_text(5000)}]
    out = haiku_llm._format_messages_for_provider(messages)
    assert out[0]["content"] == _long_text(5000)


def test_haiku_caches_when_above_2048(haiku_llm):
    # 10000 chars ≈ 2500 tokens — above Haiku threshold
    messages = [{"role": "user", "content": _long_text(10000)}]
    out = haiku_llm._format_messages_for_provider(messages)
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_breakpoint_budget_capped_at_four(sonnet_llm):
    messages = [{"role": "user", "content": _long_text(5000)} for _ in range(6)]
    out = sonnet_llm._format_messages_for_provider(messages)
    cached = sum(1 for m in out if isinstance(m["content"], list))
    assert cached == 4


def test_assistant_role_not_cached(sonnet_llm):
    messages = [
        {"role": "user", "content": "start"},
        {"role": "assistant", "content": _long_text(5000)},
    ]
    out = sonnet_llm._format_messages_for_provider(messages)
    assert out[1]["content"] == _long_text(5000)


def test_non_anthropic_passthrough():
    llm = CachingLLM(model="ollama/qwen3.5:9b")
    messages = [{"role": "user", "content": _long_text(5000)}]
    out = llm._format_messages_for_provider(messages)
    assert out[0]["content"] == _long_text(5000)


def test_extended_ttl_adds_beta_header_and_ttl_field():
    llm = CachingLLM(
        model="anthropic/claude-sonnet-4-6",
        api_key="test-key",
        cache_ttl="1h",
    )
    messages = [{"role": "user", "content": _long_text(5000)}]
    out = llm._format_messages_for_provider(messages)
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
