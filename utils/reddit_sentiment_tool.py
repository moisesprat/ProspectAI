#!/usr/bin/env python3
"""
Reddit Sentiment Tool - Fetches Reddit posts and calculates stock sentiment for a sector.
Returns the top 5 most-discussed stocks ranked by mention frequency and sentiment.
"""

import os
import re
from typing import Any, ClassVar, Dict, List
from crewai.tools import BaseTool


class RedditSentimentTool(BaseTool):
    """
    Fetches Reddit posts across investing-focused subreddits and returns
    the top 5 stocks in a given sector ranked by mention count and sentiment.

    Sets fallback_required=True (instead of raising) when PRAW credentials
    are missing or invalid, so the calling agent can switch to SerperDevTool.
    """

    name: str = "analyze_sector_reddit_sentiment"
    description: str = """Fetch Reddit posts for a market sector and return the top 5 stocks
    ranked by mention frequency and sentiment score.

    Args:
        sector: One of 'Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer'
        limit:  Number of posts to fetch per subreddit (default 100)

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

    SUBREDDITS: list = [
        "investing",
        "stocks",
        "wallstreetbets",
        "SecurityAnalysis",
        "StockMarket",
        "ValueInvesting",
    ]

    def _run(self, sector: str, limit: int = 100) -> Dict[str, Any]:
        """
        Main entry point called by the CrewAI agent.
        Returns structured sentiment data or sets fallback_required=True on failure.
        """
        try:
            import praw
        except ImportError:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "raw_post_count": 0,
                "subreddits_searched": [],
                "fallback_required": True,
                "error": "praw not installed. Run: pip install praw>=7.7.0",
            }

        client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
        user_agent = os.getenv("REDDIT_USER_AGENT", "ProspectAI/1.0").strip()

        if not client_id or not client_secret:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "raw_post_count": 0,
                "subreddits_searched": [],
                "fallback_required": True,
                "error": (
                    "REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not set. "
                    "Using Serper fallback."
                ),
            }

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

        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            # Validate credentials with a lightweight call
            reddit.user.me()
        except Exception as e:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "raw_post_count": 0,
                "subreddits_searched": [],
                "fallback_required": True,
                "error": f"Reddit authentication failed: {str(e)}",
            }

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
        total_posts = 0
        subreddits_searched = []

        for subreddit_name in self.SUBREDDITS:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                posts = list(subreddit.hot(limit=limit))
                total_posts += len(posts)
                subreddits_searched.append(subreddit_name)

                for post in posts:
                    text = f"{post.title} {post.selftext}"
                    sentiment_score = self._score_sentiment(
                        post.score, post.upvote_ratio
                    )

                    for ticker, pattern in ticker_patterns.items():
                        hits = len(pattern.findall(text))
                        if hits > 0:
                            mention_counts[ticker] += hits
                            sentiment_sums[ticker] += sentiment_score
                            if len(sample_posts[ticker]) < 3:
                                sample_posts[ticker].append(post.title[:200])

            except Exception:
                # Skip inaccessible subreddits; continue with others
                continue

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

    def _score_sentiment(self, upvotes: int, upvote_ratio: float) -> float:
        """
        Produce a [-1, +1] sentiment proxy from Reddit engagement signals.
        upvote_ratio is 0-1; we center it at 0.5 and scale to [-1, +1].
        A small volume boost rewards high-engagement posts, capped at 0.3.
        """
        base = (upvote_ratio - 0.5) * 2.0
        volume_boost = min(max(upvotes, 0) / 1000.0, 0.3)
        return round(max(-1.0, min(1.0, base + volume_boost)), 4)
