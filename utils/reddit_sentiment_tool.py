#!/usr/bin/env python3
"""
Reddit Sentiment Tool - Fetches Reddit posts and calculates stock sentiment for a sector.
Returns the top 5 most-discussed stocks ranked by mention frequency and sentiment.

Uses Reddit's public JSON endpoints — no OAuth credentials required.

Stall rules (phase 2, plan 02-08, decision D-13). Phase 1 measured this tool at a
fixed 10.3-14.4 s per run while returning no data in 9/9 sectors: an unconditional
2 s sleep before every subreddit request, then a failure. A 429 added a 60 s sleep.
The tool is kept but degrades fast:

- one wall budget per call (TIME_BUDGET_SECONDS, measured with time.monotonic);
  each request's timeout is capped to the budget that is left;
- no sleep before the first request; pacing between two successful requests is
  at most PACING_SECONDS and never longer than the remaining budget;
- a 429 skips that subreddit at once: no wait, no retry;
- a circuit breaker stops the tool after MAX_CONSECUTIVE_FAILURES consecutive
  failed requests (non-200 or request error), so a Reddit outage costs well
  under 3 s instead of the whole budget;
- warnings name the subreddit and the status or exception class only, never a
  URL or exception text.
When Reddit returns nothing usable the tool returns fallback_required=True and
no candidate stocks, so downstream sentiment stays null, never 0.0.
"""

import re
import time
import warnings
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from crewai.tools import BaseTool

import requests

_USER_AGENT = "ProspectAI/1.0 (investment research bot)"
_BASE_URL = "https://www.reddit.com"


