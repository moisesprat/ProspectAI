"""Flow-built market corpus and the merge with the LLM's picks (CORR-10, D-13, D-14).

The Market Analyst used to choose its own tool calls, copy tool numbers, invent
``mention_count=0`` and ``relevance_score=0.5``, type a sentiment score from snippet tone,
and write the timestamp and a ``data_source`` field the schema does not have. Now the Flow
calls the search tool itself (utils/flow_tools.py), this module turns its output into one
*corpus*, and the LLM only chooses up to five tickers from that corpus and writes a
rationale for each plus a summary (``MarketNarrativeOutput``). ``merge_market`` joins the
picks with numbers the Flow measured into the published ``MarketAnalysisOutput``. Nothing
the LLM answers can reach a number, a flag or the timestamp.

Candidate discovery is Serper only (change sentiment-source-replacement, D-04, D-05). Two
paths, chosen by what the search returned (``source`` of the corpus):

    serper       The Flow ran the three fixed Serper queries and they returned usable
                 results (merged, de-duplicated and bounded, see below). mention_count is
                 the number of times the ticker symbol appears in the result titles and
                 snippets (``symbol_mention_counts``); relevance_score is that count
                 divided by the largest count among the published picks, rounded to 2
                 decimals, null when the largest count is 0. Sentiment comes from
                 ``serper_sentiment_by_ticker`` (below).
    unavailable  Search produced no data. mention_count, relevance_score and
                 average_sentiment are null, sentiment_available is false, and the LLM
                 picks from the sector's static universe when one is known. Absence of
                 data is null, never 0 and never 0.5.

Serper-path sentiment (phase 3.1, D-04, D-08, D-09, D-10). A tone score typed by the LLM from
search snippets is a number the LLM produced, which the project rule forbids (CLAUDE.md,
ROADMAP SC7); operator decision A (plan 02-16) therefore left ``average_sentiment`` null on
this path, and ``sentiment_available`` was false in every run. Decision A is superseded by the
news provider's own per-ticker score (``utils.news_sentiment``): after the LLM has chosen, the
Flow looks the grounded picks up through a Flow-owned tool and stores the mapped scores in
``corpus["news_sentiment"]``. The one function that reads them is ``serper_sentiment_by_ticker``
(below); a pick with no usable score keeps ``average_sentiment`` null, never 0.0, and
``sentiment_available`` is true only when every published candidate has a measured sentiment
(all or none, so the composite never mixes scored and unscored picks). SEED-261030-nun (a
snippet classifier) stays deferred. When the lookup is skipped or fails every score is null and
the composite renormalises over the technical and fundamental components (an existing, tested
path).

Search text is untrusted (prompt injection): the corpus the LLM reads is capped (a few
snippets, bounded length, link host only), and the LLM has no tool and no number field.

Search and corpus bounds (change 02-23, G2/G3). The Flow runs three fixed Serper queries one
after another (``serper_queries``; the model never picks a query). The queries use a plain sector
phrase instead of the SPA label and the third names four curated symbols of the sector, so on-sector
tickers reach the corpus (phase 4.1 D-14); the corpus caps below are unchanged. Their organic results are
merged rank by rank across the queries (rank 1 of each, then rank 2 of each, ...), a repeated
link is removed (an entry with no link repeats when its text repeats), full URLs are scrubbed
from the text, and the corpus stops at ``MAX_SNIPPETS`` (20) results of at most
``SNIPPET_CHARS`` (300) characters and ``MAX_CORPUS_TEXT_CHARS`` (6000) characters in total;
the link host is cut to ``MAX_HOST_CHARS`` (253, the DNS hostname maximum; phase 4 CORR-09).
``corpus_record`` is the stored view: what the model saw, host only, cut to
``MAX_RECORD_BYTES`` (8192) so it can be kept in the run's public execution metrics.

Grounding (change 02-23, review CR-01). A pick is published only if it is well formed
(``utils.ticker_matching.is_valid_ticker``) and traceable to the data the model saw:

    serper       the symbol appears in the result text by the same rule that produces
                 ``mention_count`` (``symbol_mention_counts``), so a pick always has a
                 count of at least 1, and a false positive (a common word) can neither be
                 a pick nor set the largest count that normalises relevance
    unavailable  the ticker is in the sector universe when that is non-empty; with no
                 universe only the format check applies

Sector-benchmark and broad-market ETFs (``utils.candidate_universe_filter``) are dropped
here too, after the source rule and with the reason ``excluded_etf``: before the retry
decision, so an ETF-only answer spends the retry budget instead of leaving the phase with
an empty candidate list, and before relevance is scaled, so an ETF can never set the
largest count (gap review WR-01). The Flow's later ``filter_candidates`` call stays as a
backstop.

Sector membership (phase 4.1 D-07, D-09). On the serper path only, a pick that passes the three
checks above can still be dropped with the reason ``not_in_sector``: its yfinance sector and
industry prove it is outside the requested sector (``utils.sector_membership``). That check does
network I/O, so it is a separate async step that runs before the retry decision and stores its
verdicts in ``corpus["sector_check"]`` (``SECTOR_CHECK_KEY``); ``_picks`` stays pure and offline
and only reads that memo. With no memo (the check did not run) ``_picks`` behaves exactly as before.
Picks in the curated list of the requested sector are exempt (verdict curated, no lookup), a verdict
is read from the memo and never fetched here, so this module stays pure and offline, and
a failed lookup keeps the pick: only proof from the yfinance labels drops one. The retry feedback for the
serper path ends with the fixed sentence "the company must belong to the requested sector" (the hint is
kept short enough that the 200-character cap of ``utils.phase_runner.feedback_from`` does not cut it), so a
model whose picks were all set aside is told the rule without being shown a ticker or any search text.

The closed set of dropped-pick reasons is invalid_format, not_in_search_results,
not_in_sector_universe, excluded_etf, not_in_sector. A pick that fails is dropped with a warning that
carries the reason and the ticker cut to 20 characters shown with its repr, never corpus
text. When none is left the phase answer is a validation failure that spends the bounded
retry budget; the retry feedback is fixed text per source. After the serper-path budget ends with
none left, the Flow publishes the curated fallback of ``utils.market_fallback`` (phase 4.1 D-13), the
one exception to the rule that an exhausted phase never publishes a substitute; the error that ends
the last attempt is a ``NoPicksError`` so the Flow can tell this case from a schema failure. The rule differs by source: on
the serper path it is format + grounding in the search results + ETF exclusion (the sector
universe is not checked there); on the unavailable path it is format + sector universe +
ETF exclusion. What this does not prove: a symbol present in the text is not shown to be a
real listed company. Per the operator decision narrowing D-03 (phase 4 CORR-06) there is no
listing check here: a symbol yfinance cannot price is excluded by the technical phase
(plan 02-15).

``require_market_picks`` is the synchronous format + grounding check; the Flow's ``validate=``
callback for ``utils.phase_runner.run_phase`` is ``utils.sector_membership.validate_market_picks``,
which runs the sector check first and then calls it.
"""
import json
import logging
import math
import re
from datetime import datetime
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from schemas.agent_outputs import CandidateStock, MarketAnalysisOutput, MarketNarrativeOutput
from utils.candidate_universe_filter import excluded_tickers_for_sector
from utils.phase_runner import PhaseOutputError
from utils.sector_universe import (
    FALLBACK_PICKS, SEARCH_PHRASES, SECTOR_ALIASES, SECTOR_TICKERS, canonical_sector,
)
from utils.ticker_matching import is_valid_ticker, symbol_pattern

