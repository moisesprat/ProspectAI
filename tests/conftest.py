import os

# Offline defaults, set before any project import. setdefault only, so a
# developer's real environment is never overwritten.
# crewai 1.12.2's AnthropicCompletion ignores the api_key= argument and reads
# the environment, so a placeholder key is needed to construct the LLM offline.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
# A non-interactive run otherwise shows a tracing-consent prompt.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

import pytest
from utils import sector_membership, yfinance_cache


@pytest.fixture(autouse=True)
def _clear_yfinance_cache():
    """Ensure the module-level yfinance cache is empty before every test."""
    yfinance_cache.clear()


@pytest.fixture
def real_sector_check():
    """Request this fixture to run the real sector-membership check (phase 4.1) in a test."""


@pytest.fixture(autouse=True)
def _offline_sector_check(request, monkeypatch):
    """Replace the sector-membership check with an async no-op unless the test opts in.

    No test may reach Yahoo, and every pre-existing test keeps its pre-phase behaviour (no extra
    warnings, no memo key). The signature is open on purpose: a keyword added to the check later
    (plan 04.1-03 forwards ``tracker=``) must still be accepted here. Tests that exercise the
    check request the ``real_sector_check`` fixture.
    """
    if "real_sector_check" in request.fixturenames:
        return

    async def _no_check(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(sector_membership, "check_sector_membership", _no_check)
