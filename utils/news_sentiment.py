"""News sentiment for the grounded market picks (phase 3.1, D-04, D-06, D-08, D-09, D-10).

The old forum source never produced a sentiment number (9 of 9 baseline runs), so
``sentiment_available`` has been false in every production run since Phase 2 decision A. This module fills the one seam
that decision left, ``utils.market_records.serper_sentiment_by_ticker``, with the locked news
provider's own per-ticker score.

Rules (the project rule: the LLM never produces a number that reaches the report):

- The number is the provider's per-ticker score, nothing else. ``map_sentiment`` is a pure
  function: the mean of the provider's finite scores, rounded to 4 decimals, kept only inside
  [-1, 1]. It does not rescale (a rescaled score would be a number this project made up).
- Unknown is ``None``, never 0.0. Fewer than ``MIN_ARTICLES`` articles in the window, no
  usable score, a request error and a missing key are all ``None``. 0.0 is published only for
  a real neutral mean.
- The tool runs only from the Flow, after the LLM chose its picks (``ProspectAIFlow.
  market_analysis``), off the event loop. No agent has it and no score reaches a prompt
  before the choice.
- Lookups are cached per symbol and UTC date in a store the caller injects (the backend hands
  a Modal Dict or a JSON file store, keyed per symbol per UTC day). The store needs only
  ``get(key)`` and ``store[key] = value``. The cached value is the provider *observation*,
  ``{"scores": [float, ...], "articles": int}``, not the mapped score, so the minimum-article
  rule is applied on every read and a later change of ``MIN_ARTICLES`` never serves a stale
  decision. A no-data answer (zero articles) is cached, a request error is not, and a cached
  value of any other shape is a miss.
- The provider token is read from ``NEWS_SENTIMENT_API_KEY`` at call time and travels only in
  the request params. It is never logged, returned, cached or put in a tool input. Request
  errors embed the URL (and so the token), so warnings carry the exception class or the status
  code only. No article text, title or URL is stored or returned: scores and counts only.

Provider: Marketaux, free tier, one request per ticker (03.1-DECISIONS.md, 03.1-SENTIMENT-SPIKE.md
"Adapter contract"). The adapter is two pure functions, ``build_params`` and ``parse``, so the
network is the only thing a test has to fake.

Failure containment (D-07, plan 03.1-09). The free tier's 100 requests a day are shared with
public traffic, so refusals are expected, and nothing here may ever fail or stall a run; the only
effect of a failure is a null score.

- One wall budget per call, ``TIME_BUDGET_SECONDS``, measured on ``time.monotonic``. Each request's
  timeout is ``min(MAX_REQUEST_TIMEOUT_SECONDS, budget left)``; with less than
  ``MIN_REQUEST_SECONDS`` left the lookup stops with reason ``budget``. The module never sleeps
  (no retry, no backoff): a free tier is not worth a stall.
- Answer classes. Quota (HTTP 402), rate limit (429) and access denial (401, 403) stop the lookup
  for the rest of the call: ``status`` "stopped", ``stopped_reason`` quota, rate_limited or
  access_denied, every remaining ticker null, no further request. A 5xx, another HTTP status, a
  timeout, any ``requests`` error or an unusable body nulls that ticker and counts one consecutive
  failure; ``MAX_CONSECUTIVE_FAILURES`` in a row stop the lookup with reason ``failures``; a good
  answer resets the count.
- Caching. An error answer is never cached, so the next run or day retries; a no-data answer is.
- Cache operations run on a small module-level thread pool, each waiting at most
  ``min(CACHE_OP_TIMEOUT_SECONDS, budget left)``. A timeout or exception is a miss (read) or a
  skipped write, logged by class, and counted in ``cache_errors`` so a slow or broken store shows
  in the run metrics. A hung store call may keep its worker thread; the run does not wait for it.
- Hygiene. Request errors embed the request address, hence the token, so every warning has the
  fixed shape "news sentiment <fixed reason> (<status code or exception class name>)". Nothing
  formats an exception, a request address, a response body or the token.
"""
import concurrent.futures
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests
from crewai.tools import BaseTool
from pydantic import PrivateAttr

from utils.ticker_matching import is_valid_ticker

logger = logging.getLogger(__name__)

TOOL_NAME = "lookup_news_sentiment"
API_KEY_ENV = "NEWS_SENTIMENT_API_KEY"

# Locked by the operator in 03.1-DECISIONS.md (plan 03.1-01, Task 3).
PROVIDER = "marketaux"            # DECISION provider: marketaux (tier: free)
LOOKBACK_DAYS = 7                 # DECISION window_days: 7
MIN_ARTICLES = 1                  # DECISION min_articles: 1
ARTICLE_COUNT = "found"           # DECISION article_count: found (meta.found, not the capped scored count)
BATCH = "per-ticker"              # DECISION batch: per-ticker
TIME_BUDGET_SECONDS = 8           # DECISION budget_seconds: 8 (wall budget of one lookup call)

