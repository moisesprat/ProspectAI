"""Flow-built market corpus and the merge with the LLM's picks (CORR-10, D-13, D-14).

The Market Analyst used to call Reddit, decide whether to fall back to Serper
(on Haiku 5.5 it never did, so tickers came from model memory, REBASELINE item 9),
copy Reddit's numbers, invent ``mention_count=0`` and ``relevance_score=0.5`` on
fallback, type a sentiment score from snippet tone, and write the timestamp and a
``data_source`` field the schema does not have. Now the Flow calls both tools itself
(utils/flow_tools.py), this module turns their output into one *corpus*, and the LLM
only chooses up to five tickers from that corpus and writes a rationale for each plus a
summary (``MarketNarrativeOutput``). ``merge_market`` joins the picks with numbers the
Flow measured into the published ``MarketAnalysisOutput``. Nothing the LLM answers can
reach a number, a flag or the timestamp.

Three paths, chosen by what the tools returned (``source`` of the corpus):

    reddit       Reddit returned candidates and did not ask for fallback. The LLM may
                 only pick listed tickers (a pick outside the list has no measured
                 data: it is dropped with a warning, and if none remain the phase
                 answer is a validation failure that spends the retry budget).
                 mention_count, average_sentiment and relevance_score are Reddit's.
    serper       Reddit asked for fallback and the fixed Serper query returned usable
                 results. mention_count is the number of times the ticker symbol
                 appears in the result titles and snippets (the Reddit tool's own
                 matching rule, see ``symbol_mention_counts``); relevance_score is that
                 count divided by the largest count among the published picks, rounded
                 to 2 decimals, null when the largest count is 0. Sentiment comes from
                 ``serper_sentiment_by_ticker`` (below).
    unavailable  Neither source produced data. mention_count, relevance_score and
                 average_sentiment are null, sentiment_available is false, and the LLM
                 picks from the sector's static universe when one is known. Absence of
                 data is null, never 0 and never 0.5.

Serper-path sentiment (operator decision A, plan 02-16 task 1). A tone score typed by
the LLM from search snippets is a number the LLM produced, which the project rule
forbids (CLAUDE.md, ROADMAP SC7). So on the Serper path ``average_sentiment`` is null
and ``sentiment_available`` is false; the composite score then renormalises over the
technical and fundamental components (an existing, tested path). The decision lives in
one small function, ``serper_sentiment_by_ticker``, so a later classifier (planted seed
SEED-261030-nun: TypeSafe "Jev", or a self-hosted finance sentiment model) can fill it
in without touching the rest of the market phase. Today it returns None for every
ticker. ``sentiment_available`` is true only when every published candidate has a
measured sentiment.

Text from Reddit and Serper is untrusted (prompt injection): the corpus the LLM reads
is capped (a few posts or snippets, bounded length, link host only), and the LLM has no
tool and no number field.

Grounding (change 02-23, review CR-01). A pick is published only if it is well formed
(``utils.ticker_matching.is_valid_ticker``) and traceable to the data the model saw:

    reddit       the ticker is one of the listed candidates
    serper       the symbol appears in the result text by the same rule that produces
                 ``mention_count`` (``symbol_mention_counts``), so a pick always has a
                 count of at least 1, and a false positive (a common word) can neither be
                 a pick nor set the largest count that normalises relevance
    unavailable  the ticker is in the sector universe when that is non-empty; with no
                 universe only the format check applies

A pick that fails is dropped with a warning that carries the reason and the ticker cut to
20 characters shown with its repr, never corpus text. When none is left the phase answer is
a validation failure that spends the bounded retry budget; the retry feedback is fixed text
per source. What this does not prove: a symbol present in the text is not shown to be a
real listed company. That check stays Phase 4 (CORR-06).

``require_market_picks`` is the ``validate=`` callback for
``utils.phase_runner.run_phase``.
"""
import json
import logging
import math
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from schemas.agent_outputs import CandidateStock, MarketAnalysisOutput, MarketNarrativeOutput
from utils.phase_runner import PhaseOutputError
from utils.reddit_sentiment_tool import RedditSentimentTool
from utils.ticker_matching import is_valid_ticker, symbol_pattern