logger = logging.getLogger(__name__)

PHASE = "market_analysis"

# The closed set of dropped-pick reasons, in the order the module docstring lists them. The public
# ``execution_metrics.market_fallback`` record counts drops by these names only (phase 4.1 D-13).
DROP_REASONS: Tuple[str, ...] = (
    "invalid_format", "not_in_search_results", "not_in_sector_universe", "excluded_etf", "not_in_sector",
)

# Key of the memo ``utils.sector_membership`` writes into the corpus and ``_picks`` reads
# ({TICKER: {"verdict", "reason", "sector", "industry"}}); phase 4.1 D-07.
SECTOR_CHECK_KEY = "sector_check"

# Tool name the Flow looks up in TaskFactory (the Serper name is the crewai tool's own).
SERPER_TOOL_NAME = "Search the internet with Serper"

# Bounds on untrusted text that reaches the prompt.
MAX_SNIPPETS = 20
SNIPPET_CHARS = 300
MAX_CORPUS_TEXT_CHARS = 6000
MAX_RECORD_BYTES = 8192
# The DNS hostname maximum, so a valid host is never changed. The link host was the one
# Serper-derived string that reached the prompt uncut (phase 4 CORR-09).
MAX_HOST_CHARS = 253

# How many curated symbols the third Serper query names (phase 4.1 D-14).
QUERY_SYMBOLS = 4

