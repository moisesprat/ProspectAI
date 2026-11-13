"""
Sector-membership check on search-grounded market picks (phase 4.1).

Origin. A live Financials run published AAPL (04-VERIFICATION, decisions_for_operator). On the
Serper path a pick is grounded only by a symbol mention in a search snippet, and the Phase 4
operator decision narrowing CORR-06 D-03 left that path with format + grounding + ETF checks
and no sector check, so a snippet that names AAPL next to JPM was enough. This module adds the
missing check without calling the LLM for any fact: a pick is published only if its yfinance
sector OR industry belongs to the requested sector (``utils.sector_universe.SECTOR_MEMBERSHIP``,
hand-written, never derived at runtime).

Scope (D-07). Serper path only, and only for a sector that has an entry in the map once the SPA
aliases are resolved (``canonical_sector``: Financials is Finance). The unavailable and open
paths are untouched. The check is a separate step run inside the market phase's ``validate``
callback (``validate_market_picks``), before the technical and fundamental phases.

Curated short-circuit (D-03). A pick in the curated ``SECTOR_TICKERS`` list of the requested,
alias-resolved sector is kept with no lookup: the curated lists contain names whose Yahoo
labels sit outside the map (GOOGL, AMZN and TSLA under Technology, BRK.B under Finance).

The memo and why ``_picks`` stays pure. The verdicts are written to ``corpus["sector_check"]``
({TICKER: {"verdict", "reason", "sector", "industry"}}); ``utils.market_records._picks`` only
reads that memo, does no I/O and behaves exactly as before when the memo is absent. Every
outcome, timeouts included, is memoised, so the up-to-3 market attempts and the three
``_picks`` callers never pay for a lookup twice. A verdict is one of: curated, member,
not_in_sector, skipped.

Fail open, no invented values (D-04, D-05). Non-membership needs proof: ``not_in_sector`` only
when at least one label is present and every non-empty accepted set of the sector has its
label present. Both labels missing, a missing label the sector needs, an empty or failed
lookup and a lookup that did not finish in the budget are all ``skipped`` and the pick is kept.
Absence is None, never a placeholder. A skip is logged by reason and exception class name only,
never the exception message.

Retry (D-06). ``lookup_sector`` retries a failed lookup exactly once on the same worker: an
exception directly, an empty (None, {}, non-dict) answer after ``yfinance_cache.forget_info``
evicted the cached empty entry; an answer with both labels missing is never retried. Matrix
(first outcome -> retry -> verdict -> log): ok -> never -> member / not_in_sector or skipped
no_sector_data -> WARNING only for the skip; exception -> yes -> skipped lookup_error after a
second failure, WARNING with the class name; empty -> yes, after forget_info -> skipped empty_info
after a second failure, WARNING.

Blocking I/O never runs on the event loop (STALL-02). Lookups run in a dedicated 5-worker
thread pool under one run-level budget (``SECTOR_CHECK_BUDGET_SEC``), the pool is shut down
with ``wait=False, cancel_futures=True`` so a hung Yahoo call never holds the Flow past the
budget, and each task runs in its own copy of the run's context so ``yfinance_cache.get_info``
fills the run's cache and the fundamentals phase reuses the cached info.

Security. Only survivors of ``_picks`` (validated symbol format, grounded, not an ETF) reach
``get_info``; no snippet text or link is used. Yahoo labels are third-party strings: they are
cut to 40 characters and the drop line (``utils.market_records``) repr-escapes them.

The check emits no SSE step and no new event (no SSE contract change); the drop and skip lines
are logs.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from schemas.agent_outputs import MarketNarrativeOutput
from utils import yfinance_cache
from utils.market_records import PHASE, SECTOR_CHECK_KEY, grounded_picks, require_market_picks
from utils.sector_universe import SECTOR_MEMBERSHIP, SECTOR_TICKERS, canonical_sector

logger = logging.getLogger(__name__)

SECTOR_CHECK_BUDGET_SEC = 15.0
SECTOR_CHECK_WORKERS = 5
FIELD_CHARS = 40
# Corpus key holding the seconds the run has already spent on lookups (the budget is run-level).
SPENT_KEY = "sector_check_spent_sec"


def _clean(label: object) -> str | None:
    """A label counts only if it is a non-empty str after ``strip()``."""
    if not isinstance(label, str):
        return None
    return label.strip() or None


def classify(canonical: str, sector: object, industry: object) -> str:
    """member, not_in_sector or unchecked for one pick's yfinance labels under sector ``canonical``.

    member: the sector is in the accepted sectors or the industry is in the accepted industries.
    not_in_sector: at least one label is present and every non-empty accepted set has its label
    present (the labels present prove the pick is outside). Otherwise unchecked, including an
    unmapped sector.
    """
    accepted = SECTOR_MEMBERSHIP.get(canonical)
    if accepted is None:
        return "unchecked"
    sectors, industries = accepted
    sec, ind = _clean(sector), _clean(industry)
    if (sec is not None and sec in sectors) or (ind is not None and ind in industries):
        return "member"
    if sec is None and ind is None:
        return "unchecked"
    if (sectors and sec is None) or (industries and ind is None):
        return "unchecked"
    return "not_in_sector"


def _attempt(ticker: str) -> dict:
    """One ``get_info`` call turned into an outcome dict; never raises."""
    try:
        info = yfinance_cache.get_info(ticker)
    except Exception as exc:
        return {"status": "error", "reason": "lookup_error", "error": type(exc).__name__}
    if not isinstance(info, dict) or not info:
        return {"status": "error", "reason": "empty_info"}
    return {"status": "ok", "sector": info.get("sector"), "industry": info.get("industry")}


def lookup_sector(ticker: str) -> dict:
    """Look up one ticker's yfinance labels with at most one retry; never raises.

    Fail-open matrix (D-04, D-05, D-06). At most two ``get_info`` calls, on the same worker thread,
    no sleep between them (the retry runs inside the same run budget, D-08):

    ==============================  ===============  =====================  ==========================
    first call                      retry            final outcome          verdict, log line
    ==============================  ===============  =====================  ==========================
    non-empty dict                  never            ok (labels as given)   member / not_in_sector, or
                                                                            skipped no_sector_data when
                                                                            both labels are missing
    exception                       yes              second call's outcome  skipped lookup_error, WARNING
                                                                            with the class name only
    None, {} or a non-dict          yes, after       second call's outcome  skipped empty_info, WARNING
                                    ``forget_info``
    ==============================  ===============  =====================  ==========================

    A non-empty dict is final, including one whose labels are both missing (assumption A5: it is
    stable across runs, so a retry cannot help). The first empty answer is forgotten so the retry
    really fetches; a second empty answer stays cached so the fundamentals phase does not refetch.
    The exception message is never logged or stored: only ``type(exc).__name__``.

    Returns ``{"status": "ok", "sector", "industry"}`` (raw ``info.get`` values) or
    ``{"status": "error", "reason": "empty_info" | "lookup_error", "error"?: <class name>}``.
    """
    outcome = _attempt(ticker)
    if outcome["status"] == "ok":
        return outcome
    if outcome["reason"] == "empty_info":
        yfinance_cache.forget_info(ticker)
    return _attempt(ticker)


def _field(label: object) -> str | None:
    """A Yahoo label for the memo: a str cut to ``FIELD_CHARS``, else None."""
    cleaned = _clean(label)
    return cleaned[:FIELD_CHARS] if cleaned is not None else None


def _entry(verdict: str, reason: str, sector: str | None = None, industry: str | None = None) -> dict:
    return {"verdict": verdict, "reason": reason, "sector": sector, "industry": industry}


def _skip(memo: dict, ticker: str, reason: str, error: str | None = None) -> None:
    """Memoise a skipped (kept, unchecked) pick and log it once, by reason and class name only."""
    memo[ticker] = _entry("skipped", reason)
    suffix = f"; error {error}" if reason == "lookup_error" and error else ""
    logger.warning("%s: sector_check_skipped (%s): %s%s", PHASE, reason, repr(ticker[:20]), suffix)


def _record(memo: dict, canonical: str, ticker: str, outcome: dict) -> None:
    """Turn one lookup outcome into a memo entry."""
    if outcome.get("status") != "ok":
        _skip(memo, ticker, outcome.get("reason", "lookup_error"), outcome.get("error"))
        return
    sector, industry = outcome.get("sector"), outcome.get("industry")
    verdict = classify(canonical, sector, industry)
    if verdict == "unchecked":
        _skip(memo, ticker, "no_sector_data")
    elif verdict == "member":
        memo[ticker] = _entry("member", "sector_match", _field(sector), _field(industry))
    else:
        memo[ticker] = _entry("not_in_sector", "label_mismatch", _field(sector), _field(industry))


async def _lookup_all(todo: list[str], budget: float) -> tuple[dict[str, dict], float]:
    """Look up ``todo`` in a dedicated pool within ``budget`` seconds; return (outcomes, seconds spent).

    A ticker whose lookup did not finish is absent from the outcomes. Each task runs in its own
    copy of the current context so the run's yfinance cache is shared with the worker thread.
    """
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(
        max_workers=min(SECTOR_CHECK_WORKERS, len(todo)), thread_name_prefix="sector-check"
    )
    started = time.monotonic()
    pending: set = set()
    futures: dict[Any, str] = {}
    outcomes: dict[str, dict] = {}
    try:
        for ticker in todo:
            future = loop.run_in_executor(pool, contextvars.copy_context().run, lookup_sector, ticker)
            futures[future] = ticker
        done, pending = await asyncio.wait(list(futures), timeout=budget)
        for future in done:
            try:
                outcomes[futures[future]] = future.result()
            except Exception as exc:
                outcomes[futures[future]] = {
                    "status": "error", "reason": "lookup_error", "error": type(exc).__name__,
                }
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
    spent = time.monotonic() - started
    if pending:
        # A timeout means the whole budget is spent, even if the loop's timer fired a clock tick early.
        spent = max(spent, budget)
    return outcomes, spent


async def check_sector_membership(narrative: MarketNarrativeOutput | None, corpus: dict) -> None:
    """Write a sector verdict into ``corpus["sector_check"]`` for each grounded pick not yet in it.

    Returns at once unless the corpus source is serper and the alias-resolved sector has an entry
    in ``SECTOR_MEMBERSHIP``. Curated picks get verdict "curated" with no call; the rest are looked
    up in a dedicated pool under the run-level budget. Never raises: an unexpected failure leaves
    every unresolved pick as skipped (kept).
    """
    if corpus.get("source") != "serper":
        return
    canonical = canonical_sector(corpus.get("sector", ""))
    if canonical not in SECTOR_MEMBERSHIP:
        return
    memo = corpus.setdefault(SECTOR_CHECK_KEY, {})
    curated = set(SECTOR_TICKERS.get(canonical, []))
    todo: list[str] = []
    for ticker in grounded_picks(narrative, corpus):
        if ticker in memo:
            continue
        if ticker in curated:
            memo[ticker] = _entry("curated", "curated_list")
        else:
            todo.append(ticker)
    if not todo:
        return
    try:
        remaining = SECTOR_CHECK_BUDGET_SEC - corpus.get(SPENT_KEY, 0.0)
        if remaining <= 0:
            for ticker in todo:
                _skip(memo, ticker, "timeout")
            return
        outcomes, spent = await _lookup_all(todo, remaining)
        corpus[SPENT_KEY] = corpus.get(SPENT_KEY, 0.0) + spent
        for ticker in todo:
            if ticker in outcomes:
                _record(memo, canonical, ticker, outcomes[ticker])
            else:
                _skip(memo, ticker, "timeout")
    except Exception as exc:
        logger.warning("%s: sector_check failed (%s)", PHASE, type(exc).__name__)
        for ticker in todo:
            if ticker not in memo:
                _skip(memo, ticker, "lookup_error", type(exc).__name__)


async def validate_market_picks(narrative: MarketNarrativeOutput | None, corpus: dict) -> None:
    """The market phase's ``validate`` callback: the sector check (serper only), then the pick check.

    Zero surviving picks raise PhaseOutputError into the bounded retry (utils.phase_runner).
    """
    if corpus.get("source") == "serper":
        await check_sector_membership(narrative, corpus)
    require_market_picks(narrative, corpus)
