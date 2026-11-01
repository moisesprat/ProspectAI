"""Offline request-shape gate for Claude Haiku 5.5 and Sonnet 5.5 (MODEL-01; D-01, D-02, D-03).

Builds the five agents through ``TaskFactory`` (market, technical, fundamental,
investor_strategic, critic -- six phases, draft and final share investor_strategic),
swaps each LLM's HTTP client for a capture transport, and asserts on the JSON body
that would reach the Messages API. Nothing leaves the process (runs under
``--disable-socket``).

Why a wire capture and not a mock of ``messages.create``: the shape Haiku 5.5
refuses (sampling keys, ``budget_tokens``, prefill) and the shape that silently
drops real tools (crewai's structured-output allow-list) are only visible in the
final body.

Model split (plan 02-25): investor_strategic (draft and final steps) and critic run
claude-sonnet-5-5, the other three agents claude-haiku-5-5. Sonnet 5.5 also rejects
thinking of type disabled or enabled and a forced tool choice. The expected thinking
body is written here from the documented API facts (``expected_thinking``), never
read back from the production capability table, so a table mistake fails a test.
"""
import json

import httpx
import pytest
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from config.config import AGENT_MODEL_ENV_KEYS, Config
from prospect_ai_crew import TaskFactory
from prospect_ai_flow import PHASES

HAIKU_55 = "claude-haiku-5-5"
SONNET_55 = "claude-sonnet-5-5"
HAIKU_45 = "claude-haiku-4-5-20251001"
SAMPLING_KEYS = ("temperature", "top_p", "top_k")
THINKING_OFF_PHASES = ("market_analysis", "technical_analysis", "fundamental_analysis")
THINKING_LOW_PHASES = ("draft_strategy", "critique_review", "final_strategy")
SONNET_PHASES = THINKING_LOW_PHASES
HAIKU_PHASES = THINKING_OFF_PHASES

# Phase to the agents.yaml key whose model and thinking mode that phase uses.
PHASE_AGENT_KEY = {
    "market_analysis": "market_analyst",
    "technical_analysis": "technical_analyst",
    "fundamental_analysis": "fundamental_analyst",
    "draft_strategy": "investor_strategic",
    "critique_review": "critic",
    "final_strategy": "investor_strategic",
}

REAL_TOOL = {
    "type": "function",
    "function": {
        "name": "real_tool",
        "description": "d",
        "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
    },
}


class _Answer(BaseModel):
    ticker: str
    note: str


_ANSWER_JSON = json.dumps({"ticker": "AAA", "note": "ok"})


# ─── Capture helper (also imported by tests/test_caching_llm.py) ──────────────

class CaptureTransport(httpx.AsyncBaseTransport):
    """Applies the LLM's own interceptor (as crewai's transport would), records
    the outbound request, and returns a canned 200 Messages response."""

    def __init__(self, llm, content_blocks):
        self._llm = llm
        self._content = content_blocks
        self.requests: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if getattr(self._llm, "interceptor", None) is not None:
            request = await self._llm.interceptor.aon_outbound(request)
        self.requests.append(
            {
                "body": json.loads(request.content),
                "beta": request.headers.get("anthropic-beta", ""),
                "url": str(request.url),
                "content_length": request.headers.get("content-length"),
                "raw_length": len(request.content),
            }
        )
        message = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": self._llm.model,
            "content": self._content,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        return httpx.Response(200, json=message)


def install_capture(llm, content_blocks=None) -> CaptureTransport:
    """Replace ``llm.async_client`` with one whose transport captures requests."""
    if content_blocks is None:
        content_blocks = [{"type": "text", "text": _ANSWER_JSON}]
    transport = CaptureTransport(llm, content_blocks)
    llm.async_client = AsyncAnthropic(
        api_key="k", http_client=httpx.AsyncClient(transport=transport)
    )
    return transport


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    for name in ("MODEL", "MODEL_PROVIDER", "ANTHROPIC_MODEL", "OLLAMA_MODEL",
                 "OLLAMA_BASE_URL", *AGENT_MODEL_ENV_KEYS.values()):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _factory():
    return TaskFactory(config=Config())


