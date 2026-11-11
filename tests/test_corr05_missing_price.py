"""Tests for a missing price on a deployed pick (phase 4 CORR-05, D-01, D-02)."""
import json
import logging

import pytest

from tests.test_llm_role_audit import (
    ALLOCATOR_TOOL,
    DRAFT_PHASE,
    FINAL_PHASE,
    critic_payload,
    draft_entry,
    draft_payload,
    flow,  # noqa: F401  (fixture)
    narrative_result,
    prime_draft,
    run_critic,
    run_draft,
    run_final,
    wire_tools,
)
from utils.action_policy_gate import (
    PRICE_UNAVAILABLE_REASON,
    eligible_actions,
    filter_critiques,
    filter_directives,
    price_unavailable_reason,
)
from utils.portfolio_allocator_tool import PortfolioAllocatorTool
from utils.strategy_assembly import (
    PRICE_RULE,
    allocator_payload,
    clamp_actions,
    clamp_warnings,
    eligible_by_ticker,
    policy_context_by_ticker,
    policy_rule,
)

PRICE_TAIL = (
    " Action set to MONITOR by policy: "
    "price unavailable (no current price): only MONITOR or AVOID are allowed."
)


def _make_aaa_priceless(flow):
    """Copy AAA's technical record with no current price (the backstop path of plan 04-01)."""
    technical = flow.state.technical_output
    records = [
        r.model_copy(update={"current_price": None}) if r.ticker == "AAA" else r
        for r in technical.technical_analysis
    ]
    flow.state.technical_output = technical.model_copy(update={"technical_analysis": records})


# ─── the shared price rule ─────────────────────────────────────────────────────

class TestPriceUnavailableReason:
    def test_usable_price_is_none(self):
        assert price_unavailable_reason(99.0) is None
        assert price_unavailable_reason(1) is None

    @pytest.mark.parametrize("bad", [None, 0, 0.0, -1.0, float("nan"), float("inf"), True, "99"])
    def test_unusable_price_has_the_reason(self, bad):
        assert price_unavailable_reason(bad) == PRICE_UNAVAILABLE_REASON == "no current price"

    def test_a_price_error_text_wins(self):
        assert price_unavailable_reason(99.0, "stale quote") == "stale quote"

    def test_empty_error_text_is_ignored(self):
        assert price_unavailable_reason(99.0, "") is None
        assert price_unavailable_reason(None, "") == PRICE_UNAVAILABLE_REASON

    def test_eligible_actions_caps_at_monitor_or_avoid(self):
        reason = price_unavailable_reason(None)
        assert eligible_actions("CURRENT_ENTRY", "conservative", None, reason) == frozenset({"MONITOR", "AVOID"})
        assert eligible_actions("PULLBACK_ENTRY", "aggressive", None, reason) == frozenset({"MONITOR", "AVOID"})


class TestPolicyContext:
    def test_a_priceless_ticker_is_capped_and_the_other_is_not(self, flow):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        to = flow.state.technical_output
        ctx = policy_context_by_ticker(to, {}, "conservative")
        assert ctx["AAA"]["price_data_error"] == "no current price" and ctx["BBB"]["price_data_error"] is None
        eligible = eligible_by_ticker(to, {"AAA": "AVAILABLE", "BBB": "AVAILABLE"}, "conservative")
        assert eligible["AAA"] == frozenset({"MONITOR", "AVOID"})
        assert eligible["BBB"] == frozenset({"WAIT-FOR-ENTRY", "LONG-BUY", "MONITOR", "AVOID"})

    def test_policy_rule_names_the_price(self):
        rule = policy_rule("LONG-BUY", "CURRENT_ENTRY", "conservative", None, price_data_error="no current price")
        assert "price unavailable (no current price): only MONITOR or AVOID are allowed" in rule
        assert PRICE_RULE.format(reason="no current price") in rule

    def test_policy_rule_without_a_price_error_is_unchanged(self):
        rule = policy_rule("WAIT-FOR-ENTRY", "CURRENT_ENTRY", "conservative", None)
        assert "price unavailable" not in rule and "CURRENT_ENTRY" in rule

    def test_policy_rule_ignores_the_price_for_monitor_and_avoid(self):
        assert "price unavailable" not in policy_rule("MONITOR", "CURRENT_ENTRY", "conservative", None, "no current price")

    def test_clamp_actions_uses_the_price_rule(self, flow, caplog):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        to = flow.state.technical_output
        ctx = policy_context_by_ticker(to, {}, "conservative")
        eligible = eligible_by_ticker(to, {}, "conservative")
        from schemas.agent_outputs import PositionNarrative

        pos = PositionNarrative.model_validate(draft_entry("AAA", "LONG-BUY"))
        with caplog.at_level(logging.WARNING):
            [out], [clamp] = clamp_actions([pos], eligible, ctx)
        assert out.action == "MONITOR" and out.rationale.endswith(PRICE_TAIL)
        assert "price unavailable" in clamp["rule"] and "price unavailable" in caplog.text


