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
    assert 0.02 < momentum.entry_zone_high / momentum.entry_zone_low - 1 < 0.04  # a zone about 3 percent wide
    assert momentum.momentum_score >= 7
    rating = case.fundamental.fundamental_analysis[0].fundamental_rating
    assert (rating.valuation, rating.quality, rating.growth) == ("FAIR", "High", "High Growth")
    assert case.fundamental.fundamental_analysis[0].data_status == "ok"

    eligible = replay.preflight(case, ProspectAIFlow())
    assert "LONG-BUY" in eligible and "WAIT-FOR-ENTRY" not in eligible


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
