"""
Candidate Universe Filter — deterministic exclusion of sector-benchmark ETFs
and broad-market ETFs from the Market Analyst's candidate list.

Applied once, after MarketAnalysisOutput is parsed, regardless of whether the
candidates came from the search corpus or utils.sector_universe.SECTOR_TICKERS (already
ETF-free). The search corpus (free-text extraction from Serper snippets)
has no such curation and can surface a sector's own benchmark ETF --
e.g. XLE for Energy -- as if it were an investable single-stock candidate).
The sector aliases the web app sends (Financials, Consumer Discretionary) exclude the
same benchmark ETF as their package sector (Finance, Consumer).
Applying the filter after parsing, rather than duplicating it in each source
path, guarantees it cannot be bypassed by whichever source is active.
"""

from typing import FrozenSet, List, Tuple

from utils.sector_universe import SECTOR_ALIASES

# Standard SPDR/iShares sector-benchmark ETF per ProspectAI sector, matching
# the sectors in utils.sector_universe.SECTOR_TICKERS.
SECTOR_BENCHMARK_ETF = {
    "Technology": "XLK",
    "Semiconductors": "SOXX",
    "Healthcare": "XLV",
    "Finance": "XLF",
    "Energy": "XLE",
    "Consumer": "XLY",
    "Industrials": "XLI",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

# Broad-market ETFs that could plausibly appear in search snippets for any
# sector as a market-wide reference point, not a sector-specific pick.
BROAD_MARKET_ETFS: FrozenSet[str] = frozenset({
    "SPY", "QQQ", "DIA", "IWM", "VOO", "VTI", "VXUS", "IVV",
})


def excluded_tickers_for_sector(sector: str) -> FrozenSet[str]:
    """Tickers to exclude from the candidate universe for a given sector.

    A sector alias the web app sends ("Financials", "Consumer Discretionary") resolves to its
    package sector first, so it excludes the same benchmark ETF (XLF, XLY) as "Finance" and
    "Consumer" (phase 4 CORR-06). The universe is not remapped, only this lookup.
    """
    excluded = set(BROAD_MARKET_ETFS)
    benchmark = SECTOR_BENCHMARK_ETF.get(SECTOR_ALIASES.get(sector, sector))
    if benchmark:
        excluded.add(benchmark)
    return frozenset(excluded)


def filter_candidates(candidate_stocks: List, sector: str) -> Tuple[List, List[str]]:
    """Split candidate_stocks into (kept, dropped_tickers) for the given sector.

    `candidate_stocks` is a list of objects exposing a `.ticker` attribute
    (e.g. schemas.agent_outputs.CandidateStock instances).
    """
    excluded = excluded_tickers_for_sector(sector)
    kept = [c for c in candidate_stocks if c.ticker.upper() not in excluded]
    dropped = [c.ticker for c in candidate_stocks if c.ticker.upper() in excluded]
    return kept, dropped
