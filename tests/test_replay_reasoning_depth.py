"""Offline tests for scripts/replay_reasoning_depth.py (phase 4 SPEC-01, D-08, D-09)."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from config.config import AGENT_MODEL_ENV_KEYS
from prospect_ai_flow import ProspectAIFlow

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "replay_reasoning_depth.py"
SENTINEL = "sk-ant-SENTINEL-KEY-do-not-print"


def _load():
    spec = importlib.util.spec_from_file_location("replay_reasoning_depth", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def replay(monkeypatch):
    """The script module with a sentinel key, no model overrides and dotenv loading disabled."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL)
    for name in ("MODEL", "MODEL_PROVIDER", "ANTHROPIC_MODEL", "OLLAMA_MODEL",
                 "OLLAMA_BASE_URL", *AGENT_MODEL_ENV_KEYS.values()):
        monkeypatch.delenv(name, raising=False)
    mod = _load()
    monkeypatch.setattr(mod, "load_dotenv", lambda *args, **kwargs: False)
    return mod


# ─── Canned crew answers ───────────────────────────────────────────────────────

RATIONALE = (
    "Momentum is strong and the RSI trend is constructive, but the valuation is stretched "
    "and the growth outlook is declining, so the quality of the business is a concern here."
)


def crew_result(payload):
    """A crew result carrying ``payload`` as raw JSON (parsed by extract_model)."""
    task_out = SimpleNamespace(pydantic=None, json_dict=None)
    return SimpleNamespace(raw=json.dumps(payload), tasks_output=[task_out], token_usage=MagicMock())


def narrative(ticker, action, rationale=RATIONALE):
    return crew_result({
        "positions": [{
            "ticker": ticker, "action": action, "rationale": rationale,
            "monitoring_triggers": [f"{ticker} closes below its 50-day average"],
            "review_frequency": "WEEKLY",
        }],
        "overall_strategy": "o" * 120,
    })


def critic(ticker, severity="MAJOR"):
    return crew_result({
        "sector": "Technology", "risk_profile": "conservative",
        "draft_assessment": "The draft leans on momentum while the fundamentals point the other way. " * 2,
        "per_ticker_critiques": [{
            "ticker": ticker, "severity": severity, "issue_type": "REASONING_GAP",
            "finding": f"{ticker} rationale does not weigh the expensive valuation against momentum.",
            "instruction": f"{ticker}: explain how the valuation and declining growth were weighed.",
        }],
        "portfolio_level_issues": [], "revision_directives": [], "approved_positions": [],
    })


def install_crew(monkeypatch, *results, **kwargs):
    """Patch ProspectAIFlow._make_crew so every kickoff answers from ``results``."""
    akickoff = AsyncMock(side_effect=list(results)) if results else AsyncMock(**kwargs)
    crew = MagicMock()
    crew.akickoff = akickoff
    monkeypatch.setattr(ProspectAIFlow, "_make_crew", lambda self, task, index: crew)
    return akickoff


def conflict_answers(final_action="LONG-BUY"):
    ticker = _load().SEED["conflict"]["ticker"]
    return [narrative(ticker, "LONG-BUY"), critic(ticker), narrative(ticker, final_action)]


# ─── The conflict case ─────────────────────────────────────────────────────────

def test_conflict_case_is_valid_graded_weak_and_long_buy_eligible(replay):
    case = replay.build_case("conflict")
    technical = case.technical.technical_analysis[0]
    momentum = technical.momentum_analysis
    assert case.name == "conflict" and case.synthetic is True
    assert technical.ticker == case.ticker == replay.SEED["conflict"]["ticker"]
    assert technical.current_price == replay.SEED["conflict"]["price"]
    assert momentum.overall_signal == "BULLISH" and momentum.momentum_score == 8
    assert momentum.entry_zone_status == "CURRENT_ENTRY"
    assert momentum.entry_zone_low <= technical.current_price <= momentum.entry_zone_high
    rating = case.fundamental.fundamental_analysis[0].fundamental_rating
    assert (rating.valuation, rating.quality, rating.growth) == ("VERY_EXPENSIVE", "Low", "Declining")
    assert case.fundamental.fundamental_analysis[0].data_status == "ok"

    flow = ProspectAIFlow()
    eligible = replay.preflight(case, flow)
    assert flow._fundamentals_status_by_ticker() == {case.ticker: "AVAILABLE"}
    assert "LONG-BUY" in eligible and "WAIT-FOR-ENTRY" not in eligible


