"""
Tests for RedditSentimentTool.
All Reddit HTTP requests are mocked — no real network calls.
"""

import os
import pytest
import requests
from unittest.mock import patch, MagicMock

from tests.fake_clock import FakeClock
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


def _status_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    return resp


def _run_on_fake_clock(response, latency=0.0, sector="Technology"):
    """Run the tool with requests.get and the module clock faked."""
    clock = FakeClock()
    get = clock.get_side_effect(response, latency=latency)
    with patch("utils.reddit_sentiment_tool.requests.get", side_effect=get), \
         patch("utils.reddit_sentiment_tool.time", clock):
        result = RedditSentimentTool()._run(sector)
    return result, clock


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
        result = _run_with_posts([_post("$MSFT is booming")] * 10)
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
        posts = [_post("$MSFT is bullish today")] * 5
        result = _run_with_posts(posts)
        msft = next((s for s in result["candidate_stocks"] if s["ticker"] == "MSFT"), None)
        assert msft is not None
        assert msft["mention_count"] > 0

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


# ── Sector definitions ────────────────────────────────────────────────────────

class TestSectorDefinitions:

    def test_no_ticker_overlap_between_technology_and_semiconductors(self):
        tech = set(RedditSentimentTool.SECTOR_TICKERS["Technology"])
        semi = set(RedditSentimentTool.SECTOR_TICKERS["Semiconductors"])
        assert tech & semi == set(), f"Overlapping tickers: {tech & semi}"

    def test_semiconductors_sector_exists_with_key_tickers(self):
        semi = set(RedditSentimentTool.SECTOR_TICKERS["Semiconductors"])
        assert "Semiconductors" in RedditSentimentTool.SECTOR_TICKERS
        for ticker in ("ASML", "TSM", "NVDA"):
            assert ticker in semi, f"{ticker} missing from Semiconductors"

    def test_it_services_tickers_in_technology(self):
        tech = set(RedditSentimentTool.SECTOR_TICKERS["Technology"])
        for ticker in ("EPAM", "INFY", "CTSH"):
            assert ticker in tech, f"{ticker} missing from Technology"

    def test_semiconductor_tickers_not_in_technology(self):
        tech = set(RedditSentimentTool.SECTOR_TICKERS["Technology"])
        moved = {"NVDA", "AMD", "INTC", "QCOM", "AVGO", "MU", "MRVL", "ALAB", "SMCI", "ARM"}
        assert tech & moved == set(), f"Chip tickers still in Technology: {tech & moved}"

    def test_stocks_picks_and_stockinvest_in_technology_subreddits(self):
        subs = RedditSentimentTool.SECTOR_CONFIG["Technology"]["subreddits"]
        assert "Stocks_picks" in subs
        assert "StockInvest" in subs

    def test_stocks_picks_and_stockinvest_in_semiconductors_subreddits(self):
        subs = RedditSentimentTool.SECTOR_CONFIG["Semiconductors"]["subreddits"]
        assert "Stocks_picks" in subs
        assert "StockInvest" in subs


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


# ── Budget, breaker and pacing (change phase-2 plan 02-08, D-13) ──────────────

class TestRedditBudget:

    def test_all_429_stops_fast(self):
        result, clock = _run_on_fake_clock(_status_response(429))
        assert result["fallback_required"] is True
        assert result["candidate_stocks"] == []
        assert clock.request_count == 2  # breaker opens after two failures
        assert clock.now < 1.0
        assert 60 not in clock.sleeps and 60.0 not in clock.sleeps

    def test_one_429_is_skipped(self):
        ok = _reddit_response([_post("$MSFT is booming")])
        result, clock = _run_on_fake_clock([_status_response(429), ok])
        subs = RedditSentimentTool.SECTOR_CONFIG["Technology"]["subreddits"]
        assert subs[0] not in result["subreddits_searched"]
        assert subs[1] in result["subreddits_searched"]
        assert result["fallback_required"] is False
        assert clock.now < 10.0
        assert all(s <= 1.0 for s in clock.sleeps)

    def test_all_403_breaker_under_3s(self):
        result, clock = _run_on_fake_clock(_status_response(403))
        assert result["fallback_required"] is True
        assert clock.request_count == 2
        assert clock.now < 3.0
        assert "breaker" in result["error"]
        assert "http_403" in result["error"]

    def test_all_request_errors_open_the_breaker(self):
        err = requests.exceptions.ConnectionError("no network")
        result, clock = _run_on_fake_clock(err)
        assert result["fallback_required"] is True
        assert clock.request_count == 2
        assert clock.now < 3.0
        assert "error_ConnectionError" in result["error"]

    def test_budget_caps_slow_responses(self):
        ok = _reddit_response([_post("$MSFT is booming")])
        result, clock = _run_on_fake_clock(ok, latency=3.0)
        assert clock.now <= RedditSentimentTool.TIME_BUDGET_SECONDS + 0.5
        assert all(t is not None and t <= RedditSentimentTool.MAX_REQUEST_TIMEOUT_SECONDS
                   for t in clock.timeouts)
        # A later request is never allowed more time than the budget has left.
        assert min(clock.timeouts) < RedditSentimentTool.MAX_REQUEST_TIMEOUT_SECONDS

    def test_no_sleep_before_first_request(self):
        ok = _reddit_response([_post("$MSFT is booming")])
        _, clock = _run_on_fake_clock(ok)
        assert clock.events[0][0] == "get"

    def test_pacing_is_bounded(self):
        ok = _reddit_response([_post("$MSFT is booming")])
        result, clock = _run_on_fake_clock(ok)
        assert result["fallback_required"] is False
        assert clock.sleeps, "successful requests are paced"
        assert all(s <= RedditSentimentTool.PACING_SECONDS for s in clock.sleeps)
        assert clock.now <= RedditSentimentTool.TIME_BUDGET_SECONDS

    def test_pacing_never_exceeds_remaining_budget(self):
        ok = _reddit_response([_post("$MSFT is booming")])
        clock = FakeClock()
        get = clock.get_side_effect(ok, latency=4.8)
        with patch("utils.reddit_sentiment_tool.requests.get", side_effect=get), \
             patch("utils.reddit_sentiment_tool.time", clock):
            RedditSentimentTool()._run("Technology")
        assert clock.now <= RedditSentimentTool.TIME_BUDGET_SECONDS + 1e-9

    def test_warnings_have_no_urls(self):
        import warnings as _warnings
        err = requests.exceptions.ConnectionError("HTTPSConnectionPool(host='www.reddit.com'): max retries")
        for response in (_status_response(403), _status_response(429), err):
            with _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always")
                _run_on_fake_clock(response)
            texts = [str(w.message) for w in caught]
            assert texts, "failures warn"
            for text in texts:
                assert "http" not in text.lower(), text
                assert "reddit.com" not in text.lower(), text
                assert "r/investing" in text or "r/stocks" in text, text
        # status and exception class are named
        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            _run_on_fake_clock(_status_response(403))
        assert any("403" in str(w.message) for w in caught)
        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            _run_on_fake_clock(err)
        assert any("ConnectionError" in str(w.message) for w in caught)

    def test_empty_reddit_leaves_no_sentiment(self):
        result, _ = _run_on_fake_clock(_status_response(500))
        assert result["candidate_stocks"] == []
        assert result["fallback_required"] is True
        assert "average_sentiment" not in str(result)