_URL = re.compile(r"(?:https?://|www\.)\S*", re.IGNORECASE)


# ── Supported sectors ──────────────────────────────────────────────────────────

# SECTOR_ALIASES (the web app's Financials and Consumer Discretionary) lives in
# utils.sector_universe and is re-exported here; accepted as supported, not remapped (WR-03).
SUPPORTED_SECTORS: FrozenSet[str] = frozenset(SECTOR_TICKERS) | frozenset(SECTOR_ALIASES)


def is_supported_sector(sector: Any) -> bool:
    """True only for a str that is exactly a supported sector name (no case folding, no stripping)."""
    return isinstance(sector, str) and sector in SUPPORTED_SECTORS


def serper_queries(sector: str, today: str) -> List[str]:
    """The three fixed Serper queries of the market search (phase 4.1 D-14).

    The SPA label alone ("Financials sector stocks ...") returned generic market pages that name
    companies in prose and carry almost no on-sector ticker symbols (the 2026-11-13 live runs), so
    the analyst had nothing on-sector to choose from. A supported sector now uses its plain phrase
    from ``SEARCH_PHRASES``, and only the third query also names the first ``QUERY_SYMBOLS`` curated
    symbols of the sector, so most of the corpus stays unbiased. Every query keeps the run date. The
    text comes only from tables in code and the Flow's date, never from the model or the visitor. A
    sector with no phrase keeps the original wording.
    """
    canonical = canonical_sector(sector)
    phrase = SEARCH_PHRASES.get(canonical)
    if phrase is None:
        return [
            f"{sector} sector stocks investors discussing {today}",
            f"{sector} sector stocks to watch analyst picks {today}",
            f"most discussed trending {sector} stocks this week {today}",
        ]
    symbols = " ".join(FALLBACK_PICKS[canonical][:QUERY_SYMBOLS])
    return [
        f"{phrase} stocks investors discussing {today}",
        f"{phrase} stocks to watch analyst picks {today}",
        f"most discussed trending {phrase} stocks {symbols} this week {today}",
    ]


def _scrub(text: str) -> str:
    """Remove full URLs (they can carry tokens and tracking) and collapse the whitespace they leave."""
    return " ".join(_URL.sub(" ", text).split())


# ── Small sanitizers: anything unusable is None, never a default ───────────────

def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _ranged(value: Any, low: float, high: float) -> Optional[float]:
    number = _finite(value)
    return number if number is not None and low <= number <= high else None