async def _capture_phase(factory, phase, tools=None):
    llm = factory._phase_config[phase]["agent"].llm
    transport = install_capture(llm)
    result = await llm.acall(
        [{"role": "user", "content": "hi"}], tools=tools, response_model=_Answer
    )
    assert isinstance(result, _Answer)
    assert len(transport.requests) == 1
    return transport.requests[0]


async def _capture_all(factory, tools=None):
    return {p: await _capture_phase(factory, p, tools) for p in PHASES}
# ─── Expectation helpers (written from the documented API facts) ───────────────

def yaml_agent(agent_key):
    """The agent's entry from config/agents.yaml, read with PyYAML."""
    from pathlib import Path

    import yaml

    import config as config_pkg

    raw = yaml.safe_load((Path(config_pkg.__file__).parent / "agents.yaml").read_text())
    return raw["agents"][agent_key]


def expected_thinking(model, mode):
    """(thinking body, effort) the Messages API accepts for ``model`` and ``mode``.

    Haiku 5.5: off is ``disabled``; low is ``adaptive`` with effort low.
    Sonnet 5.5: ``disabled`` is a 400, so off is ``between_tools`` (nothing else in
    the dict, no effort); low is ``adaptive`` with effort low.
    Any other model is sent neither thinking nor effort.
    """
    if HAIKU_55 in model:
        if mode == "off":
            return {"type": "disabled"}, None
        return {"type": "adaptive"}, "low"
    if SONNET_55 in model:
        if mode == "off":
            return {"type": "between_tools"}, None
        return {"type": "adaptive"}, "low"
    return None, None


def body_effort(body):
    return (body.get("output_config") or {}).get("effort")


def assert_thinking_matches(body, model, mode, label):
    thinking, effort = expected_thinking(model, mode)
    assert body.get("thinking") == thinking, (label, body.get("thinking"), thinking)
    assert body_effort(body) == effort, (label, body_effort(body), effort)
    assert "budget_tokens" not in (body.get("thinking") or {}), label



# ─── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_models_follow_the_split(clean_env):
    captured = await _capture_all(_factory())
    for phase in HAIKU_PHASES:
        assert captured[phase]["body"]["model"] == HAIKU_55, phase
    for phase in SONNET_PHASES:
        assert captured[phase]["body"]["model"] == SONNET_55, phase


@pytest.mark.asyncio
async def test_sonnet_phases_never_carry_a_rejected_shape(clean_env):
    for tools in (None, [REAL_TOOL]):
        captured = await _capture_all(_factory(), tools=tools)
        for phase in SONNET_PHASES:
            req = captured[phase]
            body = req["body"]
            label = (phase, bool(tools))
            assert body["model"] == SONNET_55, label
            for key in SAMPLING_KEYS:
                assert key not in body, (label, key)
            assert "budget_tokens" not in (body.get("thinking") or {}), label
            assert body["thinking"]["type"] not in ("disabled", "enabled"), label
            mode = yaml_agent(PHASE_AGENT_KEY[phase])["thinking"]
            assert_thinking_matches(body, SONNET_55, mode, label)
            assert "output_format" in body, label
            assert "structured-outputs-2025-11-13" in req["beta"], label
            assert (body.get("tool_choice") or {}).get("type") not in ("any", "tool"), label
            assert body["messages"][-1]["role"] == "user", label


@pytest.mark.asyncio
async def test_no_sampling_params(clean_env):
    captured = await _capture_all(_factory())
    for phase, req in captured.items():
        for key in SAMPLING_KEYS:
            assert key not in req["body"], (phase, key)


@pytest.mark.asyncio
async def test_thinking_per_agent(clean_env):
    captured = await _capture_all(_factory())
    for phase, req in captured.items():
        body = req["body"]
        mode = yaml_agent(PHASE_AGENT_KEY[phase])["thinking"]
        assert_thinking_matches(body, body["model"], mode, phase)
        if (body.get("thinking") or {}).get("type") in ("disabled", "between_tools"):
            assert body_effort(body) not in ("xhigh", "max"), phase


@pytest.mark.asyncio
async def test_effort_rewrite_keeps_content_length_consistent(clean_env):
    captured = await _capture_phase(_factory(), "draft_strategy")
    assert int(captured["content_length"]) == captured["raw_length"]


