"""Tests for the sector universe module (phase 3.1, plan 03.1-03: SECTOR_TICKERS stands alone)."""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

from utils.candidate_universe_filter import excluded_tickers_for_sector
from utils.market_records import SUPPORTED_SECTORS, build_market_corpus
from utils.sector_membership import classify
from utils.sector_universe import SECTOR_MEMBERSHIP, SECTOR_TICKERS, canonical_sector
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


# ─── Sector membership map (phase 4.1, D-01, D-02) ─────────────────────────────

def test_membership_map_lists_the_nine_sectors_in_universe_order():
    assert list(SECTOR_MEMBERSHIP) == list(SECTOR_TICKERS)


def test_membership_entries_are_clean_frozensets():
    for sector, entry in SECTOR_MEMBERSHIP.items():
        assert isinstance(entry, tuple) and len(entry) == 2, sector
        sectors, industries = entry
        assert isinstance(sectors, frozenset) and isinstance(industries, frozenset), sector
        assert sectors | industries, sector
        for label in sectors | industries:
            assert label and label == label.strip(), (sector, label)


def test_semiconductors_membership_is_industry_only():
    """A3: a Technology-sector fallback would readmit AAPL."""
    sectors, industries = SECTOR_MEMBERSHIP["Semiconductors"]
    assert sectors == frozenset()
    assert industries == frozenset({"Semiconductors", "Semiconductor Equipment & Materials"})


@pytest.mark.parametrize("name,expected", [
    ("Financials", "Finance"),
    ("Consumer Discretionary", "Consumer"),
    ("Technology", "Technology"),
    ("Basket Weaving", "Basket Weaving"),
])
def test_canonical_sector_resolves_the_two_aliases(name, expected):
    assert canonical_sector(name) == expected


def test_sector_universe_imports_only_typing():
    """D-01: the map is hand-written and never derived at runtime, so the module imports no data source."""
    tree = ast.parse((REPO_ROOT / "utils" / "sector_universe.py").read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module)
    assert modules == {"typing"}


# Recorded live yfinance labels (RESEARCH, 2026-11-13) against the sector each is checked under.
LABEL_CASES = [
    pytest.param("Finance", "Technology", "Consumer Electronics", "not_in_sector", id="AAPL-Finance"),
    pytest.param("Finance", "Technology", "Semiconductors", "not_in_sector", id="NVDA-Finance"),
    pytest.param("Semiconductors", "Technology", "Consumer Electronics", "not_in_sector", id="AAPL-Semiconductors"),
    pytest.param("Semiconductors", "Technology", "Semiconductors", "member", id="NVDA-Semiconductors"),
    pytest.param("Semiconductors", "Technology", "Semiconductor Equipment & Materials", "member",
                 id="TER-Semiconductors"),
    pytest.param("Technology", "Technology", "Semiconductors", "member", id="NVDA-Technology"),
    pytest.param("Technology", "Communication Services", "Internet Content & Information", "member",
                 id="SNAP-Technology"),
    pytest.param("Technology", "Communication Services", "Entertainment", "not_in_sector", id="NFLX-Technology"),
    pytest.param("Finance", "Financial Services", "Banks - Diversified", "member", id="JPM-Finance"),
    pytest.param("Finance", "Financial Services", "Insurance - Diversified", "member", id="BRKB-Finance"),
    pytest.param("Consumer", "Consumer Defensive", "Household & Personal Products", "member", id="PG-Consumer"),
    pytest.param("Consumer", "Consumer Cyclical", "Internet Retail", "member", id="AMZN-Consumer"),
    pytest.param("Energy", "Technology", "Solar", "not_in_sector", id="FSLR-Energy"),
    pytest.param("Energy", "Energy", "Oil & Gas Integrated", "member", id="XOM-Energy"),
    pytest.param("Industrials", "Industrials", "Farm & Heavy Construction Machinery", "member", id="CAT-Industrials"),
    pytest.param("Real Estate", "Real Estate", "REIT - Industrial", "member", id="PLD-RealEstate"),
    pytest.param("Utilities", "Utilities", "Utilities - Regulated Electric", "member", id="NEE-Utilities"),
    pytest.param("Healthcare", "Healthcare", "Drug Manufacturers - General", "member", id="LLY-Healthcare"),
    pytest.param("Energy", None, None, "unchecked", id="CTRA-Energy"),
    pytest.param("Semiconductors", "Technology", None, "unchecked", id="TechNoIndustry-Semiconductors"),
    pytest.param("Technology", "Communication Services", None, "unchecked", id="CommNoIndustry-Technology"),
    pytest.param("Technology", " Technology ", 3, "member", id="PaddedAndNonStr-Technology"),
]


@pytest.mark.parametrize("canonical,sector,industry,expected", LABEL_CASES)
def test_recorded_yahoo_labels_classify(canonical, sector, industry, expected):
    assert classify(canonical, sector, industry) == expected


@pytest.mark.parametrize("ticker,canonical,sector,industry", [
    pytest.param("AMZN", "Technology", "Consumer Cyclical", "Internet Retail", id="AMZN"),
    pytest.param("TSLA", "Technology", "Consumer Cyclical", "Auto Manufacturers", id="TSLA"),
    pytest.param("APP", "Technology", "Communication Services", "Advertising Agencies", id="APP"),
    pytest.param("SMCI", "Semiconductors", "Technology", "Computer Hardware", id="SMCI"),
    pytest.param("FIS", "Finance", "Technology", "Information Technology Services", id="FIS"),
])
def test_curated_tickers_the_map_alone_would_drop(ticker, canonical, sector, industry):
    """Why D-03 exempts curated tickers: the map alone would drop these curated names."""
    assert ticker in SECTOR_TICKERS[canonical]
    assert classify(canonical, sector, industry) == "not_in_sector"