logger = logging.getLogger(__name__)

PHASE = "market_analysis"

# Tool names the Flow looks up in TaskFactory (the Serper name is the crewai tool's own).
REDDIT_TOOL_NAME = "analyze_sector_reddit_sentiment"
SERPER_TOOL_NAME = "Search the internet with Serper"

# Bounds on untrusted text that reaches the prompt.
MAX_SNIPPETS = 10
SNIPPET_CHARS = 500
MAX_SAMPLE_POSTS = 3
SAMPLE_POST_CHARS = 200


def serper_query(sector: str, today: str) -> str:
    """The fixed Serper query for the fallback search."""
    return f"{sector} sector stocks investors discussing {today}"


# ── Small sanitizers: anything unusable is None, never a default ───────────────

def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _ranged(value: Any, low: float, high: float) -> Optional[float]:
    number = _finite(value)
    return number if number is not None and low <= number <= high else None


def _count(value: Any) -> Optional[int]:
    number = _finite(value)
    if number is None or number < 0 or number != int(number):
        return None
    return int(number)


def _ticker(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


# ── Corpus ─────────────────────────────────────────────────────────────────────

def reddit_fallback_required(reddit_result: Any) -> bool:
    """True when the Flow must ask Serper: Reddit flagged fallback or gave no usable candidate."""
    if not isinstance(reddit_result, dict) or reddit_result.get("fallback_required"):
        return True
    return not _reddit_candidates(reddit_result)


def _reddit_candidates(reddit_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = reddit_result.get("candidate_stocks")
    if not isinstance(raw, list):
        return []
    out: Dict[str, Dict[str, Any]] = {}
    for item in raw:
        ticker = _ticker(item.get("ticker")) if isinstance(item, dict) else ""
        if not ticker or ticker in out:
            continue
        posts = item.get("sample_posts")
        out[ticker] = {
            "ticker": ticker,
            "mention_count": _count(item.get("mention_count")),
            "average_sentiment": _ranged(item.get("average_sentiment"), -1.0, 1.0),
            "relevance_score": _ranged(item.get("relevance_score"), 0.0, 1.0),
            "sample_posts": [
                p[:SAMPLE_POST_CHARS] for p in (posts if isinstance(posts, list) else []) if isinstance(p, str)
            ][:MAX_SAMPLE_POSTS],
        }
    return list(out.values())


def _serper_snippets(serper_result: Any) -> List[Dict[str, str]]:
    organic = serper_result.get("organic") if isinstance(serper_result, dict) else None
    if not isinstance(organic, list):
        return []
    snippets: List[Dict[str, str]] = []
    for item in organic:
        if not isinstance(item, dict):
            continue
        title = item.get("title") if isinstance(item.get("title"), str) else ""
        snippet = item.get("snippet") if isinstance(item.get("snippet"), str) else ""
        text = f"{title} {snippet}".strip()
        if not text:
            continue
        link = item.get("link")
        try:
            host = (urlparse(link).hostname or "") if isinstance(link, str) else ""
        except ValueError:
            host = ""
        snippets.append({"text": text[:SNIPPET_CHARS], "host": host})
        if len(snippets) >= MAX_SNIPPETS:
            break
    return snippets


def build_market_corpus(reddit_result: Any, serper_result: Any, sector: str) -> Dict[str, Any]:
    """The data the LLM chooses from, with ``source`` in reddit / serper / unavailable.

    reddit:      ``candidates`` (ticker, the three Reddit numbers, up to 3 sample post titles)
    serper:      ``snippets`` (title plus snippet text, link host only)
    unavailable: ``universe``, the sector's static ticker list (empty when unknown)
    """
    if not reddit_fallback_required(reddit_result):
        return {"source": "reddit", "candidates": _reddit_candidates(reddit_result)}
    snippets = _serper_snippets(serper_result)
    if snippets:
        return {"source": "serper", "snippets": snippets}
    return {"source": "unavailable", "universe": list(RedditSentimentTool.SECTOR_TICKERS.get(sector, []))}


def market_narrative_context(corpus: Dict[str, Any]) -> str:
    """JSON the LLM reads. The numbers may be cited in prose; they cannot be changed."""
    source = corpus["source"]
    if source == "reddit":
        body: Dict[str, Any] = {
            "candidates": corpus["candidates"],
            "note": "Choose only tickers listed in candidates.",
        }
    elif source == "serper":
        body = {
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
                "No Reddit or search data was available this run. "
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

    Operator decision A (plan 02-16): no sentiment is measured on the Serper path, so
    every ticker maps to None. This is the single plug-in point for a future classifier
    (SEED-261030-nun): return a score for the tickers it can classify and None for the
    rest. Do not return 0.0 for "unknown". The LLM must not be the source of the score.
    """
    return {_ticker(t): None for t in tickers if _ticker(t)}


# ── Picks ──────────────────────────────────────────────────────────────────────

_SOURCE_HINTS = {
    "reddit": "choose tickers from the listed candidates only; a ticker is 1 to 5 capital letters",
    "serper": (
        "choose only tickers whose symbol itself appears in the search results; "
        "a ticker is 1 to 5 capital letters"
    ),
    "universe": "choose tickers from the listed universe only; a ticker is 1 to 5 capital letters",
    "open": "choose well-formed tickers: 1 to 5 capital letters",
}


def _picks(
    narrative: Optional[MarketNarrativeOutput], corpus: Dict[str, Any]
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """(kept picks as (TICKER, rationale), dropped picks as (ticker, reason)), in the LLM's order, de-duplicated.

    Every pick is checked in this order: the format check (all sources), then the source
    rule. Reasons are a closed set: invalid_format, not_in_reddit_candidates,
    not_in_search_results, not_in_sector_universe.
    """
    source = corpus["source"]
    items = narrative.candidates if narrative is not None else []
    tickers = [_ticker(item.ticker) for item in items]
    listed = {c["ticker"] for c in corpus.get("candidates", [])} if source == "reddit" else set()
    universe = set(corpus.get("universe", [])) if source == "unavailable" else set()
    counts: Dict[str, int] = {}
    if source == "serper":
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
        elif source == "reddit" and ticker not in listed:
            dropped[ticker] = "not_in_reddit_candidates"
        elif source == "serper" and counts.get(ticker, 0) <= 0:
            dropped[ticker] = "not_in_search_results"
        elif source == "unavailable" and universe and ticker not in universe:
            dropped[ticker] = "not_in_sector_universe"
        else:
            kept[ticker] = item.rationale
    return list(kept.items()), list(dropped.items())


def _log_dropped(dropped: List[Tuple[str, str]]) -> None:
    """One warning per dropped pick: the phase, the reason and the ticker cut to 20 characters (repr).

    The ticker is model output, so it is cut and escaped before it reaches a log line; corpus
    text is never logged.
    """
    for ticker, reason in dropped:
        logger.warning("%s: pick dropped (%s): %s", PHASE, reason, repr(ticker[:20]))


def _no_picks_error(corpus: Dict[str, Any], dropped: List[Tuple[str, str]]) -> PhaseOutputError:
    """The shared failure when no pick can be published: fixed text per source, no ticker, no corpus text."""
    _log_dropped(dropped)
    source = corpus["source"]
    if source == "unavailable":
        hint = _SOURCE_HINTS["universe" if corpus.get("universe") else "open"]
    else:
        hint = _SOURCE_HINTS[source]
    message = f"{PHASE}: no chosen ticker is well formed and grounded in the data; fields: candidates"
    return PhaseOutputError(message, ["candidates"], [{"loc": ("candidates",), "msg": hint}])


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
    _log_dropped(dropped)
    tickers = [t for t, _ in kept]

    source = corpus["source"]
    mentions: Dict[str, Optional[int]] = {t: None for t in tickers}
    relevance: Dict[str, Optional[float]] = {t: None for t in tickers}
    sentiment: Dict[str, Optional[float]] = {t: None for t in tickers}

    if source == "reddit":
        measured = {c["ticker"]: c for c in corpus["candidates"]}
        for t in tickers:
            mentions[t] = measured[t]["mention_count"]
            relevance[t] = measured[t]["relevance_score"]
            sentiment[t] = measured[t]["average_sentiment"]
    elif source == "serper":
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
