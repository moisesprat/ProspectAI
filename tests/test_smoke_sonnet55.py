"""Offline tests for scripts/smoke_sonnet55.py (plan 02-25, M4).

The script is run live by a human with their own key (plan 02-26). Here the
transport is an ``httpx.MockTransport``, so nothing leaves the process (runs under
``--disable-socket``). Pinned: the three outcomes (pass, thinking-off fallback, no
fallback), that a refusal is a failure, that no key or response text is ever printed
and that ``--yaml-models`` ignores and restores the environment.

The thinking mode the real agents.yaml declares for the two Sonnet agents changes in
plan 02-26 if the fallback is applied, so the fallback tests pin the mode with a
temporary YAML copy and the pass test follows whatever the file declares.
"""
import importlib.util
import json
import os
from pathlib import Path

import httpx
import pytest
import yaml

from config.config import AGENT_MODEL_ENV_KEYS
from tests.test_llm_request_shape import body_effort, expected_thinking, yaml_agent

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "smoke_sonnet55.py"
SENTINEL = "sk-ant-SENTINEL-KEY-do-not-print"
ECHO = "bad body echo SECRET-RESPONSE-TEXT"
SONNET_55 = "claude-sonnet-5-5"


def _load():
    spec = importlib.util.spec_from_file_location("smoke_sonnet55", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def smoke_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL)
    for name in ("MODEL", "MODEL_PROVIDER", "ANTHROPIC_MODEL", "OLLAMA_MODEL",
                 "OLLAMA_BASE_URL", *AGENT_MODEL_ENV_KEYS.values()):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _pin_thinking(monkeypatch, tmp_path, mode):
    """Point the agent config loader's default at a copy of agents.yaml whose two
    Sonnet agents declare ``mode``."""
    import config as config_pkg
    from config.agent_config_loader import AgentConfigLoader

    raw = yaml.safe_load((Path(config_pkg.__file__).parent / "agents.yaml").read_text())
    for key in ("investor_strategic", "critic"):
        raw["agents"][key]["thinking"] = mode
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(raw))
    original = AgentConfigLoader.__init__

    def init(self, config_path=None):
        original(self, config_path or str(path))

    monkeypatch.setattr(AgentConfigLoader, "__init__", init)


def _ok_response(body, text=None):
    content = [{"type": "text", "text": text or json.dumps({"ticker": "AAPL", "note": "ok"})}]
    if (body.get("thinking") or {}).get("type") == "adaptive":
        content.insert(0, {"type": "thinking", "thinking": "hmm", "signature": "sig"})
    return httpx.Response(200, json={
        "id": "msg_x", "type": "message", "role": "assistant", "model": body["model"],
        "content": content, "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 11, "output_tokens": 7},
    })


def _bad_request():
    return httpx.Response(400, json={
        "type": "error", "error": {"type": "invalid_request_error", "message": ECHO},
    })