def _ticker(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


# ── Corpus ─────────────────────────────────────────────────────────────────────

def _serper_snippets(serper_result: Any) -> List[Dict[str, str]]:
    """The bounded merged corpus: one result dict, or a list of them (a non-dict entry is ignored).

    Each entry is exactly ``{"text", "host"}``. Results are taken rank by rank across the lists,
    a repeated link is dropped (no link: a repeated text is dropped), full URLs are scrubbed from
    the text before it is cut to SNIPPET_CHARS, the link host is cut to MAX_HOST_CHARS, and the
    corpus stops at MAX_SNIPPETS results or when the next one would take the text past
    MAX_CORPUS_TEXT_CHARS.
    """
    results = serper_result if isinstance(serper_result, list) else [serper_result]
    organic_lists = []
    for result in results:
        organic = result.get("organic") if isinstance(result, dict) else None
        if isinstance(organic, list):
            organic_lists.append(organic)

    snippets: List[Dict[str, str]] = []
    seen_links: set = set()
    seen_texts: set = set()
    total = 0
    for rank in range(max((len(o) for o in organic_lists), default=0)):
        for organic in organic_lists:
            item = organic[rank] if rank < len(organic) else None
            if not isinstance(item, dict):
                continue
            title = item.get("title") if isinstance(item.get("title"), str) else ""
            snippet = item.get("snippet") if isinstance(item.get("snippet"), str) else ""
            text = _scrub(f"{title} {snippet}")[:SNIPPET_CHARS]
            if not text:
                continue
            link = item.get("link")
            if isinstance(link, str) and link.strip():
                if link.strip() in seen_links:
                    continue
                seen_links.add(link.strip())
            else:
                if text in seen_texts:
                    continue
                seen_texts.add(text)
            if len(snippets) >= MAX_SNIPPETS or total + len(text) > MAX_CORPUS_TEXT_CHARS:
                return snippets
            try:
                host = (urlparse(link).hostname or "") if isinstance(link, str) else ""
            except ValueError:
                host = ""
            snippets.append({"text": text, "host": host[:MAX_HOST_CHARS]})
            total += len(text)
    return snippets


def build_market_corpus(
    serper_results: Any,
    sector: str,
    queries: Optional[List[str]] = None,
    failed_queries: int = 0,
) -> Dict[str, Any]:
    """The data the LLM chooses from, with ``source`` in serper / unavailable.

    serper:      ``snippets`` (title plus snippet text, link host only) merged from one result or a
                 list of results, plus the ``queries`` that were run and the ``failed_queries`` count
    unavailable: ``universe``, the sector's static ticker list (empty when unknown)

    Every corpus also carries ``sector`` (as given). ``_picks`` uses it for the ETF exclusion;
    it is not shown to the model (``market_narrative_context`` builds its body from explicit
    keys) and is not stored (``corpus_record`` builds its record from explicit keys).
    """
    snippets = _serper_snippets(serper_results)
    if snippets:
        return {
            "source": "serper",
            "sector": sector,
            "snippets": snippets,
            "queries": list(queries or []),
            "failed_queries": failed_queries,
        }
    return {
        "source": "unavailable",
        "sector": sector,
        "universe": list(SECTOR_TICKERS.get(sector, [])),
    }


def corpus_record(corpus: Dict[str, Any]) -> Dict[str, Any]:
    """The JSON-safe record of what the model saw, stored in ``execution_metrics.market_corpus``.

    serper:      source, queries, failed_queries, results (text and host per entry), truncated
    unavailable: source, universe, truncated

    The record never holds a full URL: results carry the link host only with URLs scrubbed from
    the text, and every stored query is scrubbed too (a caller-supplied sector can be a URL). Its size
    is measured as the backend writes it (``json.dumps`` with its defaults, the largest of the
    usual encodings); over ``MAX_RECORD_BYTES`` it drops trailing entries until it fits and sets
    ``truncated``, so the earliest results are the ones kept.
    """
    source = corpus["source"]
    if source == "serper":
        key = "results"
        record: Dict[str, Any] = {
            "source": source,
            "queries": [_scrub(str(q))[:200] for q in corpus.get("queries", [])],
            "failed_queries": int(corpus.get("failed_queries", 0)),
            key: [{"text": s["text"], "host": s["host"]} for s in corpus["snippets"]],
            "truncated": False,
        }
    else:
        key = "universe"
        record = {"source": source, key: list(corpus["universe"]), "truncated": False}
    while record[key] and len(json.dumps(record).encode("utf-8")) > MAX_RECORD_BYTES:
        record[key].pop()
        record["truncated"] = True
    return record


def market_narrative_context(corpus: Dict[str, Any]) -> str:
    """JSON the LLM reads. The numbers may be cited in prose; they cannot be changed."""
    source = corpus["source"]
    if source == "serper":
        body: Dict[str, Any] = {
            "search_results": corpus["snippets"],
            "note": (
                "Choose only tickers whose symbol itself appears in these search results. "
                "A pick whose symbol is not in the results is discarded."
            ),
        }
    else:
        body = {
            "universe": corpus["universe"],
            "note": (
                "No search data was available this run. "
                + (
                    "Choose tickers from universe only; others are discarded."
                    if corpus["universe"]
                    else "Choose well-known companies of the sector; use their real ticker symbols."
                )
            ),
        }
    return json.dumps({"source": source, **body})


# ── Serper-path counts and sentiment ───────────────────────────────────────────

def symbol_mention_counts(tickers: Iterable[str], snippets: Iterable[str]) -> Dict[str, int]:
    """How many times each ticker symbol appears in the snippet texts (0 when never).

    The one counter for the Serper path: it produces ``mention_count`` and decides whether a
    pick is grounded. One-letter and common-word symbols count only in an explicit form
    (a cashtag or an exchange-qualified form), see ``utils.ticker_matching``.
    """
    texts = list(snippets)
    counts: Dict[str, int] = {}
    for ticker in dict.fromkeys(_ticker(t) for t in tickers):
        if not ticker:
            continue
        pattern = symbol_pattern(ticker, guard_ambiguous=True)
        counts[ticker] = sum(len(pattern.findall(text)) for text in texts)
    return counts


def serper_sentiment_by_ticker(corpus: Dict[str, Any], tickers: Iterable[str]) -> Dict[str, Optional[float]]:
    """Per-ticker sentiment in [-1, 1] for the Serper path, or None when unmeasured.

    Reads ``corpus["news_sentiment"]``, the ``{TICKER: score or None}`` map the Flow stored after
    the news lookup (``utils.news_sentiment``, phase 3.1 D-04, D-08). A ticker absent from the
    map, a non-finite or out-of-range value, a non-number and a map that is not a dict are all
    None. Do not return 0.0 for "unknown". The LLM is never the source of the score.
    """
    stored = corpus.get("news_sentiment")
    if not isinstance(stored, dict):
        stored = {}
    return {_ticker(t): _ranged(stored.get(_ticker(t)), -1.0, 1.0) for t in tickers if _ticker(t)}


# ── Picks ──────────────────────────────────────────────────────────────────────

_SOURCE_HINTS = {
    "serper": (
        "choose only tickers whose symbol itself appears in the search results; "
        "a ticker is 1 to 5 capital letters; no sector or broad-market ETFs"
        "; the company must belong to the requested sector"
    ),
    "universe": (
        "choose tickers from the listed universe only; a ticker is 1 to 5 capital letters"
        "; sector and broad-market ETFs are not eligible"
    ),
    "open": "choose well-formed tickers: 1 to 5 capital letters; sector and broad-market ETFs are not eligible",
}


def _sector_verdict(verdicts: Dict[str, Any], ticker: str) -> Optional[str]:
    """The stored sector verdict for ``ticker``, or None when there is no well-formed entry."""
    entry = verdicts.get(ticker)
    return entry.get("verdict") if isinstance(entry, dict) else None


def _picks(
    narrative: Optional[MarketNarrativeOutput], corpus: Dict[str, Any]
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """(kept picks as (TICKER, rationale), dropped picks as (ticker, reason)), in the LLM's order, de-duplicated.

    Every pick is checked in this order: the format check (all sources), then the source
    rule, then the ETF exclusion (so an ungrounded ETF keeps its source reason), then, on the
    serper path only, the sector verdict ``utils.sector_membership`` stored in the corpus memo
    (read here, never computed: no I/O). Reasons are a closed set: invalid_format,
    not_in_search_results, not_in_sector_universe, excluded_etf, not_in_sector.
    """
    source = corpus["source"]
    excluded = excluded_tickers_for_sector(corpus.get("sector", ""))
    items = narrative.candidates if narrative is not None else []
    tickers = [_ticker(item.ticker) for item in items]
    universe = set(corpus.get("universe", [])) if source == "unavailable" else set()
    counts: Dict[str, int] = {}
    verdicts: Dict[str, Any] = {}
    if source == "serper":
        memo = corpus.get(SECTOR_CHECK_KEY)
        verdicts = memo if isinstance(memo, dict) else {}
        counts = symbol_mention_counts(
            [t for t in tickers if is_valid_ticker(t)], [s["text"] for s in corpus["snippets"]]
        )

    kept: Dict[str, str] = {}
    dropped: Dict[str, str] = {}
    for item, ticker in zip(items, tickers):
        if ticker in kept or ticker in dropped:
            continue
        if not is_valid_ticker(ticker):
            dropped[ticker] = "invalid_format"
        elif source == "serper" and counts.get(ticker, 0) <= 0:
            dropped[ticker] = "not_in_search_results"
        elif source == "unavailable" and universe and ticker not in universe:
            dropped[ticker] = "not_in_sector_universe"
        elif ticker in excluded:
            dropped[ticker] = "excluded_etf"
        elif _sector_verdict(verdicts, ticker) == "not_in_sector":
            dropped[ticker] = "not_in_sector"
        else:
            kept[ticker] = item.rationale
    return list(kept.items()), list(dropped.items())


def grounded_picks(narrative: Optional[MarketNarrativeOutput], corpus: Dict[str, Any]) -> List[str]:
    """The tickers ``merge_market`` would publish, in the LLM's order (the kept picks of ``_picks``)."""
    return [ticker for ticker, _ in _picks(narrative, corpus)[0]]


def _log_dropped(dropped: List[Tuple[str, str]], corpus: Optional[Dict[str, Any]] = None) -> None:
    """One warning per dropped pick: the phase, the reason and the ticker cut to 20 characters (repr).

    The ticker is model output, so it is cut and escaped before it reaches a log line; corpus
    text is never logged. A ``not_in_sector`` line adds the yfinance sector and industry from the
    memo (already cut to 40 characters, third-party strings, so repr-escaped; None when absent).
    """
    memo = corpus.get(SECTOR_CHECK_KEY) if corpus is not None else None
    memo = memo if isinstance(memo, dict) else {}
    for ticker, reason in dropped:
        if reason == "not_in_sector":
            entry = memo.get(ticker)
            entry = entry if isinstance(entry, dict) else {}
            logger.warning(
                "%s: pick dropped (%s): %s; yfinance sector %s, industry %s",
                PHASE, reason, repr(ticker[:20]), repr(entry.get("sector")), repr(entry.get("industry")),
            )
        else:
            logger.warning("%s: pick dropped (%s): %s", PHASE, reason, repr(ticker[:20]))


class NoPicksError(PhaseOutputError):
    """No chosen pick can be published (phase 4.1 D-13).

    A PhaseOutputError like any other, so the bounded retry treats it the same. ``dropped`` holds
    the (ticker, reason) pairs of the answer that failed: model output, so it stays inside this
    exception object and is never serialised or logged by the type.
    """

    def __init__(
        self, message: str, fields: List[str], errors: List[Dict[str, Any]],
        dropped: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        super().__init__(message, fields, errors)
        self.dropped: List[Tuple[str, str]] = list(dropped or [])


def _no_picks_error(corpus: Dict[str, Any], dropped: List[Tuple[str, str]]) -> NoPicksError:
    """The shared failure when no pick can be published: fixed text per source, no ticker, no corpus text."""
    _log_dropped(dropped, corpus)
    source = corpus["source"]
    if source == "unavailable":
        hint = _SOURCE_HINTS["universe" if corpus.get("universe") else "open"]
    else:
        hint = _SOURCE_HINTS[source]
    message = f"{PHASE}: no chosen ticker is well formed and grounded in the data; fields: candidates"
    return NoPicksError(message, ["candidates"], [{"loc": ("candidates",), "msg": hint}], dropped)


def require_market_picks(narrative: Optional[MarketNarrativeOutput], corpus: Dict[str, Any]) -> None:
    """Raise PhaseOutputError naming ``candidates`` when no pick can be published.

    On every source a pick must be well formed and grounded (see the module docstring), so an
    answer that leaves none spends the bounded retry budget. Dropped picks are logged only
    when this raises; ``merge_market`` logs them once when the phase succeeds.
    """
    kept, dropped = _picks(narrative, corpus)
    if not kept:
        raise _no_picks_error(corpus, dropped)


def merge_market(
    sector: str,
    corpus: Dict[str, Any],
    narrative: MarketNarrativeOutput,
    now_utc: datetime,
) -> MarketAnalysisOutput:
    """Published output: the LLM's picks and rationales plus numbers the Flow measured.

    Picks that are not well formed or not grounded in the corpus are dropped with a warning
    (no measured data for them); none left raises through the same shared error as
    ``require_market_picks``. ``now_utc`` is the analysis timestamp, set by the Flow.
    """
    kept, dropped = _picks(narrative, corpus)
    if not kept:
        raise _no_picks_error(corpus, dropped)
    _log_dropped(dropped, corpus)
    tickers = [t for t, _ in kept]

    source = corpus["source"]
    mentions: Dict[str, Optional[int]] = {t: None for t in tickers}
    relevance: Dict[str, Optional[float]] = {t: None for t in tickers}
    sentiment: Dict[str, Optional[float]] = {t: None for t in tickers}

    if source == "serper":
        counts = symbol_mention_counts(tickers, [s["text"] for s in corpus["snippets"]])
        largest = max(counts.values(), default=0)
        scores = serper_sentiment_by_ticker(corpus, tickers)
        for t in tickers:
            mentions[t] = counts[t]
            relevance[t] = round(counts[t] / largest, 2) if largest > 0 else None
            sentiment[t] = _ranged(scores.get(t), -1.0, 1.0)

    candidates = [
        CandidateStock(
            ticker=t,
            mention_count=mentions[t],
            average_sentiment=sentiment[t],
            relevance_score=relevance[t],
            rationale=rationale,
        )
        for t, rationale in kept
    ]
    return MarketAnalysisOutput(
        sector=sector,
        candidate_stocks=candidates,
        summary=narrative.summary,
        analysis_timestamp=now_utc,
        sentiment_available=all(c.average_sentiment is not None for c in candidates),
    )