class RedditSentimentTool(BaseTool):
    """
    Fetches Reddit posts across investing-focused subreddits and returns
    the top 5 stocks in a given sector ranked by mention count and sentiment.

    Uses Reddit's unauthenticated public JSON endpoints — no credentials needed.
    Sets fallback_required=True (instead of raising) when data cannot be fetched,
    so the calling agent can switch to SerperDevTool.

    Budget (D-13): the whole call stays inside TIME_BUDGET_SECONDS; a 429 skips
    the subreddit with no wait; MAX_CONSECUTIVE_FAILURES failed requests in a row
    open a breaker; pacing between successful requests is at most PACING_SECONDS.
    """

    # Wall budget and failure policy (D-13). Class constants so tests can read them.
    TIME_BUDGET_SECONDS: ClassVar[float] = 10.0
    PACING_SECONDS: ClassVar[float] = 1.0
    MAX_CONSECUTIVE_FAILURES: ClassVar[int] = 2
    MAX_REQUEST_TIMEOUT_SECONDS: ClassVar[float] = 5.0

    name: str = "analyze_sector_reddit_sentiment"
    description: str = """Fetch Reddit posts for a market sector and return the top 5 stocks
    ranked by mention frequency and sentiment score.

    Args:
        sector: One of 'Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer',
                'Industrials', 'Real Estate', 'Utilities'
        limit:  Number of posts to fetch per subreddit (default 25)

    Returns a dict with keys:
        sector              - the requested sector
        candidate_stocks    - list of up to 5 dicts, each with:
                              ticker, mention_count, average_sentiment,
                              relevance_score, sample_posts
        raw_post_count      - total posts scanned
        subreddits_searched - list of subreddit names tried
        fallback_required   - True if Reddit data could not be fetched
        error               - error message (only present when fallback_required=True)
    """

    # Sector → candidate ticker universe.
    # Small, curated lists reduce false-positive ticker matches.
    SECTOR_TICKERS: ClassVar[dict] = {
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

    # Sector-specific subreddit lists for more relevant signal
    SECTOR_CONFIG: ClassVar[dict] = {
        "Technology": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "technology", "artificial", "Stocks_picks", "StockInvest"],
            "keywords":   ["tech", "software", "AI", "cloud", "digital", "innovation", "IT services", "consulting"],
        },
        "Semiconductors": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "hardware", "chipdesign", "Stocks_picks", "StockInvest"],
            "keywords":   ["semiconductor", "chip", "foundry", "fabless", "wafer", "EUV", "lithography", "GPU", "AI chip", "data center", "HBM", "packaging"],
        },
        "Healthcare": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "healthcare", "biotech"],
            "keywords":   ["healthcare", "biotech", "pharma", "medical", "drug", "treatment", "health"],
        },
        "Finance": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "finance", "cryptocurrency"],
            "keywords":   ["finance", "banking", "fintech", "insurance", "investment", "crypto", "blockchain"],
        },
        "Energy": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "energy", "renewableenergy"],
            "keywords":   ["energy", "oil", "gas", "renewable", "solar", "wind", "battery", "clean"],
        },
        "Consumer": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "consumer", "retail"],
            "keywords":   ["consumer", "retail", "ecommerce", "food", "beverage", "apparel", "luxury"],
        },
        "Industrials": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "manufacturing", "aerospace"],
            "keywords":   ["industrial", "manufacturing", "aerospace", "defense", "logistics", "machinery", "construction"],
        },
        "Real Estate": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "realestateinvesting", "REITs"],
            "keywords":   ["REIT", "real estate", "property", "commercial", "residential", "industrial", "office", "datacenter"],
        },
        "Utilities": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "energy", "dividends"],
            "keywords":   ["utility", "utilities", "electric", "gas", "water", "power grid", "renewable", "dividend"],
        },
    }

    # Fallback subreddits when sector is not in SECTOR_CONFIG
    DEFAULT_SUBREDDITS: ClassVar[list] = [
        "investing",
        "stocks",
        "wallstreetbets",
        "SecurityAnalysis",
        "StockMarket",
        "ValueInvesting",
    ]

    def _run(self, sector: str, limit: int = 25) -> Dict[str, Any]:
        """
        Main entry point called by the CrewAI agent.
        Returns structured sentiment data or sets fallback_required=True on failure.
        """
        tickers = self.SECTOR_TICKERS.get(sector, [])
        if not tickers:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "raw_post_count": 0,
                "subreddits_searched": [],
                "fallback_required": True,
                "error": f"Unknown sector '{sector}'. Valid sectors: {list(self.SECTOR_TICKERS.keys())}",
            }

        sector_cfg = self.SECTOR_CONFIG.get(sector, {})
        subreddits = sector_cfg.get("subreddits", self.DEFAULT_SUBREDDITS)

        # Compile patterns for each ticker — match both plain word (\bAAPL\b)
        # and cashtag format ($AAPL), which is common on WSB and r/stocks.
        ticker_patterns: Dict[str, re.Pattern] = {
            ticker: re.compile(
                r"(?:\$|(?<!\w))" + re.escape(ticker.replace(".", r"\.")) + r"(?!\w)",
                re.IGNORECASE,
            )
            for ticker in tickers
        }

        mention_counts: Dict[str, int] = {t: 0 for t in tickers}
        sentiment_sums: Dict[str, float] = {t: 0.0 for t in tickers}
        sample_posts: Dict[str, List[str]] = {t: [] for t in tickers}
        seen_urls: set = set()
        total_posts = 0
        subreddits_searched = []
        any_success = False

        deadline = time.monotonic() + self.TIME_BUDGET_SECONDS
        consecutive_failures = 0
        recent_outcomes: List[str] = []
        stop_reason = ""
        pace_next = False

        for subreddit_name in subreddits:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_reason = f"time budget of {self.TIME_BUDGET_SECONDS:g}s spent"
                break

            # Pace only between a successful request and the next one, never first.
            if pace_next:
                time.sleep(min(self.PACING_SECONDS, remaining))
                pace_next = False

            posts, outcome = self._fetch_posts_public(
                subreddit_name, sort="hot", limit=limit, deadline=deadline
            )
            if outcome == "ok":
                consecutive_failures = 0
                pace_next = True
            else:
                consecutive_failures += 1
                recent_outcomes.append(outcome)
                warnings.warn(f"Reddit r/{subreddit_name} skipped: {self._describe_outcome(outcome)}")
                if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    stop_reason = (
                        f"breaker open after {consecutive_failures} consecutive failures "
                        f"({', '.join(recent_outcomes[-consecutive_failures:])})"
                    )
                    break
            if posts:
                any_success = True
                subreddits_searched.append(subreddit_name)

            for post in posts:
                url = post.get("url", "") or post.get("permalink", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                total_posts += 1

                text = f"{post.get('title', '')} {post.get('selftext', '')}"
                sentiment_score = self._score_sentiment(
                    post.get("score", 0), post.get("upvote_ratio", 0.5)
                )

                for ticker, pattern in ticker_patterns.items():
                    hits = len(pattern.findall(text))
                    if hits > 0:
                        mention_counts[ticker] += hits
                        sentiment_sums[ticker] += sentiment_score
                        if len(sample_posts[ticker]) < 3:
                            sample_posts[ticker].append(post.get("title", "")[:200])

        if not any_success:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "raw_post_count": 0,
                "subreddits_searched": [],
                "fallback_required": True,
                "error": (
                    "All Reddit public endpoint requests failed"
                    + (f" ({stop_reason})" if stop_reason else "")
                    + ". Serper fallback required."
                ),
            }

        # Build ranked list — only include stocks with at least 1 mention
        ranked = []
        for ticker in tickers:
            count = mention_counts[ticker]
            if count == 0:
                continue
            avg_sentiment = round(sentiment_sums[ticker] / count, 4)
            ranked.append(
                {
                    "ticker": ticker,
                    "mention_count": count,
                    "average_sentiment": avg_sentiment,
                    "relevance_score": 0.0,  # filled below
                    "sample_posts": sample_posts[ticker],
                }
            )

        # Sort: highest mention count first, break ties by sentiment
        ranked.sort(key=lambda x: (-x["mention_count"], -x["average_sentiment"]))
        top5 = ranked[:5]

        if not top5:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "raw_post_count": total_posts,
                "subreddits_searched": subreddits_searched,
                "fallback_required": True,
                "error": f"No {sector} sector tickers found in Reddit posts. Serper fallback required.",
            }

        # Relevance score: linear decay from 1.0 to 0.6 across 5 positions
        for i, stock in enumerate(top5):
            stock["relevance_score"] = round(1.0 - i * 0.08, 4)

        return {
            "sector": sector,
            "candidate_stocks": top5,
            "raw_post_count": total_posts,
            "subreddits_searched": subreddits_searched,
            "fallback_required": False,
        }

    @staticmethod
    def _describe_outcome(outcome: str) -> str:
        """Outcome code to log text: a status or an exception class, never a URL."""
        if outcome == "rate_limited":
            return "status 429"
        if outcome.startswith("http_"):
            return f"status {outcome[len('http_'):]}"
        if outcome.startswith("error_"):
            return f"exception {outcome[len('error_'):]}"
        return outcome

    def _get_json(
        self, url: str, params: Dict[str, Any], deadline: float
    ) -> Tuple[Optional[dict], str]:
        """
        One bounded GET against Reddit. Never sleeps, never retries.

        Returns (json, outcome). Outcome is one of "ok", "rate_limited" (429, returned
        at once), "http_<status>", "error_<ExceptionClass>" or "budget" (nothing left).
        The request timeout is min(MAX_REQUEST_TIMEOUT_SECONDS, remaining budget).
        """
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, "budget"
        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=min(self.MAX_REQUEST_TIMEOUT_SECONDS, remaining),
            )
            if response.status_code == 429:
                return None, "rate_limited"
            if response.status_code != 200:
                return None, f"http_{response.status_code}"
            data = response.json()
            if not isinstance(data, dict):
                return None, "error_TypeError"
            return data, "ok"
        except requests.exceptions.RequestException as exc:
            return None, f"error_{type(exc).__name__}"
        except ValueError as exc:
            return None, f"error_{type(exc).__name__}"

    @staticmethod
    def _posts_from(data: dict) -> List[Dict[str, Any]]:
        children = data.get("data", {}).get("children", [])
        return [child["data"] for child in children if child.get("data")]

    def _fetch_posts_public(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = 25,
        time_filter: str = "week",
        deadline: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Fetch posts from a subreddit using Reddit's public JSON endpoint.
        No credentials required.

        Args:
            subreddit:   Subreddit name (without r/)
            sort:        Listing sort — hot | new | top | rising
            limit:       Number of posts to fetch (max 100)
            time_filter: Time window for top/controversial — hour | day | week | month | year | all
            deadline:    time.monotonic() value the call must finish by
                         (default: TIME_BUDGET_SECONDS from now)

        Returns:
            (posts, outcome): posts are child["data"] dicts from Reddit's response;
            the list is empty on any failure so the caller can continue. Outcome is
            the code from _get_json. No sleeping and no retry here (D-13).
        """
        if deadline is None:
            deadline = time.monotonic() + self.TIME_BUDGET_SECONDS
        url = f"{_BASE_URL}/r/{subreddit}/{sort}.json"
        params: Dict[str, Any] = {"limit": limit}
        if sort in ("top", "controversial"):
            params["t"] = time_filter

        data, outcome = self._get_json(url, params, deadline)
        if data is None:
            return [], outcome
        try:
            return self._posts_from(data), "ok"
        except (KeyError, AttributeError, TypeError) as exc:
            return [], f"error_{type(exc).__name__}"

    def _search_reddit_public(
        self,
        query: str,
        sort: str = "relevance",
        time_filter: str = "week",
        limit: int = 25,
        deadline: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Search Reddit using the public search JSON endpoint.
        No credentials required. Not used by _run; same budget rules (D-13).

        Args:
            query:       Search query string
            sort:        relevance | hot | top | new
            time_filter: hour | day | week | month | year | all
            limit:       Number of results (max 100)
            deadline:    time.monotonic() value the call must finish by

        Returns:
            (posts, outcome), as _fetch_posts_public. Empty list on any failure.
        """
        if deadline is None:
            deadline = time.monotonic() + self.TIME_BUDGET_SECONDS
        url = f"{_BASE_URL}/search.json"
        params: Dict[str, Any] = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": limit,
        }

        data, outcome = self._get_json(url, params, deadline)
        if data is None:
            warnings.warn(f"Reddit search failed: {self._describe_outcome(outcome)}")
            return [], outcome
        try:
            return self._posts_from(data), "ok"
        except (KeyError, AttributeError, TypeError) as exc:
            return [], f"error_{type(exc).__name__}"

    def _score_sentiment(self, upvotes: int, upvote_ratio: float) -> float:
        """
        Produce a [-1, +1] sentiment proxy from Reddit engagement signals.
        upvote_ratio is 0-1; we center it at 0.5 and scale to [-1, +1].
        A small volume boost rewards high-engagement posts, capped at 0.3.
        """
        base = (upvote_ratio - 0.5) * 2.0
        volume_boost = min(max(upvotes, 0) / 1000.0, 0.3)
        return round(max(-1.0, min(1.0, base + volume_boost)), 4)