# ─── the allocator contract ────────────────────────────────────────────────────

def _alloc(stocks, risk_profile="conservative"):
    return json.loads(PortfolioAllocatorTool()._run(json.dumps({"risk_profile": risk_profile, "stocks": stocks})))


class TestAllocatorNullPrice:
    @pytest.mark.parametrize("action", ["MONITOR", "AVOID"])
    @pytest.mark.parametrize("price", [None, "absent"])
    def test_monitor_and_avoid_without_a_price(self, action, price):
        stock = {"ticker": "AAA", "action": action, "composite_score": 70.0}
        if price != "absent":
            stock["current_price"] = None
        result = _alloc([stock])
        assert "error" not in result
        assert result["stocks"][0]["allocation_pct"] == 0.0 and result["stocks"][0]["trade_setup"] is None

    @pytest.mark.parametrize("action", ["LONG-BUY", "WAIT-FOR-ENTRY"])
    @pytest.mark.parametrize("price", [None, "absent", 0, -3.0, True])
    def test_deployed_action_without_a_price_is_an_error(self, action, price):
        stock = {"ticker": "aaa", "action": action, "composite_score": 70.0,
                 "entry_zone_low": 95.0, "entry_zone_high": 100.0}
        if price != "absent":
            stock["current_price"] = price
        result = _alloc([stock])
        assert "LONG-BUY or WAIT-FOR-ENTRY without a current price: AAA" in result["error"]

    def test_long_buy_with_a_price_and_no_zones_falls_back_to_the_price(self):
        result = _alloc([{"ticker": "AAA", "action": "LONG-BUY", "composite_score": 70.0, "current_price": 100.0}])
        setup = result["stocks"][0]["trade_setup"]
        assert (setup["entry_zone_low"], setup["entry_zone_high"]) == (100.0, 100.0)

    def test_a_priceless_monitor_does_not_block_a_priced_buy(self):
        result = _alloc([
            {"ticker": "AAA", "action": "MONITOR", "composite_score": 70.0, "current_price": None},
            {"ticker": "BBB", "action": "LONG-BUY", "composite_score": 60.0, "current_price": 50.0,
             "entry_zone_low": 48.0, "entry_zone_high": 52.0},
        ])
        assert "error" not in result
        assert [s["allocation_pct"] for s in result["stocks"]] == [0.0, 15.0]

    def test_description_states_the_null_rule(self):
        description = PortfolioAllocatorTool().description
        assert "null" in description and "never 0" in description


class TestAllocatorPayload:
    def test_a_missing_price_is_left_out_not_zeroed(self, flow):
        from schemas.agent_outputs import PositionNarrative

        prime_draft(flow)
        _make_aaa_priceless(flow)
        by = {a.ticker: a for a in flow.state.technical_output.technical_analysis}
        positions = [PositionNarrative.model_validate(draft_entry("AAA")), PositionNarrative.model_validate(draft_entry("BBB"))]
        composite = {"AAA": {"composite_score": 70.0}, "BBB": {"composite_score": 40.0}}
        payload = allocator_payload(positions, composite, by, "conservative")
        assert "current_price" not in payload["stocks"][0] and payload["stocks"][1]["current_price"] == 50.0


# ─── end to end, offline: draft, critic, final, finalize ───────────────────────

def _by(output):
    return {p.ticker: p for p in output.positions}


