"""
Curated sector to ticker universe (the single source of truth for sectors).

Small, curated lists keep ticker matching precise (fewer false-positive symbol
matches) and are ETF-free. Consumers:

- ``utils.market_records.SUPPORTED_SECTORS`` (the sectors a run may start for)
- the unavailable-path universe in ``utils.market_records.build_market_corpus``
- the CLI ``--sector`` choices in ``main.py``
- the ETF filter in ``utils.candidate_universe_filter``

Kept as a standalone module in phase 3.1 so that the universe does not depend on
any one sentiment source (decision D-05). Do not reorder or edit entries
without updating the parity tests in ``tests/test_sector_universe.py``.
"""

from typing import Dict, List

SECTOR_TICKERS: Dict[str, List[str]] = {
    "Technology": [
        "AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN", "TSLA",
        "CRM", "ORCL", "ADBE", "PLTR", "NOW", "SNOW", "ANET",
        "PANW", "CRWD", "NET", "DDOG", "APP", "UBER",
        "EPAM", "INFY", "CTSH", "ACN", "WIT", "IBM", "GLOB", "DXC",
    ],
    "Semiconductors": [
        "NVDA", "AMD", "INTC", "QCOM", "AVGO", "MU", "MRVL", "ALAB",
        "ASML", "TSM", "KLAC", "LRCX", "AMAT", "ARM", "SMCI",
    ],
    "Healthcare": [
        "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO",
        "ABT", "AMGN", "GILD", "ISRG", "MDT", "CVS", "BMY",
        "MRNA", "REGN", "VRTX", "HCA", "CI", "ELV", "DXCM",
        "IDXX", "IQV", "BSX", "SYK", "ZBH", "BIIB", "ILMN",
    ],
    "Finance": [
        "JPM", "BAC", "WFC", "GS", "MS", "BRK.B", "V",
        "MA", "AXP", "C", "SCHW", "BLK", "SPGI", "CB",
        "COF", "USB", "PNC", "TFC", "ICE", "CME", "MCO",
        "FIS", "PYPL", "SQ", "COIN", "HOOD", "SOFI", "NU",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO",
        "MPC", "OXY", "HAL", "DVN", "FANG", "HES", "BKR",
        "WMB", "KMI", "ET", "LNG", "CTRA", "PR", "MRO",
        "APA", "NOV", "CHK", "AR", "RRC", "SM", "MTDR",
    ],
    "Consumer": [
        "WMT", "AMZN", "HD", "NKE", "SBUX", "MCD", "TGT",
        "COST", "LOW", "TJX", "BABA", "PG", "KO", "PEP",
        "TSLA", "F", "GM", "RIVN", "LCID", "CMG", "YUM",
        "DG", "DLTR", "ROST", "EBAY", "ETSY", "DASH", "ABNB",
    ],
    "Industrials": [
        "CAT", "DE", "BA", "HON", "UPS", "LMT", "RTX", "GE",
        "MMM", "EMR", "ITW", "ETN", "PH", "ROK", "FDX", "NSC",
        "UNP", "CSX", "GD", "NOC", "TDG", "CARR", "OTIS", "IR",
        "PCAR", "WM", "RSG", "CTAS", "XYL", "JCI",
    ],
    "Real Estate": [
        "AMT", "PLD", "CCI", "EQIX", "PSA", "WELL", "DLR", "O",
        "SPG", "VICI", "EXR", "AVB", "EQR", "MAA", "UDR", "CPT",
        "ARE", "BXP", "KIM", "REG", "FRT", "NNN", "WPC", "STAG",
        "REXR", "ELS", "SUI", "AMH", "INVH", "VTR",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "AEP", "EXC", "SRE", "D", "PCG",
        "XEL", "ED", "ES", "WEC", "DTE", "ETR", "PPL", "FE",
        "AEE", "LNT", "EVRG", "CMS", "NI", "PNW", "OGE", "AVA",
        "NWE", "BKH", "OTTER", "AWK", "SWX", "ATO",
    ],
}


# Names the web app (prospectai-web ui/data.js SECTORS) and the backend (SECTOR_ETF) use for two
# package sectors. They are accepted as supported sectors but the universe is NOT remapped, so a
# run for them behaves as before (empty unavailable-path universe, Serper path); remapping is a
# separate decision (gap review WR-03 stays open). The ETF filter does resolve them
# (utils.candidate_universe_filter.excluded_tickers_for_sector), so the sector-benchmark ETF is
# excluded under either name (phase 4 CORR-06).
SECTOR_ALIASES: Dict[str, str] = {
    "Financials": "Finance",
    "Consumer Discretionary": "Consumer",
}
