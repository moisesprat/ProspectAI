"""Tests for the Serper queries of the market search (phase 4.1 D-14).

The exact strings are pinned on purpose: any change to the wording, to ``SEARCH_PHRASES`` or to the
order of ``FALLBACK_PICKS`` must be a conscious edit of this file. Live behaviour of the other eight
sectors is judged by the milestone's acceptance runs, not here.
"""
import pytest

from utils.market_records import QUERY_SYMBOLS, serper_queries
from utils.sector_universe import FALLBACK_PICKS, SECTOR_TICKERS

DATE = "2026-11-13"

EXPECTED = {
    "Technology": [
        "technology stocks investors discussing 2026-11-13",
        "technology stocks to watch analyst picks 2026-11-13",
        "most discussed trending technology stocks AAPL MSFT GOOGL CRM this week 2026-11-13",
    ],
    "Semiconductors": [
        "semiconductor stocks investors discussing 2026-11-13",
        "semiconductor stocks to watch analyst picks 2026-11-13",
        "most discussed trending semiconductor stocks NVDA AMD AVGO QCOM this week 2026-11-13",
    ],
    "Healthcare": [
        "healthcare stocks investors discussing 2026-11-13",
        "healthcare stocks to watch analyst picks 2026-11-13",
        "most discussed trending healthcare stocks JNJ UNH LLY ABBV this week 2026-11-13",
    ],
    "Finance": [
        "bank and financial services stocks investors discussing 2026-11-13",
        "bank and financial services stocks to watch analyst picks 2026-11-13",
        "most discussed trending bank and financial services stocks JPM BAC WFC GS this week 2026-11-13",
    ],
    "Energy": [
        "oil and gas energy stocks investors discussing 2026-11-13",
        "oil and gas energy stocks to watch analyst picks 2026-11-13",
        "most discussed trending oil and gas energy stocks XOM CVX COP SLB this week 2026-11-13",
    ],
    "Consumer": [
        "consumer retail and discretionary stocks investors discussing 2026-11-13",
        "consumer retail and discretionary stocks to watch analyst picks 2026-11-13",
        "most discussed trending consumer retail and discretionary stocks WMT HD MCD NKE this week 2026-11-13",
    ],
    "Industrials": [
        "industrial stocks investors discussing 2026-11-13",
        "industrial stocks to watch analyst picks 2026-11-13",
        "most discussed trending industrial stocks CAT DE HON UPS this week 2026-11-13",
    ],
    "Real Estate": [
        "real estate REIT stocks investors discussing 2026-11-13",
        "real estate REIT stocks to watch analyst picks 2026-11-13",
        "most discussed trending real estate REIT stocks AMT PLD EQIX PSA this week 2026-11-13",
    ],
    "Utilities": [
        "electric and gas utility stocks investors discussing 2026-11-13",
        "electric and gas utility stocks to watch analyst picks 2026-11-13",
        "most discussed trending electric and gas utility stocks NEE DUK AEP EXC this week 2026-11-13",
    ],
}
EXPECTED["Financials"] = EXPECTED["Finance"]
EXPECTED["Consumer Discretionary"] = EXPECTED["Consumer"]


@pytest.mark.parametrize("name", list(EXPECTED))
def test_queries_for_every_spa_sector_are_pinned(name):
    assert serper_queries(name, DATE) == EXPECTED[name]


def test_the_aliases_give_the_same_queries_as_their_package_sector():
    assert serper_queries("Financials", DATE) == serper_queries("Finance", DATE)
    assert serper_queries("Consumer Discretionary", DATE) == serper_queries("Consumer", DATE)


@pytest.mark.parametrize("name", list(EXPECTED))
def test_every_query_carries_the_run_date_and_only_plain_text(name):
    queries = serper_queries(name, DATE)
    assert len(queries) == 3
    for query in queries:
        assert DATE in query
        assert len(query) <= 150
        assert ":" not in query and "/" not in query
    assert serper_queries(name, DATE) == queries


@pytest.mark.parametrize("sector", list(SECTOR_TICKERS))
def test_symbols_named_in_the_third_query_are_curated_and_valid(sector):
    third = serper_queries(sector, DATE)[2]
    expected = list(FALLBACK_PICKS[sector][:QUERY_SYMBOLS])
    named = [word for word in third.split() if word in SECTOR_TICKERS[sector]]
    assert named == expected
    assert QUERY_SYMBOLS == 4
    assert all(symbol in SECTOR_TICKERS[sector] for symbol in expected)
    for query in serper_queries(sector, DATE)[:2]:
        assert not any(symbol in query.split() for symbol in expected)


def test_unmapped_sector_keeps_the_original_queries():
    assert serper_queries("Basket Weaving", "2026-04-29") == [
        "Basket Weaving sector stocks investors discussing 2026-04-29",
        "Basket Weaving sector stocks to watch analyst picks 2026-04-29",
        "most discussed trending Basket Weaving stocks this week 2026-04-29",
    ]
