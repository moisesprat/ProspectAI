"""Tests for the size caps on search text entering prompts (phase 4 CORR-09, D-07)."""
import json

import pytest

from tests import test_repo_hygiene
from tests.test_llm_role_audit import (  # noqa: F401  (flow is a fixture)
    MARKET_PHASE, SERPER_TOOL, SerperSequence, flow, mkt_entry, mkt_payload, narrative_result,
    run_market, wire_tools,
)
from utils import market_records
from utils.market_records import (
    MAX_CORPUS_TEXT_CHARS, MAX_HOST_CHARS, MAX_RECORD_BYTES, MAX_SNIPPETS, SNIPPET_CHARS,
    build_market_corpus, corpus_record, market_narrative_context,
)

HEADER = "=== Market Data (collected by the pipeline) ==="
HOSTILE_FILLERS = {
    "ascii": "word see https://tracker.example.com/path?token=SECRET and www.evil.example/x ",
    "quotes": '"\\ ',
    "emoji": "\U0001F600 ",
}


def _hostile_list(tag, filler, host_chars=1000):
    """One Serper answer: 50 results, titles and snippets of 5000 characters, hosts of ``host_chars``."""
    text = (f"AAA {tag} " + filler * 5000)[:5000]
    return {"organic": [
        {
            "title": text,
            "snippet": text,
            "link": f"https://{'h' * (host_chars - 20)}{tag}{i:04d}.example.com/a?q=1",
        }
        for i in range(50)
    ]}


def _hostile_answer(kind):
    return [_hostile_list(tag, HOSTILE_FILLERS[kind]) for tag in ("p", "q", "r")]


def _decoded_totals(snippets):
    return (
        sum(len(s["text"]) for s in snippets),
        max((len(s["host"]) for s in snippets), default=0),
    )


def test_cap_constants_are_pinned():
    assert (MAX_SNIPPETS, SNIPPET_CHARS, MAX_CORPUS_TEXT_CHARS, MAX_RECORD_BYTES, MAX_HOST_CHARS) == (
        20, 300, 6000, 8192, 253,
    )


@pytest.mark.parametrize("kind", sorted(HOSTILE_FILLERS))
def test_hostile_corpus_stays_within_the_caps(kind):
    corpus = build_market_corpus(_hostile_answer(kind), "Technology")
    snippets = corpus["snippets"]
    assert 0 < len(snippets) <= MAX_SNIPPETS
    assert all(len(s["text"]) <= SNIPPET_CHARS for s in snippets)
    text_total, longest_host = _decoded_totals(snippets)
    assert text_total <= MAX_CORPUS_TEXT_CHARS
    assert longest_host == MAX_HOST_CHARS
    assert not any("http" in s["text"].lower() or "www." in s["text"].lower() for s in snippets)
    assert not any("SECRET" in s["text"] for s in snippets)
    record = corpus_record(corpus)
    assert len(json.dumps(record).encode("utf-8")) <= MAX_RECORD_BYTES


def test_host_is_cut_to_the_dns_maximum_and_a_normal_host_is_unchanged():
    long_host = "x" * 1000 + ".example.com"
    answer = {"organic": [
        {"title": "AAA one", "snippet": "", "link": f"https://{long_host}/a"},
        {"title": "AAA two", "snippet": "", "link": "https://news1.example.com/a/b?q=1"},
    ]}
    hosts = [s["host"] for s in build_market_corpus(answer, "Technology")["snippets"]]
    assert hosts[0] == long_host[:MAX_HOST_CHARS] and len(hosts[0]) == MAX_HOST_CHARS
    assert hosts[1] == "news1.example.com"


def test_narrative_context_has_only_the_pinned_keys():
    corpus = build_market_corpus(_hostile_answer("ascii"), "Technology")
    body = json.loads(market_narrative_context(corpus))
    assert set(body) == {"source", "search_results", "note"}
    assert all(set(s) == {"text", "host"} for s in body["search_results"])


@pytest.mark.parametrize("kind", sorted(HOSTILE_FILLERS))
def test_prompt_context_is_bounded_end_to_end_through_the_market_phase(flow, kind):
    answers = _hostile_answer(kind)
    tools = {SERPER_TOOL: SerperSequence(*answers)}
    wire_tools(flow, tools, phase=MARKET_PHASE)
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    ctx = flow._factory.build_task.call_args_list[0].args[3]
    header, _, body_text = ctx.partition("\n")
    assert header == HEADER
    body = json.loads(body_text)
    assert set(body) == {"source", "search_results", "note"}
    assert body["source"] == "serper"
    results = body["search_results"]
    assert 0 < len(results) <= MAX_SNIPPETS
    text_total, longest_host = _decoded_totals(results)
    assert text_total <= MAX_CORPUS_TEXT_CHARS
    assert longest_host <= MAX_HOST_CHARS
    # worst case: every text character is a non-BMP one that json.dumps writes as 12 characters
    assert len(ctx) <= 12 * (MAX_CORPUS_TEXT_CHARS + MAX_SNIPPETS * MAX_HOST_CHARS) + 2000


def test_no_other_source_text_reaches_a_prompt():
    # the Reddit source is gone (hygiene guard) and the market corpus is the only search text
    test_repo_hygiene.test_no_reddit_source_left()
    assert not hasattr(market_records, "reddit_context")
