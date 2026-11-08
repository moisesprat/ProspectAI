"""Tests for the news-sentiment tool and its Flow wiring (phase 3.1 D-06, D-08, D-09)."""
import concurrent.futures
import json
import math
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests

import utils.news_sentiment as ns
from prospect_ai_flow import ProspectAIFlow
from tests.test_llm_role_audit import (
    ANTHROPIC_ENV,
    COMPOSITE_TOOL,
    SERPER_TOOL,
    draft_entry,
    draft_payload,
    draft_tools,
    make_task,
    market_tools,
    mkt_entry,
    mkt_payload,
    narrative_entry,
    narrative_payload,
    narrative_result,
    stub_tools,
    tech_narrative_entry,
    tech_payload,
    tech_tools,
    wire_tools,
)
from tests.fake_clock import FakeClock
from tests.test_no_blocking_sleep import _critic, _crew_factory, _json_result
from utils.execution_tracker import ExecutionTracker

TOKEN = "tok-FAKE-1234567890"
DAY_1 = datetime(2026, 11, 8, 10, 30, tzinfo=timezone.utc)
DAY_2 = DAY_1 + timedelta(days=1)


# ─── Fakes ─────────────────────────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def provider_body(symbol, scores, found=None, other=0.99):
    """The recorded Marketaux shape: articles with entities; another company's entity rides along."""
    data = [
        {
            "uuid": f"u{i}", "title": "headline text", "url": "https://news.example.com/a",
            "entities": [
                {"symbol": other_symbol(symbol), "sentiment_score": other},
                {"symbol": symbol, "sentiment_score": score},
            ],
        }
        for i, score in enumerate(scores)
    ]
    n = len(scores) if found is None else found
    return {"data": data, "meta": {"found": n, "returned": len(data), "limit": 3, "page": 1}}


def other_symbol(symbol):
    return "ZZOTHER" if symbol != "ZZOTHER" else "YYOTHER"


class FakeProvider:
    """Installed on requests.get: records (url, params, timeout), answers per requested symbol."""

    def __init__(self, table=None):
        self.table = table or {}
        self.calls = []

    def __call__(self, url, params=None, timeout=None, **kwargs):
        self.calls.append((url, dict(params), timeout))
        answer = self.table.get(params["symbols"], FakeResponse(200, provider_body(params["symbols"], [])))
        if isinstance(answer, Exception):
            raise answer
        return answer