# Marketaux free tier: 3 articles per response (spike, "meta.limit echoed 3").
MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"
FREE_TIER_ARTICLE_LIMIT = 3

# Budget and breaker (D-07, research Pattern 4).
MAX_REQUEST_TIMEOUT_SECONDS = 4.0  # one request never waits longer, nor longer than the budget left
MIN_REQUEST_SECONDS = 0.2          # less budget than this left: stop with reason "budget"
MAX_CONSECUTIVE_FAILURES = 2       # this many failures in a row: stop with reason "failures"

# Modal Dict latency, measured from inside a Modal container on a named Dict
# (modal.Dict.from_name, dict_kind "from_name", the same kind as production's
# prospectai-news-sentiment, though not that Dict itself), probe of 2026-11-08, 5 operations each,
# unit milliseconds. Evidence: 03.1-SENTIMENT-SPIKE.md "## Latency". Copied by hand: this package
# never reads the workspace probe output, its suite runs from the repo alone.
MODAL_DICT_PUT_MEDIAN_MS = 51.7
MODAL_DICT_GET_MEDIAN_MS = 35.5

# One cache read or write may wait at most this long: the slower median in ms, divided by 1000 for
# seconds, times 20 for headroom, rounded up to 0.1 s, at least 1.0 s and at most 2.0 s. The 2.0 s
# cap bounds ONE slow store call. It does not by itself fit the 8 s wall budget (5 lookups with a
# read and a write each could take 20 s at the cap); that is held only because every store call
# waits min(CACHE_OP_TIMEOUT_SECONDS, budget left) and the lookup stops with reason "budget" once
# less than MIN_REQUEST_SECONDS remains.
CACHE_OP_TIMEOUT_SECONDS = min(
    2.0, max(1.0, math.ceil(20 * max(MODAL_DICT_PUT_MEDIAN_MS, MODAL_DICT_GET_MEDIAN_MS) / 1000 * 10) / 10),
)

# Provider answer classes that end the lookup for the rest of the call, by HTTP status.
_STOP_REASON_BY_STATUS = {402: "quota", 429: "rate_limited", 401: "access_denied", 403: "access_denied"}

_CACHE_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="news-sentiment-cache")

Observation = Dict[str, Any]


# ── Pure helpers ───────────────────────────────────────────────────────────────

def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def cache_key(provider: str, symbol: str, utc_date: str) -> str:
    """The store key of one symbol's observation on one UTC date."""
    return f"news-sentiment:{provider}:{symbol}:{utc_date}"


def map_sentiment(scores: Any, articles: Any, min_articles: int) -> Optional[float]:
    """The published sentiment of one pick, or None when the evidence is too thin or unusable.

    The mean of the finite provider scores rounded to 4 decimals. None when ``articles`` is not a
    count, is below ``min_articles``, no finite score remains, or the mean falls outside [-1, 1].
    Non-numbers, bools and non-finite values are ignored. No rescaling.
    """
    if isinstance(articles, bool) or not isinstance(articles, int) or articles < min_articles:
        return None
    if not isinstance(scores, (list, tuple)):
        return None
    usable = [float(s) for s in scores if _is_number(s)]
    if not usable:
        return None
    mean = round(sum(usable) / len(usable), 4)
    if not -1.0 <= mean <= 1.0:
        return None
    return mean or 0.0  # -0.0 is a neutral 0.0


def _valid_observation(value: Any) -> Optional[Observation]:
    """A fresh, normalised copy of a cached observation, or None when it has any other shape."""
    if not isinstance(value, dict):
        return None
    scores, articles = value.get("scores"), value.get("articles")
    if isinstance(articles, bool) or not isinstance(articles, int) or articles < 0:
        return None
    if not isinstance(scores, (list, tuple)):
        return None
    if not all(_is_number(s) and -1.0 <= s <= 1.0 for s in scores):
        return None
    return {"scores": [float(s) for s in scores], "articles": articles}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Marketaux adapter ──────────────────────────────────────────────────────────

def provider_symbol(ticker: str) -> str:
    """The spelling the provider knows: a share-class ticker is sent with a hyphen.

    Measured in the spike: ``BRK-B`` returned entity symbol ``BRK-B`` (2 articles in 7 days) and
    ``BRK.B`` returned ``found`` 0. A valid ticker has at most one separator, so this is the
    whole table; every other ticker is sent unchanged.
    """
    return ticker.replace(".", "-")


def _same_symbol(left: Any, right: str) -> bool:
    """Case-insensitive match with '-' and '.' treated as equal (spike, per-ticker score rule)."""
    if not isinstance(left, str):
        return False
    return left.strip().upper().replace(".", "-") == right.upper().replace(".", "-")


