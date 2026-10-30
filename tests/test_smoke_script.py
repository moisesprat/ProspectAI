"""Offline tests for scripts/smoke_haiku55.py (plan 02-03; MODEL-01 live smoke)."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from config.config import AGENT_MODEL_ENV_KEYS

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "smoke_haiku55.py"
SENTINEL = "sk-ant-SENTINEL-do-not-print-0123456789"


def _load():
    spec = importlib.util.spec_from_file_location("smoke_haiku55", SCRIPT)
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


def _ok_handler(seen):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        content = [{"type": "text", "text": json.dumps({"ticker": "AAPL", "note": "ok"})}]
        if body.get("thinking", {}).get("type") == "adaptive":
            content.insert(0, {"type": "thinking", "thinking": "hmm", "signature": "sig"})
        return httpx.Response(200, json={
            "id": "msg_x", "type": "message", "role": "assistant", "model": body["model"],
            "content": content, "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        })
    return handler


def _error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, json={
        "type": "error",
        "error": {"type": "invalid_request_error", "message": f"bad body echo {SENTINEL}"},
    })


def test_smoke_offline_pass(smoke_env, capsys):
    seen = []
    code = _load().run_smoke(transport=httpx.MockTransport(_ok_handler(seen)))
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("PASS") == 2 and "FAIL" not in out
    assert "tokens_in=11" in out and "stop_reason=end_turn" in out
    assert "thinking" in out  # block types of case B include the thinking block
    assert len(seen) == 2  # exactly two live calls
    assert seen[0]["thinking"] == {"type": "disabled"} and "tools" in seen[0]
    assert seen[1]["thinking"] == {"type": "adaptive"}
    assert seen[1]["output_config"]["effort"] == "low"


def test_smoke_offline_fail(smoke_env, capsys):
    code = _load().run_smoke(transport=httpx.MockTransport(_error_handler))
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("FAIL") == 2
    assert "status=400" in out
    assert "BadRequestError" in out
    assert "bad body echo" not in out


def test_smoke_never_prints_key(smoke_env, capsys):
    smoke = _load()
    smoke.run_smoke(transport=httpx.MockTransport(_ok_handler([])))
    smoke.run_smoke(transport=httpx.MockTransport(_error_handler))
    captured = capsys.readouterr()
    assert SENTINEL not in captured.out
    assert SENTINEL not in captured.err


def test_yaml_models_ignores_env_and_restores_it(smoke_env, capsys):
    smoke_env.setenv("MODEL", "claude-x")
    code = _load().run_smoke(transport=httpx.MockTransport(_ok_handler([])), yaml_models=True)
    out = capsys.readouterr().out
    assert code == 0
    assert "market_analysis=claude-haiku-5-5" in out
    import os
    assert os.environ["MODEL"] == "claude-x"


def test_env_models_honoured_by_default(smoke_env, capsys):
    smoke_env.setenv("MODEL", "claude-haiku-4-5-20251001")
    _load().run_smoke(transport=httpx.MockTransport(_ok_handler([])))
    assert "market_analysis=claude-haiku-4-5-20251001" in capsys.readouterr().out
