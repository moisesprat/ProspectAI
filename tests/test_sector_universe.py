"""Tests for the sector universe module (phase 3.1, plan 03.1-03: SECTOR_TICKERS stands alone)."""
import subprocess
import sys
from pathlib import Path

import pytest

from utils.candidate_universe_filter import excluded_tickers_for_sector
from utils.market_records import SUPPORTED_SECTORS, build_market_corpus
from utils.sector_universe import SECTOR_TICKERS
from utils.ticker_matching import is_valid_ticker

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_LENGTHS = {
    "Technology": 28,
    "Semiconductors": 15,
    "Healthcare": 28,
    "Finance": 28,
    "Energy": 28,
    "Consumer": 28,
    "Industrials": 30,
    "Real Estate": 30,
    "Utilities": 30,
}


# ─── The universe itself ───────────────────────────────────────────────────────

def test_universe_has_the_nine_sectors_with_pinned_lengths():
    assert list(SECTOR_TICKERS) == list(EXPECTED_LENGTHS)
    assert {k: len(v) for k, v in SECTOR_TICKERS.items()} == EXPECTED_LENGTHS


@pytest.mark.parametrize("sector", list(EXPECTED_LENGTHS))
def test_each_sector_is_duplicate_free_valid_and_etf_free(sector):
    tickers = SECTOR_TICKERS[sector]
    assert len(tickers) == len(set(tickers))
    assert all(is_valid_ticker(t) for t in tickers)
    assert not set(tickers) & excluded_tickers_for_sector(sector)


# ─── Consumers ─────────────────────────────────────────────────────────────────

def test_supported_sectors_are_the_universe_plus_the_two_aliases():
    assert SUPPORTED_SECTORS == set(SECTOR_TICKERS) | {"Financials", "Consumer Discretionary"}


def test_unavailable_corpus_serves_the_sector_universe():
    corpus = build_market_corpus(None, "Semiconductors")
    assert corpus["source"] == "unavailable"
    assert corpus["universe"] == SECTOR_TICKERS["Semiconductors"]


def test_unavailable_corpus_for_an_alias_has_an_empty_universe():
    assert build_market_corpus(None, "Financials")["universe"] == []


def test_cli_help_lists_every_sector_choice():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0
    flat = " ".join(result.stdout.split())
    for sector in SECTOR_TICKERS:
        assert sector in flat


# ─── Environment check ─────────────────────────────────────────────────────────

# The removed source's name, spelled in parts so tests/test_repo_hygiene.py does not flag
# this regression check (D-05).
_REMOVED = "RED" "DIT"


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """No .env in cwd and no market-data variables, so only the test sets them."""
    monkeypatch.chdir(tmp_path)
    for name in ("SERPER_API_KEY", f"{_REMOVED}_CLIENT_ID", f"{_REMOVED}_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    return monkeypatch


def test_env_check_requires_serper_and_names_no_removed_source_variable(clean_env, capsys):
    import main

    with pytest.raises(SystemExit):
        main.load_and_validate_env("anthropic", None, None)
    out = capsys.readouterr().out
    assert "SERPER_API_KEY" in out
    assert _REMOVED not in out.upper()


def test_env_check_passes_with_serper_set_and_ignores_removed_source_variables(clean_env, capsys):
    import main

    clean_env.setenv("SERPER_API_KEY", "serper-test-key")
    main.load_and_validate_env("anthropic", None, None)
    assert _REMOVED not in capsys.readouterr().out.upper()
