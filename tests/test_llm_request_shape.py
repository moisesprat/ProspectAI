"""Offline request-shape gate for Claude Haiku 5.5 (MODEL-01; D-01, D-02, D-03).

Builds the five agents through ``TaskFactory`` (market, technical, fundamental,
investor_strategic, critic -- six phases, draft and final share investor_strategic),
swaps each LLM's HTTP client for a capture transport, and asserts on the JSON body
that would reach the Messages API. Nothing leaves the process (runs under
``--disable-socket``).

Why a wire capture and not a mock of ``messages.create``: the shape Haiku 5.5
refuses (sampling keys, ``budget_tokens``, prefill) and the shape that silently
drops real tools (crewai's structured-output allow-list) are only visible in the
final body.
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
HAIKU_45 = "claude-haiku-4-5-20251001"
SAMPLING_KEYS = ("temperature", "top_p", "top_k")
THINKING_OFF_PHASES = ("market_analysis", "technical_analysis", "fundamental_analysis")
THINKING_LOW_PHASES = ("draft_strategy", "critique_review", "final_strategy")

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


# ─── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_agents_default_to_haiku_55(clean_env):
    captured = await _capture_all(_factory())
    for phase, req in captured.items():
        assert req["body"]["model"] == HAIKU_55, (phase, req["body"]["model"])


@pytest.mark.asyncio
async def test_no_sampling_params(clean_env):
    captured = await _capture_all(_factory())
    for phase, req in captured.items():
        for key in SAMPLING_KEYS:
            assert key not in req["body"], (phase, key)


@pytest.mark.asyncio
async def test_thinking_per_agent(clean_env):
    captured = await _capture_all(_factory())
    for phase in THINKING_OFF_PHASES:
        assert captured[phase]["body"]["thinking"] == {"type": "disabled"}, phase
    for phase in THINKING_LOW_PHASES:
        body = captured[phase]["body"]
        assert body["thinking"] == {"type": "adaptive"}, phase
        assert body["output_config"]["effort"] == "low", phase
    for phase, req in captured.items():
        body = req["body"]
        assert "budget_tokens" not in body["thinking"], phase
        if body["thinking"].get("type") == "disabled":
            assert body.get("output_config", {}).get("effort") not in ("xhigh", "max"), phase


@pytest.mark.asyncio
async def test_effort_rewrite_keeps_content_length_consistent(clean_env):
    captured = await _capture_phase(_factory(), "draft_strategy")
    assert int(captured["content_length"]) == captured["raw_length"]


@pytest.mark.asyncio
async def test_real_tool_survives_on_haiku_55(clean_env):
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