def test_unknown_case_name_is_rejected(replay):
    with pytest.raises(ValueError):
        replay.build_case("nope")


def test_conflict_pass_writes_complete_evidence(replay, monkeypatch, tmp_path):
    akickoff = install_crew(monkeypatch, *conflict_answers())
    case = replay.build_case("conflict")
    evidence = replay.run_pass(case, tmp_path, ProspectAIFlow())

    assert akickoff.await_count == 3
    path = tmp_path / "pass-1-conflict.json"
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == evidence
    ledger = [json.loads(line) for line in (tmp_path / "passes.jsonl").read_text().splitlines()]
    assert [(e["pass"], e["case"]) for e in ledger] == [(1, "conflict")]
    assert replay.passes_used(tmp_path) == 1

    assert evidence["case"] == "conflict" and evidence["pass"] == 1
    assert evidence["max_passes"] == 6 and evidence["synthetic"] is True
    assert evidence["seed"]["ticker"] == case.ticker and evidence["seed"]["price"] == case.price
    assert set(evidence["models"]) == set(replay.PHASES)
    assert all(evidence["models"][phase] for phase in replay.PHASES)
    assert "LONG-BUY" in evidence["eligible_actions"]
    assert evidence["draft"]["action"] == "LONG-BUY" and evidence["draft"]["rationale"].startswith("Momentum")
    assert evidence["final"]["action"] == "LONG-BUY" and "valuation" in evidence["final"]["rationale"]
    critiques = evidence["critic"]["critiques"]
    assert [(c["severity"], c["issue_type"]) for c in critiques] == [("MAJOR", "REASONING_GAP")]
    assert "finding" in critiques[0]
    published = evidence["published"]
    assert published["action"] == "LONG-BUY"
    assert published["current_price"] == case.price
    assert published["allocation_pct"] > 0 and published["trade_setup"] is not None
    assert evidence["bounds_violations"] == [] and evidence["critical_issues"] == []
    assert evidence["clamps"] == [] and evidence["error"] is None
    checks = evidence["checks"]
    assert checks["action_eligible"] is True and checks["no_clamp"] is True
    assert checks["hint_mentions_technical"] is True and checks["hint_mentions_fundamental"] is True
    assert {"hint_mentions_technical", "hint_mentions_fundamental"} <= set(evidence["advisory_checks"])