def test_a_priceless_long_buy_is_published_as_monitor_through_every_phase(flow, caplog):
    tools = prime_draft(flow)
    _make_aaa_priceless(flow)
    wire_tools(flow, tools, phase=DRAFT_PHASE)

    with caplog.at_level(logging.WARNING):
        run_draft(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "MONITOR"))))
    aaa = _by(flow.state.draft_output)["AAA"]
    assert aaa.action == "MONITOR" and aaa.allocation_pct == 0.0 and aaa.trade_setup is None
    assert aaa.current_price is None
    assert aaa.rationale.endswith(PRICE_TAIL)
    [clamp] = flow.state.policy_clamps
    assert clamp["ticker"] == "AAA" and clamp["phase"] == DRAFT_PHASE and "price unavailable" in clamp["rule"]
    assert any("AAA" in r.getMessage() and "price unavailable" in r.getMessage() for r in caplog.records
               if r.levelno == logging.WARNING)
    sent = json.loads(tools[ALLOCATOR_TOOL].calls[0]["stocks_json"])
    assert "current_price" not in sent["stocks"][0]

    # Critic: a directive to buy the priceless ticker is dropped before the final phase.
    run_critic(flow, narrative_result(critic_payload(
        revision_directives=["AAA: change action to LONG-BUY because momentum is strong"],
        per_ticker_critiques=[{
            "ticker": "AAA", "severity": "MAJOR", "issue_type": "VAGUE_RATIONALE",
            "finding": "AAA is too cautious for its momentum and the rationale does not say why.",
            "instruction": "AAA: change action to LONG-BUY because momentum is strong.",
        }],
    )))
    gated = json.loads(flow._gated_slim_critique())
    assert gated["revision_directives"] == [] and gated["per_ticker_critiques"] == []

    # Final: the LLM asks for LONG-BUY again; the published position is MONITOR again.
    run_final(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "MONITOR"))))
    final_aaa = _by(flow.state.final_output)["AAA"]
    assert final_aaa.action == "MONITOR" and final_aaa.current_price is None and final_aaa.trade_setup is None
    assert final_aaa.rationale.endswith(PRICE_TAIL)
    assert [(c["ticker"], c["phase"]) for c in flow.state.policy_clamps] == [("AAA", DRAFT_PHASE), ("AAA", FINAL_PHASE)]

    finalized = flow._finalize_and_validate_portfolio(flow.state.final_output.model_dump(mode="json"), "conservative")
    published = {p["ticker"]: p for p in finalized["positions"]}
    assert published["AAA"]["action"] == "MONITOR" and published["AAA"]["current_price"] is None
    assert published["AAA"]["allocation_pct"] == 0.0 and published["AAA"]["trade_setup"] is None
    warnings = clamp_warnings(flow.state.policy_clamps, {t: p["action"] for t, p in published.items()})
    assert warnings and all("price unavailable" in w["message"] for w in warnings)


def test_a_priceless_ticker_is_in_the_critic_gate_context(flow):
    prime_draft(flow)
    _make_aaa_priceless(flow)
    ctx = flow._gate_position_context()
    assert ctx["AAA"]["price_data_error"] == "no current price" and ctx["BBB"]["price_data_error"] is None
    kept, rejected = filter_directives(["AAA: change action to LONG-BUY because x"], ctx)
    assert kept == [] and rejected[0].ticker == "AAA" and "price_data_error" in rejected[0].reason
    kept, rejected = filter_critiques([{"instruction": "AAA: change action to LONG-BUY because x"}], ctx)
    assert kept == [] and len(rejected) == 1
    kept, _ = filter_directives(["AAA: change action to MONITOR because x"], ctx)
    assert kept == ["AAA: change action to MONITOR because x"]


# ─── the final stage: downgrade once, read only the technical record ───────────

from unittest.mock import patch  # noqa: E402

from utils.strategy_assembly import CLAMP_SENTENCE, downgrade_priceless_positions  # noqa: E402


def _structured(*positions):
    return {"sector": "Technology", "risk_profile": "conservative", "positions": list(positions),
            "deployed_pct": 0.0, "reserved_pct": 0.0, "cash_reserve_pct": 100.0, "total_allocated_pct": 0.0}


