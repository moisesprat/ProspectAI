import os

# Offline defaults, set before any project import. setdefault only, so a
# developer's real environment is never overwritten.
# crewai 1.12.2's AnthropicCompletion ignores the api_key= argument and reads
# the environment, so a placeholder key is needed to construct the LLM offline.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
# A non-interactive run otherwise shows a tracing-consent prompt.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

import pytest
from utils import yfinance_cache


@pytest.fixture(autouse=True)
def _clear_yfinance_cache():
    """Ensure the module-level yfinance cache is empty before every test."""
    yfinance_cache.clear()