def build_params(symbols: Sequence[str], window_start_utc: datetime, token: str) -> "tuple[str, Dict[str, Any]]":
    """(url, query params) of one Marketaux news request for ``symbols``. The token is a param only."""
    return MARKETAUX_URL, {
        "api_token": token,
        "symbols": ",".join(provider_symbol(s) for s in symbols),
        "filter_entities": "true",
        "language": "en",
        "published_after": window_start_utc.strftime("%Y-%m-%dT%H:%M"),
        "limit": FREE_TIER_ARTICLE_LIMIT,
    }


def parse(status_code: Any, body: Any, symbols: Sequence[str]) -> Dict[str, Optional[Observation]]:
    """Per requested symbol, an observation, or None for "no observation this call, do not cache".

    Only a 200 with a ``data`` list and a ``meta`` dict is an answer. For each symbol the scores
    are the ``sentiment_score`` of every entity whose ``symbol`` is that symbol (other entities
    in the same article are other companies); a score that is not a finite number in [-1, 1] is
    dropped. ``articles`` is ``meta.found`` for a single-symbol request when ``ARTICLE_COUNT`` is
    ``found``, otherwise the number of articles that carried a matching score. ``found`` 0 with no
    data is a real, cacheable "no articles".
    """
    nothing: Dict[str, Optional[Observation]] = {s: None for s in symbols}
    if status_code != 200 or not isinstance(body, dict):
        return nothing
    data, meta = body.get("data"), body.get("meta")
    if not isinstance(data, list) or not isinstance(meta, dict):
        return nothing

    use_found = ARTICLE_COUNT == "found" and len(symbols) == 1
    found = meta.get("found")
    if use_found and (isinstance(found, bool) or not isinstance(found, int) or found < 0):
        return nothing

    observations: Dict[str, Optional[Observation]] = {}
    for symbol in symbols:
        wanted = provider_symbol(symbol)
        scores: List[float] = []
        scored_articles = 0
        for article in data:
            entities = article.get("entities") if isinstance(article, dict) else None
            if not isinstance(entities, list):
                continue
            matched = [
                e.get("sentiment_score") for e in entities
                if isinstance(e, dict) and _same_symbol(e.get("symbol"), wanted)
            ]
            usable = [float(s) for s in matched if _is_number(s) and -1.0 <= s <= 1.0]
            if usable:
                scored_articles += 1
                scores.extend(usable)
        observations[symbol] = {"scores": scores, "articles": found if use_found else scored_articles}
    return observations


# ── The tool ───────────────────────────────────────────────────────────────────