def _pos(ticker, action="LONG-BUY", **extra):
    pos = {
        "ticker": ticker, "action": action, "composite_score": 70.0, "allocation_pct": 15.0,
        "current_price": 99.0, "rationale": f"{ticker} rationale.", "monitoring_triggers": ["t"],
        "review_frequency": "WEEKLY",
        "trade_setup": {"direction": "LONG-BUY", "entry_zone_low": 99.0, "entry_zone_high": 99.0,
                        "stop_loss": 96.03, "take_profit": 106.5},
    }
    pos.update(extra)
    return pos


def _seed_scores(flow, *tickers):
    flow.state.composite_scores = {t: {"ticker": t, "composite_score": 70.0} for t in tickers}


class TestDowngradePricelessPositions:
    def test_a_priceless_buy_becomes_monitor_with_one_record(self, flow, caplog):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        by = {a.ticker: a for a in flow.state.technical_output.technical_analysis}
        original = _structured(_pos("AAA"), _pos("BBB", current_price=50.0))
        before = json.loads(json.dumps(original))
        with caplog.at_level(logging.WARNING):
            out, clamps = downgrade_priceless_positions(original, by)
        assert original == before, "the input is not mutated"
        aaa, bbb = out["positions"]
        assert aaa["action"] == "MONITOR" and aaa["allocation_pct"] == 0.0 and aaa["trade_setup"] is None
        assert aaa["rationale"] == "AAA rationale." + CLAMP_SENTENCE.format(
            rule="price unavailable (no current price): only MONITOR or AVOID are allowed")
        assert bbb == original["positions"][1]
        [clamp] = clamps
        assert clamp["ticker"] == "AAA" and clamp["from_action"] == "LONG-BUY" and clamp["to_action"] == "MONITOR"
        assert clamp["phase"] == "final_strategy"
        assert clamp["rule"] == "price unavailable (no current price): only MONITOR or AVOID are allowed"
        assert clamp["message"] == f"AAA: final action LONG-BUY set to MONITOR by policy: {clamp['rule']}"
        assert clamp["message"] in caplog.text

    def test_a_priced_buy_and_a_priceless_monitor_are_unchanged(self, flow):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        by = {a.ticker: a for a in flow.state.technical_output.technical_analysis}
        original = _structured(_pos("AAA", "MONITOR", allocation_pct=0.0, trade_setup=None), _pos("BBB", "WAIT-FOR-ENTRY"))
        out, clamps = downgrade_priceless_positions(original, by)
        assert out["positions"] == original["positions"] and clamps == []

    def test_a_ticker_without_a_technical_record_counts_as_priceless(self, flow):
        prime_draft(flow)
        by = {a.ticker: a for a in flow.state.technical_output.technical_analysis}
        out, clamps = downgrade_priceless_positions(_structured(_pos("ZZZ", "WAIT-FOR-ENTRY")), by)
        assert out["positions"][0]["action"] == "MONITOR" and [c["ticker"] for c in clamps] == ["ZZZ"]

    def test_a_second_pass_changes_nothing(self, flow):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        by = {a.ticker: a for a in flow.state.technical_output.technical_analysis}
        once, _ = downgrade_priceless_positions(_structured(_pos("AAA")), by)
        twice, clamps = downgrade_priceless_positions(once, by)
        assert twice == once and clamps == []


