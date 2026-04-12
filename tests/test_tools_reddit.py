"""
Tests for RedditSentimentTool.
All Reddit HTTP requests are mocked — no real network calls.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from utils.reddit_sentiment_tool import RedditSentimentTool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reddit_response(posts: list) -> MagicMock:
    """Mock requests.Response returning Reddit-format JSON."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {"children": [{"data": p} for p in posts]}
    }
    return resp


def _post(title: str, score: int = 100, upvote_ratio: float = 0.85,
          selftext: str = "") -> dict:
    return {
        "title": title,
        "selftext": selftext,
        "score": score,
        "upvote_ratio": upvote_ratio,
        "url": f"https://reddit.com/{hash(title)}",
        "permalink": f"/r/stocks/{hash(title)}",
    }


def _run_with_posts(posts, sector="Technology"):
    """Run the tool with mocked HTTP responses (no network, no sleep)."""
    resp = _reddit_response(posts)
    with patch("utils.reddit_sentiment_tool.requests.get", return_value=resp), \
         patch("utils.reddit_sentiment_tool.time.sleep"):
        return RedditSentimentTool()._run(sector)


# ── Tool contract ──────────────────────────────────────────────────────────────

def test_tool_name():
    assert RedditSentimentTool().name == "analyze_sector_reddit_sentiment"


# ── Fallback behavior ──────────────────────────────────────────────────────────

class TestRedditFallback:

    def test_unknown_sector_sets_fallback_required(self):
        result = RedditSentimentTool()._run("Cryptocurrency")
        assert result["fallback_required"] is True
        assert "error" in result

    def test_http_connection_error_sets_fallback_required(self):
        import requests
        with patch("utils.reddit_sentiment_tool.requests.get",
                   side_effect=requests.exceptions.ConnectionError("no network")), \
             patch("utils.reddit_sentiment_tool.time.sleep"):
            result = RedditSentimentTool()._run("Technology")
        assert result["fallback_required"] is True
        assert "error" in result

    def test_http_500_sets_fallback_required(self):
        resp = MagicMock()
        resp.status_code = 500
        with patch("utils.reddit_sentiment_tool.requests.get", return_value=resp), \
             patch("utils.reddit_sentiment_tool.time.sleep"):
            result = RedditSentimentTool()._run("Technology")
        assert result["fallback_required"] is True

    def test_no_tickers_in_posts_sets_fallback_required(self):
        posts = [_post("The market looks interesting today")]
        result = _run_with_posts(posts)
        assert result["fallback_required"] is True
        assert result["candidate_stocks"] == []


# ── Successful fetch ───────────────────────────────────────────────────────────

class TestRedditSuccessfulFetch:

    def test_fallback_required_is_false_on_success(self):
        result = _run_with_posts([_post("$NVDA is booming")] * 10)
        assert result["fallback_required"] is False

    def test_returns_at_most_five_stocks(self):
        posts = [_post("NVDA AAPL MSFT GOOGL META AMD TSLA INTC CRM ADBE")]
        result = _run_with_posts(posts)
        assert len(result["candidate_stocks"]) <= 5

    def test_candidate_stock_schema(self):
        result = _run_with_posts([_post("$NVDA is great", score=500, upvote_ratio=0.9)])
        for stock in result["candidate_stocks"]:
            assert "ticker" in stock
            assert "mention_count" in stock
            assert "average_sentiment" in stock
            assert "relevance_score" in stock
            assert isinstance(stock["mention_count"], int)
            assert isinstance(stock["average_sentiment"], float)

    def test_mention_count_is_positive(self):
        posts = [_post("$NVDA is bullish today")] * 5
        result = _run_with_posts(posts)
        nvda = next((s for s in result["candidate_stocks"] if s["ticker"] == "NVDA"), None)
        assert nvda is not None
        assert nvda["mention_count"] > 0

    def test_stocks_sorted_by_mention_count_descending(self):
        posts = (
            [_post("$NVDA")] * 10 +
            [_post("$AAPL")] * 5 +
            [_post("$MSFT")] * 2
        )
        result = _run_with_posts(posts)
        counts = [s["mention_count"] for s in result["candidate_stocks"]]
        assert counts == sorted(counts, reverse=True)

    def test_sector_field_matches_input(self):
        result = _run_with_posts([_post("$NVDA")])
        assert result["sector"] == "Technology"

    def test_raw_post_count_is_positive(self):
        result = _run_with_posts([_post("$NVDA")] * 20)
        assert result["raw_post_count"] > 0

    def test_subreddits_searched_is_populated(self):
        result = _run_with_posts([_post("$NVDA")])
        assert len(result["subreddits_searched"]) > 0

    def test_no_stocks_mentioned_returns_empty_candidate_list(self):
        posts = [_post("The market is interesting today with no tickers")]
        result = _run_with_posts(posts)
        assert result["candidate_stocks"] == []

    def test_relevance_score_decreases_with_rank(self):
        posts = (
            [_post("$NVDA")] * 15 +
            [_post("$AAPL")] * 10 +
            [_post("$MSFT")] * 5 +
            [_post("$GOOGL")] * 3 +
            [_post("$META")] * 1
        )
        result = _run_with_posts(posts)
        scores = [s["relevance_score"] for s in result["candidate_stocks"]]
        assert scores == sorted(scores, reverse=True)

    def test_all_tickers_come_from_sector_universe(self):
        posts = [_post("NVDA AAPL MSFT GOOGL META TSLA AMD INTC FAKE123")]
        result = _run_with_posts(posts)
        valid = set(RedditSentimentTool.SECTOR_TICKERS["Technology"])
        for stock in result["candidate_stocks"]:
            assert stock["ticker"] in valid


# ── Sentiment scoring ─────────────────────────────────────────────────────────

class TestSentimentScoring:

    def test_high_upvote_ratio_gives_positive_sentiment(self):
        score = RedditSentimentTool()._score_sentiment(1000, 0.95)
        assert score > 0

    def test_low_upvote_ratio_gives_negative_sentiment(self):
        score = RedditSentimentTool()._score_sentiment(100, 0.1)
        assert score < 0

    def test_sentiment_is_bounded_between_minus_one_and_one(self):
        tool = RedditSentimentTool()
        for upvotes, ratio in [(0, 0.0), (10000, 1.0), (500, 0.5), (100, 0.3)]:
            s = tool._score_sentiment(upvotes, ratio)
            assert -1.0 <= s <= 1.0, f"Sentiment {s} out of bounds for ({upvotes}, {ratio})"