class MiniStore:
    """The least a store may offer: get and item assignment (the plan 03.1-05 contract)."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def __setitem__(self, key, value):
        self.data[key] = value


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(ns.API_KEY_ENV, TOKEN)


def install(monkeypatch, provider):
    monkeypatch.setattr(ns.requests, "get", provider)
    return provider


def tool(cache=None, now=DAY_1):
    return ns.NewsSentimentTool(cache=cache, clock=lambda: now)


# ─── map_sentiment ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("scores, articles, minimum, expected", [
    ([0.2, 0.4], 2, 2, 0.3),
    ([0.2], 1, 2, None),
    ([0.0, 0.0], 2, 2, 0.0),
    (["0.4", True, math.nan], 3, 1, None),
    ([0.9, 1.5], 2, 1, None),
    ([0.2, 0.4], None, 1, None),
    ([], 5, 1, None),
    ([0.1, math.inf, 0.3], 3, 1, 0.2),
    ([-0.0], 1, 1, 0.0),
    ([1 / 3], 1, 1, 0.3333),
    ("0.4", 1, 1, None),
    ([0.4], True, 1, None),
])
def test_map_sentiment(scores, articles, minimum, expected):
    got = ns.map_sentiment(scores, articles, minimum)
    assert got == expected
    if expected == 0.0:
        assert got is not None and math.copysign(1.0, got) == 1.0


def test_cache_key():
    assert ns.cache_key("marketaux", "AAA", "2026-11-08") == "news-sentiment:marketaux:AAA:2026-11-08"


def test_locked_decisions_are_the_module_constants():
    assert (ns.PROVIDER, ns.LOOKBACK_DAYS, ns.MIN_ARTICLES, ns.ARTICLE_COUNT, ns.BATCH, ns.TIME_BUDGET_SECONDS) == (
        "marketaux", 7, 1, "found", "per-ticker", 8,
    )


# ─── Adapter ───────────────────────────────────────────────────────────────────

def test_build_params_puts_the_token_in_params_only():
    url, params = ns.build_params(["BRK.B"], DAY_1 - timedelta(days=7), TOKEN)
    assert url == "https://api.marketaux.com/v1/news/all"
    assert params["api_token"] == TOKEN
    assert params["symbols"] == "BRK-B"
    assert params["published_after"] == "2026-11-01T10:30"
    assert (params["filter_entities"], params["language"], params["limit"]) == ("true", "en", 3)
    assert TOKEN not in url


def test_parse_counts_only_the_requested_symbols_scores():
    body = provider_body("AAA", [0.2, 0.4], found=9)
    assert ns.parse(200, body, ["AAA"]) == {"AAA": {"scores": [0.2, 0.4], "articles": 9}}


def test_parse_matches_dotted_ticker_through_the_hyphen_spelling():
    body = provider_body("BRK-B", [0.5], found=2)
    assert ns.parse(200, body, ["BRK.B"]) == {"BRK.B": {"scores": [0.5], "articles": 2}}


def test_parse_zero_found_is_a_real_no_data_answer():
    assert ns.parse(200, {"data": [], "meta": {"found": 0}}, ["AAA"]) == {"AAA": {"scores": [], "articles": 0}}


def test_parse_drops_unusable_scores():
    body = provider_body("AAA", [0.2, 2.5, None, "0.1", True, math.nan], found=6)
    assert ns.parse(200, body, ["AAA"])["AAA"]["scores"] == [0.2]


def test_parse_multi_symbol_counts_scored_articles():
    body = provider_body("AAA", [0.1, 0.3], found=50)
    got = ns.parse(200, body, ["AAA", "BBB"])
    assert got["AAA"] == {"scores": [0.1, 0.3], "articles": 2}
    assert got["BBB"] == {"scores": [], "articles": 0}


@pytest.mark.parametrize("status, body", [
    (429, {"error": {"code": "rate_limit_reached"}}),
    (402, {"error": {"code": "usage_limit_reached"}}),
    (500, None),
    (200, None),
    (200, []),
    (200, {"data": "x", "meta": {"found": 1}}),
    (200, {"data": []}),
    (200, {"data": [], "meta": {"found": "3"}}),
    (200, {"data": [], "meta": {"found": True}}),
    (200, {"data": [], "meta": {"found": -1}}),
])
def test_parse_other_answers_give_no_observation(status, body):
    assert ns.parse(status, body, ["AAA"]) == {"AAA": None}


# ─── Tool ──────────────────────────────────────────────────────────────────────

def test_no_key_makes_no_request_and_scores_nothing(monkeypatch):
    monkeypatch.delenv(ns.API_KEY_ENV, raising=False)
    provider = install(monkeypatch, FakeProvider())
    store = MiniStore()
    result = tool(store)._run(tickers=["AAA", "BBB"])
    assert result == {
        "provider": "marketaux", "status": "no_key", "stopped_reason": None,
        "scores": {"AAA": None, "BBB": None}, "articles": {"AAA": None, "BBB": None},
        "requests": 0, "cache_hits": 0, "cache_errors": 0,
    }
    assert provider.calls == [] and store.data == {}


def test_blank_key_counts_as_no_key(monkeypatch):
    monkeypatch.setenv(ns.API_KEY_ENV, "   ")
    provider = install(monkeypatch, FakeProvider())
    assert tool()._run(tickers=["AAA"])["status"] == "no_key"
    assert provider.calls == []


def test_first_call_requests_per_ticker_and_maps_scores(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({
        "AAA": FakeResponse(200, provider_body("AAA", [0.2, 0.4], found=7)),
        "BBB": FakeResponse(200, provider_body("BBB", [-0.5], found=1)),
    }))
    result = tool(MiniStore())._run(tickers=["AAA", "BBB"])
    assert result["status"] == "ok" and result["stopped_reason"] is None
    assert result["scores"] == {"AAA": 0.3, "BBB": -0.5}
    assert result["articles"] == {"AAA": 7, "BBB": 1}
    assert (result["requests"], result["cache_hits"]) == (2, 0)
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA", "BBB"]
    assert all(c[2] == 4.0 for c in provider.calls)
    assert all(c[1]["api_token"] == TOKEN for c in provider.calls)


def test_second_lookup_on_the_same_utc_day_makes_no_request(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({
        "AAA": FakeResponse(200, provider_body("AAA", [0.2, 0.4], found=7)),
        "BBB": FakeResponse(200, provider_body("BBB", [-0.5], found=1)),
    }))
    store = MiniStore()
    first = tool(store)._run(tickers=["AAA", "BBB"])
    later_same_day = DAY_1.replace(hour=23, minute=59)
    second = tool(store, now=later_same_day)._run(tickers=["AAA", "BBB"])
    assert len(provider.calls) == 2
    assert second["scores"] == first["scores"]
    assert (second["requests"], second["cache_hits"]) == (0, 2)
    assert sorted(store.data) == [
        "news-sentiment:marketaux:AAA:2026-11-08", "news-sentiment:marketaux:BBB:2026-11-08",
    ]


def test_next_utc_date_misses(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, provider_body("AAA", [0.2], found=1))}))
    store = MiniStore()
    tool(store)._run(tickers=["AAA"])
    result = tool(store, now=DAY_2)._run(tickers=["AAA"])
    assert len(provider.calls) == 2 and result["cache_hits"] == 0
    assert "news-sentiment:marketaux:AAA:2026-11-09" in store.data


def test_the_window_starts_lookback_days_before_now(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider())
    tool()._run(tickers=["AAA"])
    assert provider.calls[0][1]["published_after"] == "2026-11-01T10:30"


def test_no_data_answer_is_cached_and_stays_null(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, {"data": [], "meta": {"found": 0}})}))
    store = MiniStore()
    first = tool(store)._run(tickers=["AAA"])
    second = tool(store)._run(tickers=["AAA"])
    assert first["scores"] == {"AAA": None} and first["articles"] == {"AAA": 0}
    assert second["scores"] == {"AAA": None}
    assert len(provider.calls) == 1
    assert store.data["news-sentiment:marketaux:AAA:2026-11-08"] == {"scores": [], "articles": 0}


def test_minimum_article_rule_is_applied_on_every_read(key, monkeypatch):
    install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, provider_body("AAA", [0.4, 0.2], found=2))}))
    store = MiniStore()
    assert tool(store)._run(tickers=["AAA"])["scores"] == {"AAA": 0.3}
    monkeypatch.setattr(ns, "MIN_ARTICLES", 3)
    again = tool(store)._run(tickers=["AAA"])
    assert again["scores"] == {"AAA": None} and again["cache_hits"] == 1 and again["requests"] == 0
    # The cached value is the observation, not the mapped score.
    assert store.data["news-sentiment:marketaux:AAA:2026-11-08"] == {"scores": [0.4, 0.2], "articles": 2}


@pytest.mark.parametrize("failure", [
    requests.ConnectionError(f"HTTPSConnectionPool: /v1/news/all?api_token={TOKEN}"),
    requests.Timeout(f"read timed out api_token={TOKEN}"),
    FakeResponse(429, {"error": {"code": "rate_limit_reached"}}),
    FakeResponse(402, {"error": {"code": "usage_limit_reached"}}),
    FakeResponse(500, None),
    FakeResponse(200, ValueError(f"bad json {TOKEN}")),
    FakeResponse(200, {"unexpected": "shape"}),
])
def test_request_error_is_null_and_writes_nothing(key, monkeypatch, caplog, failure):
    install(monkeypatch, FakeProvider({"AAA": failure}))
    store = MiniStore()
    with caplog.at_level("DEBUG"):
        result = tool(store)._run(tickers=["AAA"])
    assert result["scores"] == {"AAA": None} and result["articles"] == {"AAA": None}
    assert result["requests"] == 1
    assert store.data == {}
    assert TOKEN not in caplog.text and "api_token" not in caplog.text and "/v1/news" not in caplog.text


def test_one_failing_ticker_does_not_stop_the_others(key, monkeypatch):
    install(monkeypatch, FakeProvider({
        "AAA": requests.ConnectionError("down"),
        "BBB": FakeResponse(200, provider_body("BBB", [0.6], found=1)),
    }))
    result = tool(MiniStore())._run(tickers=["AAA", "BBB"])
    assert result["scores"] == {"AAA": None, "BBB": 0.6} and result["requests"] == 2


@pytest.mark.parametrize("bad", [
    "0.3", [0.3], {"scores": [0.3]}, {"scores": [0.3], "articles": -1}, {"scores": [0.3], "articles": True},
    {"scores": [0.3], "articles": 1.5}, {"scores": [2.0], "articles": 1}, {"scores": [math.nan], "articles": 1},
    {"scores": ["0.3"], "articles": 1}, {"scores": [True], "articles": 1}, {"scores": "0.3", "articles": 1},
    {"articles": 1},
])
def test_malformed_cached_value_is_a_miss(key, monkeypatch, bad):
    provider = install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, provider_body("AAA", [0.5], found=1))}))
    store = MiniStore()
    store.data["news-sentiment:marketaux:AAA:2026-11-08"] = bad
    result = tool(store)._run(tickers=["AAA"])
    assert result["scores"] == {"AAA": 0.5} and len(provider.calls) == 1
    assert store.data["news-sentiment:marketaux:AAA:2026-11-08"] == {"scores": [0.5], "articles": 1}


def test_works_without_a_store(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, provider_body("AAA", [0.5], found=1))}))
    t = tool(None)
    assert t._run(tickers=["AAA"])["scores"] == {"AAA": 0.5}
    t._run(tickers=["AAA"])
    assert len(provider.calls) == 2


def test_a_failing_store_degrades_to_a_miss(key, monkeypatch, caplog):
    class BrokenStore:
        def get(self, key):
            raise OSError("store down")

        def __setitem__(self, key, value):
            raise OSError("store down")

    install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, provider_body("AAA", [0.5], found=1))}))
    with caplog.at_level("WARNING"):
        result = tool(BrokenStore())._run(tickers=["AAA"])
    assert result["scores"] == {"AAA": 0.5}
    assert "OSError" in caplog.text and "store down" not in caplog.text


def test_invalid_and_repeated_tickers_are_skipped(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider())
    result = tool()._run(tickers=["aaa", " AAA ", "bad ticker!", "TOOLONGX", "", None, 7, "BRK.B"])
    assert list(result["scores"]) == ["AAA", "BRK.B"]
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA", "BRK-B"]


def test_non_list_tickers_means_no_lookup(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider())
    assert tool()._run(tickers="AAA")["scores"] == {}
    assert provider.calls == []


def test_the_token_never_appears_in_the_result_or_the_store(key, monkeypatch):
    install(monkeypatch, FakeProvider({"AAA": FakeResponse(200, provider_body("AAA", [0.5], found=1))}))
    store = MiniStore()
    result = tool(store)._run(tickers=["AAA"])
    assert TOKEN not in json.dumps(result) and TOKEN not in json.dumps(store.data)


def test_multi_symbol_mode_sends_one_request_for_all_misses(key, monkeypatch):
    monkeypatch.setattr(ns, "BATCH", "multi-symbol")
    provider = install(monkeypatch, FakeProvider({
        "AAA,BBB": FakeResponse(200, provider_body("AAA", [0.2, 0.4], found=40)),
    }))
    result = tool(MiniStore())._run(tickers=["AAA", "BBB"])
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA,BBB"]
    assert result["requests"] == 1
    assert result["scores"] == {"AAA": 0.3, "BBB": None}
    assert result["articles"] == {"AAA": 2, "BBB": 0}


def test_tool_is_a_crewai_tool_with_the_documented_contract():
    t = ns.NewsSentimentTool()
    assert t.name == "lookup_news_sentiment"
    assert "tickers" in t.description and "null" in t.description


# ─── Failure containment (D-07, plan 03.1-09) ──────────────────────────────────

SECRET = "tok-SECRET-123"
SECRET_URL = f"https://api.marketaux.com/v1/news/all?api_token={SECRET}&symbols=AAA"
EMPTY_ANSWER = {"data": [], "meta": {"found": 0}}


def answer(symbol, score=0.2):
    return FakeResponse(200, provider_body(symbol, [score], found=1))


@pytest.mark.parametrize("status, reason", [
    (402, "quota"), (429, "rate_limited"), (401, "access_denied"), (403, "access_denied"),
])
def test_a_refusal_mid_run_stops_the_lookup_and_nulls_the_rest(key, monkeypatch, caplog, status, reason):
    provider = install(monkeypatch, FakeProvider({
        "AAA": answer("AAA", 0.4),
        "BBB": FakeResponse(status, {"error": {"code": "usage_limit_reached"}}),
        "CCC": answer("CCC", 0.1),
    }))
    store = MiniStore()
    with caplog.at_level("WARNING"):
        result = tool(store)._run(tickers=["AAA", "BBB", "CCC"])
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA", "BBB"]
    assert (result["status"], result["stopped_reason"], result["requests"]) == ("stopped", reason, 2)
    assert result["scores"] == {"AAA": 0.4, "BBB": None, "CCC": None}
    assert sorted(store.data) == ["news-sentiment:marketaux:AAA:2026-11-08"]
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1 and str(status) in warnings[0]


def test_a_cached_pick_is_still_scored_after_the_provider_refuses(key, monkeypatch):
    store = MiniStore()
    store.data["news-sentiment:marketaux:CCC:2026-11-08"] = {"scores": [0.5], "articles": 4}
    provider = install(monkeypatch, FakeProvider({"AAA": FakeResponse(429, None)}))
    result = tool(store)._run(tickers=["AAA", "BBB", "CCC"])
    assert result["scores"] == {"AAA": None, "BBB": None, "CCC": 0.5}
    assert (result["stopped_reason"], len(provider.calls), result["cache_hits"]) == ("rate_limited", 1, 1)


def test_two_consecutive_timeouts_stop_with_reason_failures(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({
        "AAA": requests.Timeout("slow"), "BBB": requests.Timeout("slow"), "CCC": answer("CCC"),
    }))
    store = MiniStore()
    result = tool(store)._run(tickers=["AAA", "BBB", "CCC"])
    assert (result["status"], result["stopped_reason"], result["requests"]) == ("stopped", "failures", 2)
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA", "BBB"]
    assert result["scores"] == {"AAA": None, "BBB": None, "CCC": None} and store.data == {}


def test_a_server_error_followed_by_a_success_keeps_going(key, monkeypatch):
    install(monkeypatch, FakeProvider({
        "AAA": FakeResponse(503, None), "BBB": answer("BBB", 0.6), "CCC": FakeResponse(500, None),
        "DDD": answer("DDD", -0.2),
    }))
    result = tool(MiniStore())._run(tickers=["AAA", "BBB", "CCC", "DDD"])
    assert (result["status"], result["stopped_reason"], result["requests"]) == ("ok", None, 4)
    assert result["scores"] == {"AAA": None, "BBB": 0.6, "CCC": None, "DDD": -0.2}


def test_the_wall_budget_caps_every_request_and_stops_the_lookup(key, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(ns, "time", clock)
    monkeypatch.setattr(ns.requests, "get", clock.get_side_effect(
        lambda i, u: FakeResponse(200, EMPTY_ANSWER), latency=3.0,
    ))
    result = tool(MiniStore())._run(tickers=["AAA", "BBB", "CCC", "DDD", "EEE"])
    assert ns.TIME_BUDGET_SECONDS == 8
    assert clock.timeouts == [4.0, 4.0, 2.0]  # the third request only gets what is left
    assert clock.now <= ns.TIME_BUDGET_SECONDS
    assert (result["status"], result["stopped_reason"], result["requests"]) == ("stopped", "budget", 3)
    assert clock.sleeps == []


def test_the_module_never_sleeps(key, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(ns, "time", clock)
    monkeypatch.setattr(ns.requests, "get", clock.get_side_effect(FakeResponse(503, None), latency=0.1))
    tool()._run(tickers=["AAA", "BBB", "CCC"])
    assert clock.sleeps == [] and not any(kind == "sleep" for kind, _ in clock.events)


class HungStore:
    """A store whose calls block until the test releases them."""

    def __init__(self):
        self.release = threading.Event()

    def get(self, key):
        self.release.wait(10)

    def __setitem__(self, key, value):
        self.release.wait(10)


@pytest.fixture
def hung_store():
    store = HungStore()
    yield store
    store.release.set()


def test_a_stalled_store_is_a_miss_and_is_counted(key, monkeypatch, caplog, hung_store):
    monkeypatch.setattr(ns, "CACHE_OP_TIMEOUT_SECONDS", 0.05)
    install(monkeypatch, FakeProvider({"AAA": answer("AAA", 0.5)}))
    with caplog.at_level("WARNING"):
        result = tool(hung_store)._run(tickers=["AAA"])
    assert result["scores"] == {"AAA": 0.5} and result["cache_hits"] == 0
    assert result["cache_errors"] == 2  # one timed-out read, one timed-out write
    assert "TimeoutError" in caplog.text


def test_a_raising_store_is_a_miss_and_is_counted(key, monkeypatch):
    class BrokenStore:
        def get(self, key):
            raise OSError(f"down {SECRET}")

        def __setitem__(self, key, value):
            raise OSError(f"down {SECRET}")

    install(monkeypatch, FakeProvider({"AAA": answer("AAA", 0.5), "BBB": answer("BBB", 0.1)}))
    result = tool(BrokenStore())._run(tickers=["AAA", "BBB"])
    assert result["scores"] == {"AAA": 0.5, "BBB": 0.1}
    assert result["cache_errors"] == 4


def test_a_healthy_store_has_no_cache_errors(key, monkeypatch):
    install(monkeypatch, FakeProvider({"AAA": answer("AAA", 0.5)}))
    assert tool(MiniStore())._run(tickers=["AAA"])["cache_errors"] == 0


def test_cache_op_timeout_is_derived_from_the_measured_modal_dict_latency():
    slower_ms = max(ns.MODAL_DICT_PUT_MEDIAN_MS, ns.MODAL_DICT_GET_MEDIAN_MS)
    expected = min(2.0, max(1.0, math.ceil(20 * slower_ms / 1000 * 10) / 10))
    assert ns.CACHE_OP_TIMEOUT_SECONDS == expected
    assert 1.0 <= ns.CACHE_OP_TIMEOUT_SECONDS <= 2.0
    assert ns.MODAL_DICT_PUT_MEDIAN_MS > 0 and ns.MODAL_DICT_GET_MEDIAN_MS > 0


class _StalledFuture:
    """A store call that never answers: waiting for it costs the full wait on the fake clock."""

    def __init__(self, clock):
        self.clock = clock

    def result(self, timeout=None):
        self.clock.now += timeout
        raise concurrent.futures.TimeoutError()

    def cancel(self):
        return True


class _StalledPool:
    def __init__(self, clock):
        self.clock = clock

    def submit(self, fn, *args, **kwargs):
        return _StalledFuture(self.clock)


def test_five_picks_with_a_store_that_never_answers_still_finish_within_the_budget(key, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(ns, "time", clock)
    monkeypatch.setattr(ns, "_CACHE_POOL", _StalledPool(clock))
    monkeypatch.setattr(ns.requests, "get", clock.get_side_effect(
        lambda i, u: FakeResponse(200, EMPTY_ANSWER), latency=0.0,
    ))
    result = tool(MiniStore())._run(tickers=["AAA", "BBB", "CCC", "DDD", "EEE"])
    assert clock.now <= ns.TIME_BUDGET_SECONDS + 1e-9
    assert result["cache_errors"] >= 5 and result["status"] in {"ok", "stopped"}
    if result["status"] == "stopped":
        assert result["stopped_reason"] == "budget"


@pytest.mark.parametrize("failure", [
    requests.ConnectionError(f"HTTPSConnectionPool(host='api.marketaux.com'): {SECRET_URL}"),
    requests.Timeout(f"Read timed out. {SECRET_URL}"),
    RuntimeError(f"boom {SECRET_URL}"),
    FakeResponse(200, ValueError(f"bad json {SECRET_URL}")),
    FakeResponse(402, {"error": {"message": SECRET_URL}}),
    FakeResponse(429, {"error": {"message": SECRET_URL}}),
    FakeResponse(500, SECRET_URL),
])
def test_no_failure_leaks_the_token_or_an_address(monkeypatch, caplog, failure):
    monkeypatch.setenv(ns.API_KEY_ENV, SECRET)
    install(monkeypatch, FakeProvider({"AAA": failure, "BBB": failure}))

    class LeakyStore(MiniStore):
        def get(self, key):
            raise OSError(f"store down {SECRET_URL}")

    cache = MiniStore()
    with caplog.at_level("DEBUG"):
        result = tool(LeakyStore())._run(tickers=["AAA", "BBB"])
        tool(cache)._run(tickers=["AAA", "BBB"])
    for text in (caplog.text, json.dumps(result), json.dumps(cache.data)):
        assert SECRET not in text and "http" not in text
    assert "api_token" not in caplog.text


def test_a_leaky_exception_through_the_flow_leaves_the_token_out_of_steps_and_metrics(monkeypatch, caplog):
    monkeypatch.setenv(ns.API_KEY_ENV, SECRET)
    install(monkeypatch, FakeProvider(
        {"AAA": requests.ConnectionError(SECRET_URL), "BBB": requests.ConnectionError(SECRET_URL)},
    ))
    steps, store = [], {}
    with caplog.at_level("DEBUG"):
        flow, _ = run_six_phases(store, None, step_callback=lambda index, step: steps.append(step))
    assert flow.state.final_output is not None
    news_steps = [s for s in steps if s.tool == ns.TOOL_NAME]
    assert len(news_steps) == 1
    metrics = json.dumps(flow._tracker.to_dict(), default=str)
    published = flow.state.final_output.model_dump_json()
    for text in (news_steps[0].tool_input, news_steps[0].log, caplog.text, metrics, published, json.dumps(store)):
        assert SECRET not in text and "api_token" not in text
    assert "http" not in news_steps[0].tool_input and "http" not in json.dumps(store)


def test_full_run_with_a_refused_quota_completes_with_null_sentiment(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider({
        "AAA": FakeResponse(402, {"error": {"code": "usage_limit_reached"}}),
        "BBB": answer("BBB"),
    }))
    store = {}
    flow, tools = run_six_phases(store, None)

    assert flow.state.final_output is not None
    market = flow.state.market_output
    assert market.sentiment_available is False
    assert [c.average_sentiment for c in market.candidate_stocks] == [None, None]
    sent = json.loads(tools[COMPOSITE_TOOL].calls[0]["stocks_json"])
    assert [s["average_sentiment"] for s in sent] == [None]
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA"]  # no request after the refusal
    assert store == {}


# ─── End to end through the six-phase Flow ─────────────────────────────────────

def run_six_phases(store, provider_table, step_callback=None):
    """A full offline kickoff for Technology with the real news tool; returns (flow, tools)."""
    with patch.dict("os.environ", ANTHROPIC_ENV), patch("prospect_ai_flow.TaskFactory") as mock_factory:
        mock_factory.return_value = type(mock_factory.return_value)()
        flow = ProspectAIFlow(step_callback=step_callback, sentiment_cache=store)
        flow._tracker = ExecutionTracker()
        flow._tracker.start()
        flow._factory.build_task.return_value = make_task()
        tools = {
            **stub_tools(), **tech_tools(), **draft_tools(),
            **market_tools(),
            ns.TOOL_NAME: ns.NewsSentimentTool(cache=store, clock=lambda: DAY_1),
        }
        wire_tools(flow, tools, phase="market_analysis")
        results = {
            0: narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))),
            1: narrative_result(tech_payload(tech_narrative_entry("AAA"))),
            2: narrative_result(narrative_payload(narrative_entry("AAA"))),
            3: narrative_result(draft_payload(draft_entry("AAA"))),
            4: _json_result(_critic()),
            5: narrative_result(draft_payload(draft_entry("AAA"))),
        }
        with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, set())), \
             patch.object(flow, "_slim_draft", return_value=""), \
             patch.object(flow, "_critic_reference_table", return_value=""), \
             patch.object(flow, "_gated_slim_critique", return_value=""):
            flow.kickoff(inputs={"sector": "Technology", "today": "2026-04-29", "risk_profile": "conservative"})
    return flow, tools


PROVIDER_TABLE = {
    "AAA": FakeResponse(200, provider_body("AAA", [0.2, 0.4], found=12)),
    "BBB": FakeResponse(200, provider_body("BBB", [-0.5], found=3)),
}


def test_full_run_publishes_the_provider_scores(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider(PROVIDER_TABLE))
    store = {}
    flow, tools = run_six_phases(store, PROVIDER_TABLE)

    assert flow.state.final_output is not None
    market = flow.state.market_output
    assert market.sentiment_available is True
    assert {c.ticker: c.average_sentiment for c in market.candidate_stocks} == {"AAA": 0.3, "BBB": -0.5}
    # The draft composite tool received the measured sentiment.
    sent = json.loads(tools[COMPOSITE_TOOL].calls[0]["stocks_json"])
    assert [(s["ticker"], s["average_sentiment"]) for s in sent] == [("AAA", 0.3)]
    # One request per pick, none from any other phase, and the store now holds both observations.
    assert [c[1]["symbols"] for c in provider.calls] == ["AAA", "BBB"]
    assert sorted(store) == [
        "news-sentiment:marketaux:AAA:2026-11-08", "news-sentiment:marketaux:BBB:2026-11-08",
    ]
    # The key never reaches the published report or the stored cache.
    assert TOKEN not in flow.state.final_output.model_dump_json()
    assert TOKEN not in json.dumps(store)


def test_full_run_with_no_key_publishes_null_sentiment(monkeypatch):
    monkeypatch.delenv(ns.API_KEY_ENV, raising=False)
    provider = install(monkeypatch, FakeProvider(PROVIDER_TABLE))
    store = {}
    flow, tools = run_six_phases(store, PROVIDER_TABLE)

    assert flow.state.final_output is not None
    market = flow.state.market_output
    assert market.sentiment_available is False
    assert [c.average_sentiment for c in market.candidate_stocks] == [None, None]
    sent = json.loads(tools[COMPOSITE_TOOL].calls[0]["stocks_json"])
    assert [s["average_sentiment"] for s in sent] == [None]
    assert provider.calls == [] and store == {}


def test_full_run_reuses_the_store_without_a_second_request(key, monkeypatch):
    provider = install(monkeypatch, FakeProvider(PROVIDER_TABLE))
    store = {}
    run_six_phases(store, PROVIDER_TABLE)
    assert len(provider.calls) == 2
    flow, _ = run_six_phases(store, PROVIDER_TABLE)
    assert len(provider.calls) == 2
    assert flow.state.market_output.sentiment_available is True


# ─── The run's sentiment_lookup record (plan 03.1-09, Task 2) ──────────────────

LOOKUP_KEYS = {"provider", "status", "stopped_reason", "scores", "articles", "requests", "cache_hits", "cache_errors"}


def test_a_scored_run_records_the_lookup(key, monkeypatch):
    install(monkeypatch, FakeProvider(PROVIDER_TABLE))
    flow, _ = run_six_phases({}, PROVIDER_TABLE)
    record = flow._tracker.to_dict()["sentiment_lookup"]
    assert set(record) == LOOKUP_KEYS
    assert (record["provider"], record["status"], record["stopped_reason"]) == ("marketaux", "ok", None)
    assert record["scores"] == {"AAA": 0.3, "BBB": -0.5} and record["articles"] == {"AAA": 12, "BBB": 3}
    assert (record["requests"], record["cache_hits"], record["cache_errors"]) == (2, 0, 0)
    assert flow._tracker.to_dict()["metrics_version"] == 2


def test_a_stopped_run_records_why(key, monkeypatch):
    install(monkeypatch, FakeProvider({"AAA": FakeResponse(429, {"error": {"code": "rate_limit_reached"}})}))
    flow, _ = run_six_phases({}, None)
    record = flow._tracker.to_dict()["sentiment_lookup"]
    assert (record["status"], record["stopped_reason"], record["requests"]) == ("stopped", "rate_limited", 1)
    assert record["scores"] == {"AAA": None, "BBB": None}


def test_an_unkeyed_run_records_no_key(monkeypatch):
    monkeypatch.delenv(ns.API_KEY_ENV, raising=False)
    install(monkeypatch, FakeProvider(PROVIDER_TABLE))
    flow, _ = run_six_phases({}, None)
    record = flow._tracker.to_dict()["sentiment_lookup"]
    assert (record["status"], record["requests"]) == ("no_key", 0)


def test_a_raising_tool_records_the_fixed_error_record(key, monkeypatch):
    def boom(self, tickers):
        raise RuntimeError(f"tool exploded {SECRET_URL}")

    monkeypatch.setattr(ns.NewsSentimentTool, "_run", boom)
    flow, _ = run_six_phases({}, None)
    assert flow.state.final_output is not None
    record = flow._tracker.to_dict()["sentiment_lookup"]
    assert record == {
        "provider": "marketaux", "status": "error", "stopped_reason": "tool_error",
        "scores": {}, "articles": {}, "requests": 0, "cache_hits": 0, "cache_errors": 0,
    }


def test_the_lookup_record_holds_no_token_and_no_address(monkeypatch):
    monkeypatch.setenv(ns.API_KEY_ENV, SECRET)
    install(monkeypatch, FakeProvider({"AAA": requests.ConnectionError(SECRET_URL), "BBB": FakeResponse(402, SECRET_URL)}))
    flow, _ = run_six_phases({}, None)
    text = json.dumps(flow._tracker.to_dict()["sentiment_lookup"])
    assert SECRET not in text and "http" not in text and "api_token" not in text


def test_no_grounded_picks_records_a_skipped_lookup():
    import asyncio

    with patch.dict("os.environ", ANTHROPIC_ENV), patch("prospect_ai_flow.TaskFactory"):
        flow = ProspectAIFlow()
        flow._tracker = ExecutionTracker()
        assert asyncio.run(flow._news_sentiment("market_analysis", [])) == {}
    record = flow._tracker.to_dict()["sentiment_lookup"]
    assert (record["status"], record["stopped_reason"], record["requests"]) == ("skipped", "no_picks", 0)