def test_main_prints_a_result_line_and_never_the_key(replay, monkeypatch, tmp_path, capsys):
    install_crew(monkeypatch, *conflict_answers())
    code = replay.main(["--case", "conflict", "--out-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 0
    assert "REPLAY RESULT: conflict pass 1/6 COMPLETED" in captured.out
    assert SENTINEL not in captured.out + captured.err
    assert RATIONALE not in captured.out
    for path in tmp_path.iterdir():
        assert SENTINEL not in path.read_text(encoding="utf-8")


def test_invalid_draft_action_ends_the_pass_with_the_exception_class(replay, monkeypatch, tmp_path, capsys):
    ticker = replay.SEED["conflict"]["ticker"]
    akickoff = install_crew(monkeypatch, return_value=narrative(ticker, "BUY"))
    code = replay.main(["--case", "conflict", "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "REPLAY RESULT: conflict pass 1/6 ERROR PhaseSchemaError" in out
    assert akickoff.await_count >= 2  # the bounded schema retries ran, nothing was repaired
    evidence = json.loads((tmp_path / "pass-1-conflict.json").read_text(encoding="utf-8"))
    assert evidence["error"] == "PhaseSchemaError"
    assert evidence["final"] is None and evidence["published"] is None
    assert replay.passes_used(tmp_path) == 1


# ─── The below-zone case, the cap, the key refusal and the dry run (Task 2) ─────

def below_answers(final_action="LONG-BUY", draft_action="LONG-BUY"):
    ticker = _load().SEED["below-zone"]["ticker"]
    return [narrative(ticker, draft_action), critic(ticker, "MINOR"), narrative(ticker, final_action)]


def test_below_zone_case_is_strictly_below_the_zone_and_long_buy_eligible(replay):
    case = replay.build_case("below-zone")
    technical = case.technical.technical_analysis[0]
    momentum = technical.momentum_analysis
    assert technical.ticker == replay.SEED["below-zone"]["ticker"]
    assert technical.current_price == replay.SEED["below-zone"]["price"]
    assert momentum.entry_zone_status == "BELOW_ZONE"
    assert technical.current_price < momentum.entry_zone_low < momentum.entry_zone_high
    assert 0.015 < 1 - technical.current_price / momentum.entry_zone_low < 0.03  # about 2 percent below
    assert momentum.momentum_score >= 7 and momentum.overall_signal == "BULLISH"
    rating = case.fundamental.fundamental_analysis[0].fundamental_rating
    assert (rating.valuation, rating.quality, rating.growth) == ("FAIR", "High", "High Growth")
    assert case.fundamental.fundamental_analysis[0].data_status == "ok"

    flow = ProspectAIFlow()
    eligible = replay.preflight(case, flow)
    assert flow._fundamentals_status_by_ticker() == {case.ticker: "AVAILABLE"}
    assert "LONG-BUY" in eligible and "WAIT-FOR-ENTRY" not in eligible
    # The preflight is pinned for the revised fixture: exactly these three actions are open.
    assert eligible == ["AVOID", "LONG-BUY", "MONITOR"]
    assert replay.eligible_for(case) == eligible


# ─── The below-zone records are internally consistent (fixture revision, plan 04-07) ──────────

def test_below_zone_technical_record_is_what_the_real_interpretation_tool_computes(replay):
    """Zone, status, regime, momentum and risk are the deterministic tool's output, not typed numbers.

    A TRENDING regime can never end BELOW_ZONE in that tool (its zone is anchored just under the
    price), so a trending below-zone record was an impossible combination.
    """
    from utils.technical_interpretation_tool import TechnicalInterpretationTool
    from utils.technical_records import trend_strength_from_adx

    case = replay.build_case("below-zone")
    raw = replay.BELOW_ZONE_INDICATORS
    assert raw["current_price"] == replay.SEED["below-zone"]["price"]
    computed = json.loads(TechnicalInterpretationTool()._run(case.ticker, json.dumps(raw)))
    technical = case.technical.technical_analysis[0]
    momentum = technical.momentum_analysis
    assert computed["entry_zone_status"] == momentum.entry_zone_status == "BELOW_ZONE"
    assert computed["entry_zone_low"] == momentum.entry_zone_low
    assert computed["entry_zone_high"] == momentum.entry_zone_high
    assert computed["regime"] == momentum.regime and momentum.regime != "TRENDING"
    assert computed["momentum_score"] == momentum.momentum_score
    assert computed["risk_level"] == momentum.risk_level
    assert momentum.trend_strength == trend_strength_from_adx(raw["adx"])
    indicators = technical.raw_indicators
    assert (indicators.rsi, indicators.adx) == (raw["rsi"], raw["adx"])
    assert (indicators.macd_status, indicators.ma_status, indicators.stochastic_status) == (
        raw["macd_status"], raw["ma_status"], raw["stochastic_status"],
    )


def test_below_zone_key_signals_are_readings_of_the_raw_indicators(replay):
    """The long-term averages the signals cite hold in the raw inputs, and the stack label matches them."""
    raw = replay.BELOW_ZONE_INDICATORS
    assert raw["sma_20"] > raw["sma_50"] > raw["sma_200"]  # the "Strong Uptrend" label in ma_status
    assert raw["ma_status"] == "Strong Uptrend"
    assert raw["current_price"] > raw["sma_50"] > raw["sma_200"]  # price above both long averages
    signals = replay.build_case("below-zone").technical.technical_analysis[0].momentum_analysis.key_signals
    assert any("SMA50" in signal and f"{raw['sma_50']:.2f}" in signal for signal in signals)
    assert any("SMA200" in signal and f"{raw['sma_200']:.2f}" in signal for signal in signals)
    assert any("RSI" in signal and f"{raw['rsi']:.0f}" in signal for signal in signals)


def test_below_zone_fundamental_record_is_what_the_real_grader_computes(replay):
    from utils.fundamental_grader_tool import FundamentalGraderTool

    case = replay.build_case("below-zone")
    analysis = case.fundamental.fundamental_analysis[0]
    batch = {"fundamentals": [replay.BELOW_ZONE_FUNDAMENTALS]}
    grade = json.loads(FundamentalGraderTool()._run(json.dumps(batch)))["grades"][0]
    rating = analysis.fundamental_rating
    assert (rating.valuation, rating.quality, rating.growth) == (grade["valuation"], grade["quality"], grade["growth"])
    assert analysis.data_status == grade["data_status"] == "ok"
    assert "UNKNOWN" not in (rating.valuation, rating.quality, rating.growth)
    metrics = analysis.valuation_metrics
    raw = replay.BELOW_ZONE_FUNDAMENTALS
    assert metrics.pe_ratio == raw["valuation"]["pe_ratio"]
    assert metrics.debt_to_equity == raw["balance_sheet"]["debt_to_equity"]
    assert metrics.free_cash_flow == raw["balance_sheet"]["free_cash_flow"] > 0
    assert metrics.revenue_growth_yoy == raw["growth"]["revenue_growth_yoy"]


def test_below_zone_market_record_carries_measured_sentiment_and_conflict_stays_unmeasured(replay):
    """Post phase 3.1 a pick normally has a news-provider score; the conflict case is left as it was."""
    below = replay.build_case("below-zone").market
    stock = below.candidate_stocks[0]
    assert below.sentiment_available is True
    assert stock.average_sentiment is not None and 0.0 < stock.average_sentiment <= 1.0
    assert stock.mention_count is not None and stock.mention_count > 0
    assert stock.relevance_score == 1.0  # the only candidate: count over the largest count
    conflict = replay.build_case("conflict").market
    assert conflict.sentiment_available is False
    assert conflict.candidate_stocks[0].average_sentiment is None


def test_replay_records_do_not_steer_the_choice_of_action(replay):
    """No record text names an action, instructs, or editorialises on the setup (no coaching)."""
    import re

    steering = re.compile(
        r"\b(long-buy|buy|sell|wait|monitor|avoid|should|must|recommend\w*|breakdown|dip\w*|weakness)\b",
        re.IGNORECASE,
    )

    def strings(value, key=""):
        if isinstance(value, str):
            yield key, value
        elif isinstance(value, dict):
            for k, v in value.items():
                yield from strings(v, k)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item, key)

    for name in replay.CASES:
        case = replay.build_case(name)
        for record in (case.market, case.technical, case.fundamental):
            for key, text in strings(record.model_dump(mode="json")):
                assert not steering.search(text), f"{name}: {key!r} steers the model: {text!r}"


def test_below_zone_long_buy_is_price_anchored_with_ordered_levels(replay, monkeypatch, tmp_path):
    install_crew(monkeypatch, *below_answers("LONG-BUY"))
    case = replay.build_case("below-zone")
    evidence = replay.run_pass(case, tmp_path, ProspectAIFlow())

    assert evidence["error"] is None and evidence["published"]["action"] == "LONG-BUY"
    setup = evidence["published"]["trade_setup"]
    price = evidence["published"]["current_price"]
    assert price == case.price
    assert setup["entry_zone_low"] == setup["entry_zone_high"] == price
    assert setup["stop_loss"] < price < setup["take_profit"]
    checks = evidence["checks"]
    assert checks["price_anchored"] is True
    assert checks["stop_below_price_below_target"] is True
    assert checks["bounds_ok"] is True and evidence["bounds_violations"] == []
    # validate_portfolio now exempts the price-anchored zone (deferred item D-04-06-1), so the
    # below-zone LONG-BUY carries no critical issue.
    assert evidence["critical_issues"] == []
    assert checks["no_critical"] is True
    assert checks["exercised"] is True
    assert "exercised" in evidence["informational_checks"]
    assert replay.mechanical_ok(evidence) is True


def test_below_zone_monitor_does_not_exercise_the_branch(replay, monkeypatch, tmp_path, capsys):
    install_crew(monkeypatch, *below_answers("MONITOR"))
    code = replay.main(["--case", "below-zone", "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    evidence = json.loads((tmp_path / "pass-1-below-zone.json").read_text(encoding="utf-8"))
    assert code == 0  # a legitimate judgment is not a failure
    assert evidence["published"]["action"] == "MONITOR"
    assert evidence["checks"]["exercised"] is False
    assert evidence["checks"]["price_anchored"] is None
    assert evidence["checks"]["stop_below_price_below_target"] is None
    assert "REPLAY RESULT: below-zone pass 1/6 COMPLETED" in out


def test_below_zone_run_never_writes_the_key(replay, monkeypatch, tmp_path, capsys):
    install_crew(monkeypatch, *below_answers("LONG-BUY"))
    replay.main(["--case", "below-zone", "--out-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert SENTINEL not in captured.out + captured.err
    for path in tmp_path.iterdir():
        assert SENTINEL not in path.read_text(encoding="utf-8")


# ─── The aggressive-profile below-zone case (operator decision after 10 conservative MONITORs) ──────

AGGRESSIVE = "below-zone-aggressive"


def test_aggressive_case_is_registered_and_the_other_cases_keep_their_profile(replay):
    assert replay.CASES == ("conflict", "below-zone", AGGRESSIVE)
    assert replay.build_case("conflict").risk_profile == "conservative"
    assert replay.build_case("below-zone").risk_profile == "conservative"
    assert replay.build_case("below-zone").name == "below-zone"
    case = replay.build_case(AGGRESSIVE)
    assert case.name == AGGRESSIVE and case.risk_profile == "aggressive" and case.synthetic is True


def test_aggressive_case_uses_the_same_synthetic_records_as_the_conservative_below_zone_case(replay):
    """Only the profile differs: the evidence the model reads is identical, so the claim stays honest."""
    base = replay.build_case("below-zone")
    case = replay.build_case(AGGRESSIVE)
    assert (case.ticker, case.price, case.sector, case.seed) == (base.ticker, base.price, base.sector, base.seed)
    for name in ("market", "technical", "fundamental"):
        assert getattr(case, name).model_dump(mode="json") == getattr(base, name).model_dump(mode="json")
    assert case.technical.technical_analysis[0].momentum_analysis.entry_zone_status == "BELOW_ZONE"


def test_aggressive_case_preflight_pins_the_eligible_actions_and_primes_the_profile(replay):
    case = replay.build_case(AGGRESSIVE)
    flow = ProspectAIFlow()
    eligible = replay.preflight(case, flow)
    assert flow.state.risk_profile == "aggressive"
    assert eligible == ["AVOID", "LONG-BUY", "MONITOR"]
    assert replay.eligible_for(case) == eligible


def test_aggressive_long_buy_is_price_anchored_and_the_profile_is_in_the_evidence(replay, monkeypatch, tmp_path):
    from utils.portfolio_allocator_tool import PROFILE_BOUNDS

    install_crew(monkeypatch, *below_answers("LONG-BUY"))
    case = replay.build_case(AGGRESSIVE)
    evidence = replay.run_pass(case, tmp_path, ProspectAIFlow())

    assert evidence["case"] == AGGRESSIVE and evidence["risk_profile"] == "aggressive"
    assert evidence["evidence_file"] == f"pass-1-{AGGRESSIVE}.json"
    assert json.loads((tmp_path / evidence["evidence_file"]).read_text(encoding="utf-8")) == evidence
    assert evidence["error"] is None and evidence["published"]["action"] == "LONG-BUY"
    assert evidence["eligible_actions"] == ["AVOID", "LONG-BUY", "MONITOR"]
    price = evidence["published"]["current_price"]
    setup = evidence["published"]["trade_setup"]
    # Same mechanical checks as the conservative case, held under the aggressive bounds.
    assert setup["entry_zone_low"] == setup["entry_zone_high"] == price == case.price
    assert setup["stop_loss"] < price < setup["take_profit"]
    assert setup["stop_loss"] == round(price * PROFILE_BOUNDS["aggressive"]["stop_multiplier"], 2)
    # The aggressive cap is 30 percent for a lone position (15 under conservative); no check reads it.
    assert evidence["published"]["allocation_pct"] == PROFILE_BOUNDS["aggressive"]["max_alloc_pct"]
    checks = evidence["checks"]
    assert checks["price_anchored"] is True and checks["stop_below_price_below_target"] is True
    assert checks["bounds_ok"] is True and checks["no_critical"] is True
    assert checks["exercised"] is True and "exercised" in evidence["informational_checks"]
    assert evidence["bounds_violations"] == [] and evidence["critical_issues"] == []
    assert replay.mechanical_ok(evidence) is True


def test_conservative_below_zone_evidence_still_records_the_conservative_profile(replay, monkeypatch, tmp_path):
    install_crew(monkeypatch, *below_answers("LONG-BUY"))
    evidence = replay.run_pass(replay.build_case("below-zone"), tmp_path, ProspectAIFlow())
    assert evidence["risk_profile"] == "conservative" and evidence["evidence_file"] == "pass-1-below-zone.json"
    assert evidence["published"]["allocation_pct"] == 15.0


def test_aggressive_monitor_does_not_exercise_the_branch(replay, monkeypatch, tmp_path, capsys):
    install_crew(monkeypatch, *below_answers("MONITOR"))
    code = replay.main(["--case", AGGRESSIVE, "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    evidence = json.loads((tmp_path / f"pass-1-{AGGRESSIVE}.json").read_text(encoding="utf-8"))
    assert code == 0
    assert evidence["checks"]["exercised"] is False and evidence["checks"]["price_anchored"] is None
    assert f"REPLAY RESULT: {AGGRESSIVE} pass 1/6 COMPLETED" in out


def test_aggressive_dry_run_prints_case_and_eligible_actions_and_writes_nothing(replay, monkeypatch, tmp_path, capsys):
    akickoff = install_crew(monkeypatch, *below_answers("LONG-BUY"))
    assert replay.main(["--case", AGGRESSIVE, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert f"Case: {AGGRESSIVE} ticker=NVDA" in out and "risk_profile=aggressive" in out
    assert "Eligible actions: AVOID, LONG-BUY, MONITOR" in out
    assert "REPLAY RESULT" not in out and SENTINEL not in out
    assert akickoff.await_count == 0 and list(tmp_path.iterdir()) == []


def test_conservative_dry_run_header_is_unchanged(replay, capsys):
    """The case line of the existing cases must stay byte-identical (no profile suffix)."""
    assert replay.main(["--case", "below-zone", "--dry-run"]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first == (
        "Case: below-zone ticker=NVDA seed_price=168.89 (SYNTHETIC records seeded from a live report: "
        "report cc3581b8-2b32-4e48-be36-c92ea401c56b run_at 2026-11-10T21:32:23Z)"
    )


def test_aggressive_cap_is_per_out_dir_and_still_six(replay, monkeypatch, tmp_path, capsys):
    assert replay.MAX_PASSES == 6
    (tmp_path / replay.LEDGER_NAME).write_text(
        "".join(json.dumps({"pass": n, "case": "below-zone"}) + "\n" for n in range(1, 7)), encoding="utf-8",
    )
    akickoff = install_crew(monkeypatch, *below_answers("LONG-BUY"))
    assert replay.main(["--case", AGGRESSIVE, "--out-dir", str(tmp_path)]) == 3
    assert "CAP REACHED: 6 of 6" in capsys.readouterr().out and akickoff.await_count == 0
    fresh = tmp_path / "fresh"
    install_crew(monkeypatch, *below_answers("MONITOR"))
    assert replay.main(["--case", AGGRESSIVE, "--out-dir", str(fresh)]) == 0
    assert replay.passes_used(fresh) == 1


def test_cap_reached_returns_3_without_building_a_flow_or_calling_the_crew(replay, monkeypatch, tmp_path, capsys):
    (tmp_path / replay.LEDGER_NAME).write_text(
        "".join(json.dumps({"pass": n, "case": "conflict"}) + "\n" for n in range(1, 7)),
        encoding="utf-8",
    )
    akickoff = install_crew(monkeypatch, *conflict_answers())

    def no_flow(*args, **kwargs):
        raise AssertionError("the flow must not be built once the cap is reached")

    monkeypatch.setattr(replay, "ProspectAIFlow", no_flow)
    code = replay.main(["--case", "conflict", "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 3
    assert "CAP REACHED: 6 of 6 passes used; stop and report to the operator (D-09)" in out
    assert akickoff.await_count == 0
    assert replay.passes_used(tmp_path) == 6
    assert sorted(p.name for p in tmp_path.iterdir()) == [replay.LEDGER_NAME]


def test_cap_counts_passes_across_runs_and_refuses_the_seventh(replay, monkeypatch, tmp_path, capsys):
    for number in range(1, 7):
        install_crew(monkeypatch, *conflict_answers())
        assert replay.main(["--case", "conflict", "--out-dir", str(tmp_path)]) == 0
        assert replay.passes_used(tmp_path) == number
    capsys.readouterr()
    akickoff = install_crew(monkeypatch, *conflict_answers())
    assert replay.main(["--case", "conflict", "--out-dir", str(tmp_path)]) == 3
    assert "CAP REACHED" in capsys.readouterr().out
    assert akickoff.await_count == 0 and replay.passes_used(tmp_path) == 6
    assert not (tmp_path / "pass-7-conflict.json").exists()


def test_missing_key_refuses_before_any_ledger_write(replay, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    akickoff = install_crew(monkeypatch, *conflict_answers())
    out_dir = tmp_path / "evidence"
    with pytest.raises(SystemExit) as info:
        replay.main(["--case", "conflict", "--out-dir", str(out_dir)])
    assert "ANTHROPIC_API_KEY" in str(info.value)
    assert not out_dir.exists()
    assert akickoff.await_count == 0


def test_dry_run_prints_eligible_actions_and_writes_nothing(replay, monkeypatch, tmp_path, capsys):
    akickoff = install_crew(monkeypatch, *conflict_answers())
    code = replay.main(["--case", "below-zone", "--out-dir", str(tmp_path / "evidence"), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Eligible actions:" in out and "LONG-BUY" in out
    assert "REPLAY RESULT" not in out and SENTINEL not in out
    assert not (tmp_path / "evidence").exists() and list(tmp_path.iterdir()) == []
    assert akickoff.await_count == 0
    # --out-dir is optional for a dry run
    assert replay.main(["--case", "conflict", "--dry-run"]) == 0


def test_long_buy_not_eligible_returns_2_without_a_call_or_ledger_line(replay, monkeypatch, tmp_path, capsys):
    case = replay.build_case("conflict")
    rating = case.fundamental.fundamental_analysis[0].fundamental_rating
    rating.quality, rating.growth = "UNKNOWN", "UNKNOWN"  # fundamentals unknown: only MONITOR or AVOID
    monkeypatch.setattr(replay, "build_case", lambda name: case)
    akickoff = install_crew(monkeypatch, *conflict_answers())
    out_dir = tmp_path / "evidence"
    code = replay.main(["--case", "conflict", "--out-dir", str(out_dir)])
    out = capsys.readouterr().out
    assert code == 2
    assert "LONG-BUY is not eligible" in out
    assert akickoff.await_count == 0 and not out_dir.exists()