def _handler(seen, reject=None):
    """200 for every request except where ``reject(body)`` is true (a 400)."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if reject is not None and reject(body):
            return _bad_request()
        return _ok_response(body)
    return handler


def _reject_adaptive(body):
    return (body.get("thinking") or {}).get("type") == "adaptive"


def _reject_structured(body):
    return "output_format" in body


def _run(smoke_env, handler, **kwargs):
    return _load().run_smoke(transport=httpx.MockTransport(handler), **kwargs)


def test_pass_makes_two_calls_with_the_configured_shape(smoke_env, capsys):
    seen = []
    code = _run(smoke_env, _handler(seen))
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("SMOKE VERDICT: PASS") == 1 and "SMOKE VERDICT: FAIL" not in out
    assert len(seen) == 2  # exactly two live calls
    for body, agent in zip(seen, ("investor_strategic", "critic")):
        assert body["model"] == SONNET_55
        thinking, effort = expected_thinking(SONNET_55, yaml_agent(agent)["thinking"])
        assert body["thinking"] == thinking
        assert body_effort(body) == effort
        assert "output_format" in body
        assert "tool_choice" not in body
    assert "tokens_in=11" in out and "stop_reason=end_turn" in out


def test_rejected_adaptive_shape_names_the_thinking_off_fallback(smoke_env, tmp_path, capsys):
    _pin_thinking(smoke_env, tmp_path, "low")
    seen = []
    code = _run(smoke_env, _handler(seen, reject=_reject_adaptive))
    out = capsys.readouterr().out
    assert code == 1
    assert "SMOKE VERDICT: FAIL" in out and "SMOKE VERDICT: PASS" not in out
    assert "S3" in out and "S4" in out
    s3 = next(l for l in out.splitlines() if l.startswith("S3"))
    s4 = next(l for l in out.splitlines() if l.startswith("S4"))
    assert "FAIL" in s3 and "PASS" in s4
    fallback = [l for l in out.splitlines() if l.startswith("FALLBACK:")]
    assert len(fallback) == 1
    assert "thinking off" in fallback[0] and "accepted" in fallback[0]
    assert "investor_strategic" in fallback[0] and "critic" in fallback[0]
    assert "SECRET-RESPONSE-TEXT" not in out and ECHO not in out
    assert len(seen) == 4  # S1, S2, then the two diagnostics


@pytest.mark.parametrize("mode", ["low", "off"])
def test_rejected_structured_output_has_no_fallback(smoke_env, tmp_path, capsys, mode):
    _pin_thinking(smoke_env, tmp_path, mode)
    seen = []
    code = _run(smoke_env, _handler(seen, reject=_reject_structured))
    out = capsys.readouterr().out
    assert code == 1
    assert "SMOKE VERDICT: FAIL" in out
    s3 = next(l for l in out.splitlines() if l.startswith("S3"))
    s4 = next(l for l in out.splitlines() if l.startswith("S4"))
    assert "PASS" in s3 and "FAIL" in s4
    fallback = [l for l in out.splitlines() if l.startswith("FALLBACK:")]
    assert len(fallback) == 1
    assert "none" in fallback[0].lower() and "must not go ahead" in fallback[0]
    assert "SECRET-RESPONSE-TEXT" not in out


def test_thinking_off_in_yaml_sends_between_tools(smoke_env, tmp_path, capsys):
    _pin_thinking(smoke_env, tmp_path, "off")
    seen = []
    code = _run(smoke_env, _handler(seen))
    capsys.readouterr()
    assert code == 0 and len(seen) == 2
    for body in seen:
        assert body["model"] == SONNET_55
        assert body["thinking"] == {"type": "between_tools"}
        assert body_effort(body) is None
        assert "output_format" in body


def test_refusal_is_a_failure(smoke_env, capsys):
    def handler(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "msg_x", "type": "message", "role": "assistant", "model": body["model"],
            "content": [], "stop_reason": "refusal", "stop_sequence": None,
            "stop_details": {"type": "refusal", "category": "general_harms"},
            "usage": {"input_tokens": 3, "output_tokens": 0},
        })

    code = _run(smoke_env, handler)
    out = capsys.readouterr().out
    assert code == 1
    assert "stop_reason=refusal" in out
    assert "SMOKE VERDICT: FAIL" in out
    assert "[S1]" in out and "FAIL" in next(l for l in out.splitlines() if l.startswith("[S1]"))


def test_non_400_failure_is_not_reported_as_a_shape_result(smoke_env, capsys):
    def handler(request):
        return httpx.Response(529, json={
            "type": "error", "error": {"type": "overloaded_error", "message": ECHO},
        })

    seen_code = _run(smoke_env, handler)
    out = capsys.readouterr().out
    assert seen_code == 1
    assert "SMOKE VERDICT: FAIL" in out
    assert "not a request-shape result" in out and "status=529" in out
    assert not [l for l in out.splitlines() if l.startswith("FALLBACK:")]
    assert "SECRET-RESPONSE-TEXT" not in out


def test_never_prints_the_key(smoke_env, tmp_path, capsys):
    smoke = _load()
    for reject, mode in ((None, "low"), (_reject_adaptive, "low"), (_reject_structured, "off")):
        _pin_thinking(smoke_env, tmp_path, mode)
        smoke.run_smoke(transport=httpx.MockTransport(_handler([], reject=reject)))
    smoke.run_smoke(transport=httpx.MockTransport(lambda request: _bad_request()))
    captured = capsys.readouterr()
    assert SENTINEL not in captured.out and SENTINEL not in captured.err
    assert "SECRET-RESPONSE-TEXT" not in captured.out + captured.err


def test_yaml_models_ignores_env_and_restores_it(smoke_env, capsys):
    smoke_env.setenv("MODEL", "claude-x")
    smoke_env.setenv("AGENT_CRITIC_MODEL", "claude-y")
    code = _run(smoke_env, _handler([]), yaml_models=True)
    out = capsys.readouterr().out
    first = out.splitlines()[0]
    assert code == 0
    for phase, model in (
        ("market_analysis", "claude-haiku-5-5"), ("technical_analysis", "claude-haiku-5-5"),
        ("fundamental_analysis", "claude-haiku-5-5"), ("draft_strategy", SONNET_55),
        ("critique_review", SONNET_55), ("final_strategy", SONNET_55),
    ):
        assert f"{phase}={model}" in first, (phase, first)
    assert os.environ["MODEL"] == "claude-x"
    assert os.environ["AGENT_CRITIC_MODEL"] == "claude-y"
