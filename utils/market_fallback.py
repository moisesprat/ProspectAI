"""Curated fallback for the market step when the web search leaves no usable pick (phase 4.1 D-13).

Origin. Two live Financials runs on prospectai 1.13.2 (2026-11-13) failed with "market_analysis:
output failed schema validation after 3 attempts; fields: candidates". The sector check worked, but
the three queries returned generic market pages that name companies in prose and carry almost no
finance ticker symbols, so every pick the analyst made was dropped (not_in_sector in one run,
not_in_search_results in the other) and the earlier rule (D-11: retry, then fail, no backfill) ended a
visitor-facing run with an error. The core value is that a visitor gets a correct, schema-valid
report, so D-13 revises D-11 for the Serper path.

What stays and what is reversed. The bounded retry with its fixed sector feedback stands unchanged.
The clause "then fail with a clear error, no backfill" is reversed for the Serper path only.

Trigger (``is_zero_survivor_failure``). The market phase raised a ``PhaseSchemaError`` whose last
attempt ended with zero surviving picks (its cause is a ``utils.market_records.NoPicksError``), the
corpus source is serper and the sector has a curated table. Any drop reason counts. Only zero
survivors trigger it: when any pick survives it is published alone, with no top-up from the curated
list (mixing model and curated picks would blur which ones the search grounded). A last attempt that
fails the schema for another reason (for example a short summary), the unavailable path and the open
path still fail as before: the fallback exists for an unusable search corpus, not for an unusable
model answer.

Content (``fallback_market_output``). The five curated stocks of ``FALLBACK_PICKS`` for the sector
(``utils.sector_universe``), which are also in the sector's curated list, so the sector check would
exempt them (D-03). Nothing here calls the LLM and no number comes from it: mention_count,
relevance_score and average_sentiment are null, sentiment_available is false, the Flow runs no news
lookup (the composite renormalises over the technical and fundamental components, the existing path
of the unavailable source), and the rationale and summary are fixed text built from the sector name
and the symbol only, with no digit. The text says the stocks come from a curated list and were not
found in the web search; the LLM still chooses only the action, later (D-12).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from schemas.agent_outputs import CandidateStock, MarketAnalysisOutput
from utils.market_records import PHASE, NoPicksError
from utils.phase_runner import PhaseSchemaError
from utils.sector_universe import FALLBACK_PICKS, canonical_sector

logger = logging.getLogger(__name__)

FALLBACK_REASON = "no_surviving_picks"

_RATIONALE = (
    "{ticker} is one of the well-known {sector} stocks the pipeline keeps as a curated list for runs "
    "where the web search finds no stock it can confirm in the sector. It was not found in the web "
    "search, so no search mention count, relevance or news sentiment is shown for it; the technical "
    "and fundamental steps score it with measured data."
)
_SUMMARY = (
    "None of the stocks chosen from the web search for the {sector} sector could be confirmed as part "
    "of that sector, so this analysis starts from a curated list of well-known {sector} stocks instead "
    "of search results. The list does not reflect current search coverage: mention counts, relevance "
    "and news sentiment are not available for these stocks, and every later step uses measured market "
    "data only."
)


def fallback_tickers(sector: str) -> list[str]:
    """The curated fallback tickers of ``sector`` (the SPA aliases resolve), empty when it has no table."""
    return list(FALLBACK_PICKS.get(canonical_sector(sector), ()))


def is_zero_survivor_failure(exc: BaseException, corpus: dict[str, Any]) -> bool:
    """True when ``exc`` is the market phase's exhausted retry budget that ended with zero surviving picks.

    The cause of the PhaseSchemaError is the LAST attempt's failure (``utils.phase_runner.run_phase``),
    so a last attempt that failed the schema for another reason is not a zero-survivor failure.
    """
    return (
        isinstance(exc, PhaseSchemaError)
        and exc.phase == PHASE
        and isinstance(exc.__cause__, NoPicksError)
        and corpus.get("source") == "serper"
        and bool(fallback_tickers(corpus.get("sector", "")))
    )


def fallback_market_output(sector: str, now_utc: datetime) -> MarketAnalysisOutput:
    """The published market output built from the curated list of ``sector``: null numbers, fixed text.

    Raises ValueError when the sector has no table; the Flow calls it only after the rule above.
    """
    tickers = fallback_tickers(sector)
    if not tickers:
        raise ValueError("no curated fallback for this sector")
    candidates = [
        CandidateStock(
            ticker=ticker,
            mention_count=None,
            average_sentiment=None,
            relevance_score=None,
            rationale=_RATIONALE.format(ticker=ticker, sector=sector),
        )
        for ticker in tickers
    ]
    return MarketAnalysisOutput(
        sector=sector,
        candidate_stocks=candidates,
        summary=_SUMMARY.format(sector=sector),
        analysis_timestamp=now_utc,
        sentiment_available=False,
    )
