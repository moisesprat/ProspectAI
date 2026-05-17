"""Unit tests for the Anthropic prompt-caching wrapper."""
import pytest

from agents.caching_llm import AnthropicCachingCompletion, make_caching_llm


def _long_text(chars: int) -> str:
    return "x" * chars


@pytest.fixture
def sonnet():
    return AnthropicCachingCompletion(model="claude-sonnet-4-6", api_key="test-key")


@pytest.fixture
def haiku():
    return AnthropicCachingCompletion(model="claude-haiku-4-5-20251001", api_key="test-key")


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
        model="claude-sonnet-4-6", api_key="test-key", cache_ttl="1h"
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
