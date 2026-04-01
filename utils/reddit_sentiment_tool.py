#!/usr/bin/env python3
"""
Reddit Sentiment Tool - Fetches Reddit posts and calculates stock sentiment for a sector.
Returns the top 5 most-discussed stocks ranked by mention frequency and sentiment.

Uses Reddit's public JSON endpoints — no OAuth credentials required.
"""

import re
import time
import warnings
from typing import Any, ClassVar, Dict, List
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
    """

    name: str = "analyze_sector_reddit_sentiment"
    description: str = """Fetch Reddit posts for a market sector and return the top 5 stocks
    ranked by mention frequency and sentiment score.

    Args:
        sector: One of 'Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer'
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
            "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN",
            "TSLA", "AMD", "INTC", "CRM", "ORCL", "ADBE", "QCOM", "AVGO",
        ],
        "Healthcare": [
            "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO",
            "ABT", "AMGN", "GILD", "ISRG", "MDT", "CVS", "BMY",
        ],
        "Finance": [
            "JPM", "BAC", "WFC", "GS", "MS", "BRK.B", "V",
            "MA", "AXP", "C", "SCHW", "BLK", "SPGI", "CB",
        ],
        "Energy": [
            "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO",
            "MPC", "OXY", "HAL", "DVN", "FANG", "HES", "BKR",
        ],
        "Consumer": [
            "WMT", "AMZN", "HD", "NKE", "SBUX", "MCD", "TGT",
            "COST", "LOW", "TJX", "BABA", "PG", "KO", "PEP",
        ],
    }

    # Sector-specific subreddit lists for more relevant signal
    SECTOR_CONFIG: ClassVar[dict] = {
        "Technology": {
            "subreddits": ["investing", "stocks", "wallstreetbets", "technology", "artificial"],
            "keywords":   ["tech", "software", "AI", "semiconductor", "cloud", "digital", "innovation"],
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

        # Compile whole-word patterns for each ticker once
        ticker_patterns: Dict[str, re.Pattern] = {
            ticker: re.compile(
                r"\b" + re.escape(ticker.replace(".", r"\.")) + r"\b",
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

        for subreddit_name in subreddits:
            posts = self._fetch_posts_public(subreddit_name, sort="hot", limit=limit)
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
                "error": "All Reddit public endpoint requests failed. Serper fallback required.",
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

    def _fetch_posts_public(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = 25,
        time_filter: str = "week",
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit using Reddit's public JSON endpoint.
        No credentials required.

        Args:
            subreddit:   Subreddit name (without r/)
            sort:        Listing sort — hot | new | top | rising
            limit:       Number of posts to fetch (max 100)
            time_filter: Time window for top/controversial — hour | day | week | month | year | all

        Returns:
            List of post data dicts (child["data"] from Reddit's response).
            Returns empty list on any error so the caller can continue.
        """
        url = f"{_BASE_URL}/r/{subreddit}/{sort}.json"
        params: Dict[str, Any] = {"limit": limit}
        if sort in ("top", "controversial"):
            params["t"] = time_filter

        time.sleep(2)  # respect unauthenticated rate limit (~10 req/min)

        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=15,
            )

            if response.status_code == 429:
                warnings.warn(f"Reddit rate-limited on r/{subreddit}. Sleeping 60s and retrying.")
                time.sleep(60)
                response = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=15,
                )

            if response.status_code != 200:
                warnings.warn(f"Reddit returned HTTP {response.status_code} for r/{subreddit}/{sort}")
                return []

            data = response.json()
            children = data.get("data", {}).get("children", [])
            return [child["data"] for child in children if child.get("data")]

        except requests.exceptions.RequestException as exc:
            warnings.warn(f"Reddit request failed for r/{subreddit}: {exc}")
            return []
        except (KeyError, ValueError) as exc:
            warnings.warn(f"Reddit response parse error for r/{subreddit}: {exc}")
            return []

    def _search_reddit_public(
        self,
        query: str,
        sort: str = "relevance",
        time_filter: str = "week",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Search Reddit using the public search JSON endpoint.
        No credentials required.

        Args:
            query:       Search query string
            sort:        relevance | hot | top | new
            time_filter: hour | day | week | month | year | all
            limit:       Number of results (max 100)

        Returns:
            List of post data dicts. Returns empty list on any error.
        """
        url = f"{_BASE_URL}/search.json"
        params: Dict[str, Any] = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": limit,
        }

        time.sleep(2)  # respect unauthenticated rate limit

        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=15,
            )

            if response.status_code == 429:
                warnings.warn(f"Reddit rate-limited on search '{query}'. Sleeping 60s and retrying.")
                time.sleep(60)
                response = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=15,
                )

            if response.status_code != 200:
                warnings.warn(f"Reddit search returned HTTP {response.status_code} for '{query}'")
                return []

            data = response.json()
            children = data.get("data", {}).get("children", [])
            return [child["data"] for child in children if child.get("data")]

        except requests.exceptions.RequestException as exc:
            warnings.warn(f"Reddit search request failed for '{query}': {exc}")
            return []
        except (KeyError, ValueError) as exc:
            warnings.warn(f"Reddit search parse error for '{query}': {exc}")
            return []

    def _score_sentiment(self, upvotes: int, upvote_ratio: float) -> float:
        """
        Produce a [-1, +1] sentiment proxy from Reddit engagement signals.
        upvote_ratio is 0-1; we center it at 0.5 and scale to [-1, +1].
        A small volume boost rewards high-engagement posts, capped at 0.3.
        """
        base = (upvote_ratio - 0.5) * 2.0
        volume_boost = min(max(upvotes, 0) / 1000.0, 0.3)
        return round(max(-1.0, min(1.0, base + volume_boost)), 4)