@pytest.mark.asyncio
async def test_real_tool_survives_on_every_phase(clean_env):
    captured = await _capture_all(_factory(), tools=[REAL_TOOL])
    for phase, req in captured.items():
        body = req["body"]
        names = [t.get("name") for t in body.get("tools", [])]
        assert "real_tool" in names, (phase, names)
        assert "output_format" in body, phase
        assert "structured-outputs-2025-11-13" in req["beta"], phase


@pytest.mark.asyncio
async def test_last_message_is_user(clean_env):
    captured = await _capture_all(_factory())
    for phase, req in captured.items():
        assert req["body"]["messages"][-1]["role"] == "user", phase


@pytest.mark.asyncio
async def test_env_override_still_wins_and_is_model_gated(clean_env):
    clean_env.setenv("AGENT_MARKET_ANALYST_MODEL", HAIKU_45)
    factory = _factory()
    market = await _capture_phase(factory, "market_analysis")
    body = market["body"]
    assert body["model"] == HAIKU_45
    assert "thinking" not in body
    assert "output_config" not in body
    for key in SAMPLING_KEYS:
        assert key not in body
    # The other agents are unaffected by the one override.
    technical = await _capture_phase(factory, "technical_analysis")
    assert technical["body"]["model"] == HAIKU_55
    assert technical["body"]["thinking"] == {"type": "disabled"}


def test_yaml_thinking_values_are_closed(clean_env, tmp_path):
    from pathlib import Path

    import yaml

    import config as config_pkg
    from agents.market_analyst_agent import MarketAnalystAgent

    raw = yaml.safe_load((Path(config_pkg.__file__).parent / "agents.yaml").read_text())
    raw["agents"]["market_analyst"]["thinking"] = "medium"
    bad = tmp_path / "agents.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="market_analyst"):
        MarketAnalystAgent(config_path=str(bad))


# ─── First-turn tool forcing (canary finding, MODEL-01) ───────────────────────
# The first live canary showed Haiku 5.5 answering the market phase straight from
# the output schema without calling either tool. For the thinking-off tool phases
# the request now carries tool_choice {"type": "any"} until a tool result is in the
# conversation; thinking-enabled phases cannot force a tool (API rule).

_TOOL_ROUND_TRIP = [
    {"role": "user", "content": "hi"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "toolu_1", "type": "function",
             "function": {"name": "real_tool", "arguments": '{"x": "y"}'}}
        ],
    },
    {"role": "tool", "tool_call_id": "toolu_1", "name": "real_tool", "content": "result"},
]


@pytest.mark.asyncio
async def test_first_turn_forces_a_tool_when_thinking_is_off(clean_env):
    captured = await _capture_all(_factory(), tools=[REAL_TOOL])
    for phase in THINKING_OFF_PHASES:
        assert captured[phase]["body"].get("tool_choice") == {"type": "any"}, phase


@pytest.mark.asyncio
async def test_thinking_phases_are_not_forced(clean_env):
    captured = await _capture_all(_factory(), tools=[REAL_TOOL])
    for phase in THINKING_LOW_PHASES:
        assert captured[phase]["body"].get("tool_choice") != {"type": "any"}, phase


@pytest.mark.asyncio
async def test_no_forcing_once_a_tool_result_is_in_the_conversation(clean_env):
    factory = _factory()
    llm = factory._phase_config["market_analysis"]["agent"].llm
    transport = install_capture(llm)
    await llm.acall(list(_TOOL_ROUND_TRIP), tools=[REAL_TOOL], response_model=_Answer)
    body = transport.requests[0]["body"]
    assert body.get("tool_choice") != {"type": "any"}
    assert any(t.get("name") == "real_tool" for t in body["tools"])


@pytest.mark.asyncio
async def test_no_tools_means_no_tool_choice(clean_env):
    captured = await _capture_phase(_factory(), "market_analysis", tools=None)
    assert "tool_choice" not in captured["body"]


@pytest.mark.asyncio
async def test_older_model_override_is_not_forced(clean_env):
    clean_env.setenv("AGENT_MARKET_ANALYST_MODEL", HAIKU_45)
    captured = await _capture_phase(_factory(), "market_analysis", tools=[REAL_TOOL])
    assert captured["body"].get("tool_choice") != {"type": "any"}
