"""
Tests for CLI argument parsing and .env validation in main.py.
No LLM calls, no network — validates startup logic only.
"""

import os
import sys
import pytest
from unittest.mock import patch
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def _run_parse(args: list[str]):
    """Import parse_arguments freshly and run it with the given argv."""
    with patch("sys.argv", ["main.py"] + args):
        # Re-import to avoid cached module state
        if "main" in sys.modules:
            del sys.modules["main"]
        import main
        return main.parse_arguments()


def _run_validation(env: dict):
    """Run load_and_validate_env with a real .env file containing env vars."""
    import tempfile, textwrap
    content = "\n".join(f"{k}={v}" for k, v in env.items())
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        tmp_path = Path(f.name)

    if "main" in sys.modules:
        del sys.modules["main"]

    try:
        import main
        with patch.object(Path, "exists", return_value=True), \
             patch("main.load_dotenv", lambda p: None), \
             patch.dict(os.environ, env, clear=False):
            main.load_and_validate_env()
    finally:
        tmp_path.unlink(missing_ok=True)


# ── CLI argument parsing ──────────────────────────────────────────────────────

class TestArgumentParsing:

    def test_defaults(self):
        args = _run_parse([])
        assert args.sector == "Technology"
        assert args.ollama is False
        assert args.model is None
        assert args.url is None

    def test_sector_flag(self):
        for sector in ("Technology", "Healthcare", "Finance", "Energy", "Consumer"):
            args = _run_parse([f"--sector", sector])
            assert args.sector == sector

    def test_invalid_sector_exits(self):
        with pytest.raises(SystemExit):
            _run_parse(["--sector", "Crypto"])

    def test_ollama_flag(self):
        args = _run_parse(["--ollama"])
        assert args.ollama is True

    def test_model_override(self):
        args = _run_parse(["--model", "claude-opus-4-6"])
        assert args.model == "claude-opus-4-6"

    def test_ollama_url_override(self):
        args = _run_parse(["--ollama", "--url", "http://192.168.1.5:11434"])
        assert args.url == "http://192.168.1.5:11434"

    def test_combined_flags(self):
        args = _run_parse(["--ollama", "--model", "llama3.2:8b", "--sector", "Finance"])
        assert args.ollama is True
        assert args.model == "llama3.2:8b"
        assert args.sector == "Finance"


# ── .env validation ───────────────────────────────────────────────────────────

class TestEnvValidation:

    def test_missing_env_file_exits(self):
        if "main" in sys.modules:
            del sys.modules["main"]
        import main
        with patch.object(Path, "exists", return_value=False), \
             pytest.raises(SystemExit) as exc:
            main.load_and_validate_env()
        assert exc.value.code == 1

    def test_valid_anthropic_with_reddit(self):
        """Should NOT raise when Anthropic + Reddit keys are present."""
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "REDDIT_CLIENT_ID": "abc",
            "REDDIT_CLIENT_SECRET": "xyz",
        }
        # Should complete without SystemExit
        _run_validation(env)

    def test_valid_anthropic_with_serper(self):
        """Should NOT raise when Anthropic + Serper keys are present."""
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "SERPER_API_KEY": "serper-key",
        }
        _run_validation(env)

    def test_missing_anthropic_key_exits(self):
        env = {
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "SERPER_API_KEY": "serper-key",
        }
        with pytest.raises(SystemExit):
            _run_validation(env)

    def test_missing_anthropic_model_exits(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "SERPER_API_KEY": "serper-key",
        }
        with pytest.raises(SystemExit):
            _run_validation(env)

    def test_no_market_data_source_exits(self):
        """Neither Reddit nor Serper — must fail."""
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
        }
        with pytest.raises(SystemExit):
            _run_validation(env)

    def test_partial_reddit_credentials_exits(self):
        """Only one of the two Reddit keys is not enough."""
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "REDDIT_CLIENT_ID": "only-id",
            # REDDIT_CLIENT_SECRET missing
        }
        with pytest.raises(SystemExit):
            _run_validation(env)

    def test_ollama_requires_base_url_and_model(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "SERPER_API_KEY": "serper-key",
            "MODEL_PROVIDER": "ollama",
            # OLLAMA_BASE_URL and OLLAMA_MODEL missing
        }
        with pytest.raises(SystemExit):
            _run_validation(env)

    def test_ollama_valid_when_all_keys_present(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "SERPER_API_KEY": "serper-key",
            "MODEL_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3.5:9b",
        }
        _run_validation(env)  # should not raise