class NewsSentimentTool(BaseTool):
    name: str = TOOL_NAME
    description: str = (
        "Look up the news provider's own per-ticker sentiment score for stock tickers. "
        "Input: tickers (list of ticker symbols, each 1 to 5 capital letters with an optional "
        "share-class letter). Output: a JSON object {provider, status, stopped_reason, scores, "
        "articles, requests, cache_hits, cache_errors}; status is ok, no_key or stopped (a refusal "
        "or a spent budget; stopped_reason says which); scores maps each ticker to a "
        "float in [-1, 1] or null (null means unknown, never neutral); articles maps each "
        "ticker to the provider's article count in the lookback window or null. Called only by "
        "the pipeline after the picks are chosen; the result is never shown to an LLM before "
        "the choice."
    )

    _cache: Any = PrivateAttr(default=None)
    _clock: Optional[Callable[[], datetime]] = PrivateAttr(default=None)  # None: the real UTC clock

    def __init__(self, cache: Any = None, clock: Optional[Callable[[], datetime]] = None, **data: Any):
        super().__init__(**data)
        self._cache = cache
        self._clock = clock

    # Store access: a store that fails or stalls degrades to a miss / a skipped write, never to a
    # failed run, and is counted so the run metrics show it.
    def _cache_call(self, deadline: float, fn: Callable[[], Any]) -> "tuple[bool, Any]":
        """Run a store call on the worker pool; (True, value), or (False, None) on timeout or error."""
        wait = min(CACHE_OP_TIMEOUT_SECONDS, deadline - time.monotonic())
        if wait <= 0:
            return False, None
        future = _CACHE_POOL.submit(fn)
        try:
            return True, future.result(timeout=wait)
        except concurrent.futures.TimeoutError:
            future.cancel()  # not started yet: it never runs; started: the worker is left to finish
            logger.warning("%s: news sentiment cache timeout (%s)", "market_analysis", "TimeoutError")
        except Exception as exc:
            logger.warning("%s: news sentiment cache error (%s)", "market_analysis", type(exc).__name__)
        return False, None

    def _cache_get(self, key: str, deadline: float, result: Dict[str, Any]) -> Optional[Observation]:
        if self._cache is None:
            return None
        store = self._cache
        ok, value = self._cache_call(deadline, lambda: store.get(key))
        if not ok:
            result["cache_errors"] += 1
            return None
        return _valid_observation(value)

    def _cache_put(self, key: str, observation: Observation, deadline: float, result: Dict[str, Any]) -> None:
        if self._cache is None:
            return
        store = self._cache
        value = {"scores": list(observation["scores"]), "articles": observation["articles"]}

        def write() -> None:
            store[key] = value

        ok, _ = self._cache_call(deadline, write)
        if not ok:
            result["cache_errors"] += 1

    def _fetch(
        self, group: List[str], token: str, window_start: datetime, timeout: float,
    ) -> "tuple[str, Dict[str, Optional[Observation]]]":
        """One provider request for ``group``: (outcome, observations).

        outcome is "ok", "failure", or a stop reason (quota, rate_limited, access_denied). Only an
        "ok" outcome carries observations; every failure is "no observation" for each symbol.
        """
        nothing: Dict[str, Optional[Observation]] = {s: None for s in group}
        try:
            url, params = build_params(group, window_start, token)
            response = requests.get(url, params=params, timeout=timeout)
            status = response.status_code
            if status in _STOP_REASON_BY_STATUS:
                reason = _STOP_REASON_BY_STATUS[status]
                logger.warning("%s: news sentiment %s (HTTP %s)", "market_analysis", reason, status)
                return reason, nothing
            if status != 200:
                logger.warning("%s: news sentiment provider error (HTTP %s)", "market_analysis", status)
                return "failure", nothing
            observations = parse(status, response.json(), group)
            if all(o is None for o in observations.values()):
                logger.warning("%s: news sentiment unusable answer (HTTP %s)", "market_analysis", status)
                return "failure", nothing
            return "ok", observations
        except Exception as exc:  # a request error embeds the address, hence the token: class name only
            logger.warning("%s: news sentiment request failed (%s)", "market_analysis", type(exc).__name__)
            return "failure", nothing

    def _run(self, tickers: list) -> dict:
        deadline = time.monotonic() + TIME_BUDGET_SECONDS
        symbols: List[str] = []
        for raw in tickers if isinstance(tickers, (list, tuple)) else []:
            symbol = raw.strip().upper() if isinstance(raw, str) else ""
            if is_valid_ticker(symbol) and symbol not in symbols:
                symbols.append(symbol)

        result: Dict[str, Any] = {
            "provider": PROVIDER,
            "status": "ok",
            "stopped_reason": None,
            "scores": {s: None for s in symbols},
            "articles": {s: None for s in symbols},
            "requests": 0,
            "cache_hits": 0,
            "cache_errors": 0,
        }
        token = (os.getenv(API_KEY_ENV) or "").strip()
        if not token:
            result["status"] = "no_key"
            return result

        now = (self._clock or _utc_now)()
        utc_date = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        window_start = now.astimezone(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

        observations: Dict[str, Optional[Observation]] = {}
        misses: List[str] = []
        for symbol in symbols:
            cached = self._cache_get(cache_key(PROVIDER, symbol, utc_date), deadline, result)
            if cached is not None:
                observations[symbol] = cached
                result["cache_hits"] += 1
            else:
                misses.append(symbol)

        groups = [[s] for s in misses] if BATCH == "per-ticker" else ([misses] if misses else [])
        stop: Optional[str] = None
        consecutive_failures = 0
        for group in groups:
            left = deadline - time.monotonic()
            if left < MIN_REQUEST_SECONDS:
                stop = "budget"
                logger.warning("%s: news sentiment budget spent (%s)", "market_analysis", "budget")
                break
            result["requests"] += 1
            outcome, fetched = self._fetch(group, token, window_start, min(MAX_REQUEST_TIMEOUT_SECONDS, left))
            if outcome == "ok":
                consecutive_failures = 0
                for symbol, observation in fetched.items():
                    observations[symbol] = observation
                    if observation is not None:
                        self._cache_put(cache_key(PROVIDER, symbol, utc_date), observation, deadline, result)
            elif outcome == "failure":
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    stop = "failures"
                    logger.warning(
                        "%s: news sentiment too many failures (%s)", "market_analysis", consecutive_failures,
                    )
                    break
            else:  # quota, rate_limited, access_denied: no further request in this call
                stop = outcome
                break

        if stop is not None:
            result["status"] = "stopped"
            result["stopped_reason"] = stop

        for symbol in symbols:
            observation = observations.get(symbol)
            if observation is None:
                continue
            result["articles"][symbol] = observation["articles"]
            result["scores"][symbol] = map_sentiment(observation["scores"], observation["articles"], MIN_ARTICLES)
        return result