class TestFinalizeDowngrade:
    def test_finalize_publishes_monitor_and_records_one_clamp(self, flow, caplog):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        _seed_scores(flow, "AAA", "BBB")
        flow.state.policy_clamps = []
        with caplog.at_level(logging.WARNING):
            out = flow._finalize_and_validate_portfolio(
                _structured(_pos("AAA"), _pos("BBB", "MONITOR", allocation_pct=0.0, trade_setup=None,
                                              current_price=50.0)), "conservative")
        aaa = out["positions"][0]
        assert aaa["action"] == "MONITOR" and aaa["allocation_pct"] == 0.0 and aaa["trade_setup"] is None
        assert [(c["ticker"], c["phase"]) for c in flow.state.policy_clamps] == [("AAA", "final_strategy")]
        assert sum("price unavailable" in r.getMessage() for r in caplog.records) == 1

    def test_the_retry_after_a_failed_validation_does_not_duplicate_the_clamp(self, flow):
        prime_draft(flow)
        _make_aaa_priceless(flow)
        _seed_scores(flow, "AAA", "BBB")
        flow.state.policy_clamps = []
        real = __import__("prospect_ai_flow").validate_bounds
        calls = []

        def fail_once(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return [{"ticker": None, "rule": "forced", "expected": "x", "actual": "y"}]
            return real(*args, **kwargs)

        with patch("prospect_ai_flow.validate_bounds", fail_once):
            out = flow._finalize_and_validate_portfolio(
                _structured(_pos("AAA"), _pos("BBB", "MONITOR", allocation_pct=0.0, trade_setup=None,
                                              current_price=50.0)), "conservative")
        assert len(calls) == 2
        assert out["positions"][0]["action"] == "MONITOR"
        assert len(flow.state.policy_clamps) == 1


class TestRepriceReadsOnlyTheTechnicalRecord:
    def _spy(self):
        sent = []
        real = PortfolioAllocatorTool._run

        def spy(self_, stocks_json):
            sent.append(json.loads(stocks_json))
            return real(self_, stocks_json)

        return sent, patch.object(PortfolioAllocatorTool, "_run", spy)

    def test_a_record_without_zones_prices_from_its_current_price(self, flow):
        prime_draft(flow)
        records = []
        for r in flow.state.technical_output.technical_analysis:
            if r.ticker == "AAA":
                r = r.model_copy(update={
                    "current_price": 108.0,
                    "momentum_analysis": r.momentum_analysis.model_copy(
                        update={"entry_zone_low": None, "entry_zone_high": None}),
                })
            records.append(r)
        flow.state.technical_output = flow.state.technical_output.model_copy(update={"technical_analysis": records})
        _seed_scores(flow, "AAA")
        sent, patcher = self._spy()
        with patcher:
            out = flow._reprice_final_output(_structured(_pos("AAA")), "conservative")
        item = sent[0]["stocks"][0]
        assert item["current_price"] == 108.0 and "entry_zone_low" not in item and "entry_zone_high" not in item
        setup = out["positions"][0]["trade_setup"]
        assert (setup["entry_zone_low"], setup["entry_zone_high"]) == (108.0, 108.0)
        assert setup["stop_loss"] == round(108.0 * 0.97, 2)

    def test_llm_written_price_and_setup_never_reach_the_allocator(self, flow):
        prime_draft(flow)
        _seed_scores(flow, "AAA")
        hostile = _pos("AAA", current_price=1.0, trade_setup={
            "direction": "LONG-BUY", "entry_zone_low": 1.0, "entry_zone_high": 2.0,
            "stop_loss": 0.5, "take_profit": 9.0})
        sent, patcher = self._spy()
        with patcher:
            out = flow._reprice_final_output(_structured(hostile), "conservative")
        item = sent[0]["stocks"][0]
        assert item["current_price"] == 99.0
        assert set(item) == {"ticker", "action", "composite_score", "entry_zone_low", "entry_zone_high", "current_price"}
        record = flow.state.technical_output.technical_analysis[0].momentum_analysis
        assert (item["entry_zone_low"], item["entry_zone_high"]) == (record.entry_zone_low, record.entry_zone_high)
        assert out["positions"][0]["trade_setup"]["entry_zone_low"] == 99.0

    def test_a_priceless_deployed_position_that_bypasses_the_downgrade_fails_closed(self, flow):
        from utils.portfolio_bounds_validator import BoundsViolationError

        prime_draft(flow)
        _make_aaa_priceless(flow)
        _seed_scores(flow, "AAA")
        with pytest.raises(BoundsViolationError) as info:
            flow._reprice_final_output(_structured(_pos("AAA")), "conservative")
        assert "without a current price: AAA" in info.value.violations[0]["actual"]


def test_a_critic_directive_to_buy_a_priceless_ticker_is_rejected_through_the_flow(flow):
    prime_draft(flow)
    _make_aaa_priceless(flow)
    kept, rejected = filter_directives(["AAA: change action to LONG-BUY because momentum is strong"],
                                       flow._gate_position_context())
    assert kept == [] and [r.ticker for r in rejected] == ["AAA"]
