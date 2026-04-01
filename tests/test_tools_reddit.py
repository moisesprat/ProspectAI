"""
Tests for RedditSentimentTool.
No real Reddit calls — PRAW is mocked throughout.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


def _make_post(title: str, score: int = 100, upvote_ratio: float = 0.85,
               selftext: str = "") -> MagicMock:
    post = MagicMock()
    post.title = title
    post.selftext = selftext
    post.score = score
    post.upvote_ratio = upvote_ratio
    return post


def _subreddit_with_posts(posts):
    sr = MagicMock()
    sr.hot.return_value = posts
    return sr


def _make_reddit(subreddits_map: dict):
    reddit = MagicMock()
    reddit.user.me.return_value = MagicMock()
    reddit.subreddit.side_effect = lambda name: subreddits_map.get(name, _subreddit_with_posts([]))
    return reddit


# ── Missing credentials ───────────────────────────────────────────────────────

class TestRedditFallbackWhenNoCreds:

    def test_missing_client_id_sets_fallback_required(self):
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": "secret"}):
            from utils.reddit_sentiment_tool import RedditSentimentTool
            result = RedditSentimentTool()._run("Technology")
            assert result["fallback_required"] is True
            assert "error" in result

    def test_missing_client_secret_sets_fallback_required(self):
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": ""}):
            from utils.reddit_sentiment_tool import RedditSentimentTool
            result = RedditSentimentTool()._run("Technology")
            assert result["fallback_required"] is True

    def test_auth_failure_sets_fallback_required(self):
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "bad"}):
            import praw
            with patch("praw.Reddit") as mock_reddit_cls:
                mock_reddit_cls.return_value.user.me.side_effect = Exception("401 Unauthorized")
                from utils.reddit_sentiment_tool import RedditSentimentTool
                result = RedditSentimentTool()._run("Technology")
                assert result["fallback_required"] is True

    def test_unknown_sector_sets_fallback_required(self):
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "s"}):
            with patch("praw.Reddit") as mock_reddit_cls:
                mock_reddit_cls.return_value.user.me.return_value = MagicMock()
                from utils.reddit_sentiment_tool import RedditSentimentTool
                result = RedditSentimentTool()._run("Cryptocurrency")
                assert result["fallback_required"] is True


# ── Successful Reddit fetch ───────────────────────────────────────────────────

class TestRedditSuccessfulFetch:

    def _run_with_posts(self, posts, sector="Technology"):
        sr = _subreddit_with_posts(posts)
        reddit = _make_reddit({name: sr for name in
                                ["investing", "stocks", "wallstreetbets",
                                 "SecurityAnalysis", "StockMarket", "ValueInvesting"]})
        env = {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}
        with patch.dict(os.environ, env):
            with patch("praw.Reddit", return_value=reddit):
                from utils.reddit_sentiment_tool import RedditSentimentTool
                return RedditSentimentTool()._run(sector)

    def test_fallback_required_is_false_on_success(self):
        posts = [_make_post("NVDA is booming")] * 10
        result = self._run_with_posts(posts)
        assert result["fallback_required"] is False

    def test_returns_at_most_five_stocks(self):
        posts = [_make_post(f"NVDA AAPL MSFT GOOGL META AMD TSLA INTC CRM ADBE")]
        result = self._run_with_posts(posts)
        assert len(result["candidate_stocks"]) <= 5

    def test_candidate_stock_schema(self):
        posts = [_make_post("NVDA is great", score=500, upvote_ratio=0.9)]
        result = self._run_with_posts(posts)
        for stock in result["candidate_stocks"]:
            assert "ticker" in stock
            assert "mention_count" in stock
            assert "average_sentiment" in stock
            assert "relevance_score" in stock
            assert isinstance(stock["mention_count"], int)
            assert isinstance(stock["average_sentiment"], float)

    def test_mention_count_is_positive(self):
        posts = [_make_post("NVDA NVDA NVDA")] * 5
        result = self._run_with_posts(posts)
        nvda = next((s for s in result["candidate_stocks"] if s["ticker"] == "NVDA"), None)
        assert nvda is not None
        assert nvda["mention_count"] > 0

    def test_stocks_sorted_by_mention_count_descending(self):
        posts = (
            [_make_post("NVDA")] * 10 +
            [_make_post("AAPL")] * 5 +
            [_make_post("MSFT")] * 2
        )
        result = self._run_with_posts(posts)
        counts = [s["mention_count"] for s in result["candidate_stocks"]]
        assert counts == sorted(counts, reverse=True)

    def test_sector_field_matches_input(self):
        posts = [_make_post("NVDA")]
        result = self._run_with_posts(posts)
        assert result["sector"] == "Technology"

    def test_raw_post_count_is_positive(self):
        posts = [_make_post("NVDA")] * 20
        result = self._run_with_posts(posts)
        assert result["raw_post_count"] > 0

    def test_subreddits_searched_is_populated(self):
        posts = [_make_post("NVDA")]
        result = self._run_with_posts(posts)
        assert len(result["subreddits_searched"]) > 0

    def test_no_stocks_mentioned_returns_empty_candidate_list(self):
        posts = [_make_post("The market is interesting today with no tickers")]
        result = self._run_with_posts(posts)
        assert result["candidate_stocks"] == []

    def test_relevance_score_decreases_with_rank(self):
        posts = (
            [_make_post("NVDA")] * 15 +
            [_make_post("AAPL")] * 10 +
            [_make_post("MSFT")] * 5 +
            [_make_post("GOOGL")] * 3 +
            [_make_post("META")] * 1
        )
        result = self._run_with_posts(posts)
        scores = [s["relevance_score"] for s in result["candidate_stocks"]]
        assert scores == sorted(scores, reverse=True)

    def test_all_tickers_come_from_sector_universe(self):
        posts = [_make_post("NVDA AAPL MSFT GOOGL META TSLA AMD INTC FAKE123")]
        result = self._run_with_posts(posts)
        from utils.reddit_sentiment_tool import RedditSentimentTool
        valid = set(RedditSentimentTool.SECTOR_TICKERS["Technology"])
        for stock in result["candidate_stocks"]:
            assert stock["ticker"] in valid


# ── Sentiment scoring ─────────────────────────────────────────────────────────

class TestSentimentScoring:

    def test_high_upvote_ratio_gives_positive_sentiment(self):
        from utils.reddit_sentiment_tool import RedditSentimentTool
        score = RedditSentimentTool()._score_sentiment(1000, 0.95)
        assert score > 0

    def test_low_upvote_ratio_gives_negative_sentiment(self):
        from utils.reddit_sentiment_tool import RedditSentimentTool
        score = RedditSentimentTool()._score_sentiment(100, 0.1)
        assert score < 0

    def test_sentiment_is_bounded_between_minus_one_and_one(self):
        from utils.reddit_sentiment_tool import RedditSentimentTool
        tool = RedditSentimentTool()
        for upvotes, ratio in [(0, 0.0), (10000, 1.0), (500, 0.5), (100, 0.3)]:
            s = tool._score_sentiment(upvotes, ratio)
            assert -1.0 <= s <= 1.0, f"Sentiment {s} out of bounds"
