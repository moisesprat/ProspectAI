"""Live replay of reasoning-depth action selection (phase 4 SPEC-01; tasks 7.1 and 7.2).

Purpose: validate, on the real configured models and before any release, that the
LLM now weighs a bullish technical picture against weak fundamentals (case
``conflict``) and the below-zone price-anchored LONG-BUY path (case ``below-zone``),
as the OpenSpec change ``reasoning-depth-action-selection`` describes. Only a live
call shows what the models choose; the offline tests mock the crew.

What a pass is: the draft_strategy, critique_review and final_strategy phases for
one case, run through the real Flow methods on the configured models, including
their bounded schema retries. After the three phases the real
``_finalize_and_validate_portfolio`` step and the deterministic validators run on
the final output. Nothing an LLM answers is repaired or normalised (D-11): a phase
that exhausts its schema retries ends the pass and the exception class is recorded.

The records are SYNTHETIC test inputs. Stored runs keep only the final report and
metrics, not the technical and fundamental records, so the market, technical and
fundamental records are hand-built typed fixtures seeded with a real ticker and
price (see ``SEED``). They are not claims about the market and are not published.
The market, technical and fundamental phases are skipped (D-08).

Cases and what the operator reviews
-----------------------------------
  conflict    Bullish technicals (BULLISH, momentum 8, CURRENT_ENTRY) against
              graded-weak fundamentals (VERY_EXPENSIVE, Low quality, Declining
              growth, data_status ok, so fundamentals are AVAILABLE, not UNKNOWN).
              LONG-BUY is eligible, so the policy clamp does not decide for the
              LLM. The operator reads the draft, critic and final rationales and
              judges whether the final action is coherent with the conflict; the
              two ``hint_*`` checks are advisory keyword hints, not a verdict.
  below-zone  entry_zone_status BELOW_ZONE with the price strictly below the zone
              and healthy fundamentals. When the LLM answers LONG-BUY the checks
              show the setup is price-anchored with stop < price < target; any
              other action is a legitimate judgment that did not exercise the branch.

Cost: a few cents to tens of cents per pass on the Sonnet 5.5 phases. Hard cap: 6
passes per ``--out-dir`` (D-09), counted in ``passes.jsonl`` and enforced before any
flow is built; a started pass is recorded before it runs, so a crash still counts.
The harness lives in ``scripts/`` and is not packaged in the wheel. Run by a human
with their own key; never by CI.

Usage, from ProspectAI/:

    .venv/bin/python scripts/replay_reasoning_depth.py --case conflict --out-dir DIR
    .venv/bin/python scripts/replay_reasoning_depth.py --case below-zone --out-dir DIR
    .venv/bin/python scripts/replay_reasoning_depth.py --case conflict --dry-run

The key is read from the environment or ProspectAI/.env. ``--dry-run`` runs only the
preflight (eligibility) and writes nothing.

Output is limited to the resolved model ids, the case, ticker and seed, the eligible
actions, the pass number, the final action, the checks, the evidence path and one
closing ``REPLAY RESULT:`` line. Keys, prompts and rationale text are never printed;
the evidence file carries the rationales for review.

Exit codes: 0 pass completed and the mechanical checks hold; 1 pass completed with a
failed check or an exception; 2 preflight refused with no LLM call; 3 cap reached
with no LLM call.
"""

import argparse
import asyncio
import contextlib
import io
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import (
    CandidateStock,
    FundamentalAnalysisOutput,
    FundamentalRating,
    MarketAnalysisOutput,
    MomentumAnalysis,
    RawIndicators,
    StockFundamentalAnalysis,
    StockTechnicalAnalysis,
    SupportResistance,
    TechnicalAnalysisOutput,
    ValuationMetrics,
)
from utils.execution_tracker import ExecutionTracker
from utils.fundamental_grader_tool import fundamentals_status
from utils.portfolio_bounds_validator import BoundsViolationError
from utils.recommendation_validator import validate_portfolio
from utils.strategy_assembly import clamp_warnings, eligible_by_ticker

# D-09: the hard spend cap. Six passes per out-dir; one pass is draft + critic + final for one case.
MAX_PASSES = 6
LEDGER_NAME = "passes.jsonl"
CASES = ("conflict", "below-zone")
PHASES = ("draft_strategy", "critique_review", "final_strategy")

# Real ticker and price per case, read once at authoring time (2026-11-12) from the live
# report run cc3581b8-2b32-4e48-be36-c92ea401c56b (Technology, run_at 2026-11-10T21:32:23Z)
# through GET /api/report/<run_id>: META's and NVDA's published current_price, to 2 decimals.
# Only the ticker and the price are real; every other field of the records is SYNTHETIC.
SEED: Dict[str, Dict[str, Any]] = {
    "conflict": {
        "ticker": "META", "price": 641.39,
        "source": "report cc3581b8-2b32-4e48-be36-c92ea401c56b run_at 2026-11-10T21:32:23Z",
    },
    "below-zone": {
        "ticker": "NVDA", "price": 168.89,
        "source": "report cc3581b8-2b32-4e48-be36-c92ea401c56b run_at 2026-11-10T21:32:23Z",
    },
}

SECTOR = "Technology"
RISK_PROFILE = "conservative"

# Advisory keyword hints (conflict case): the operator, not these sets, decides coherence.
TECHNICAL_HINTS = ("momentum", "rsi", "macd", "trend", "technical", "moving average", "adx", "breakout")
FUNDAMENTAL_HINTS = ("valuation", "expensive", "fundamental", "quality", "growth", "declining", "earnings")
ADVISORY_CHECKS = ("hint_mentions_technical", "hint_mentions_fundamental")
INFORMATIONAL_CHECKS = ("exercised",)


@dataclass
class ReplayCase:
    name: str
    ticker: str
    price: float
    market: MarketAnalysisOutput
    technical: TechnicalAnalysisOutput
    fundamental: FundamentalAnalysisOutput
    sector: str = SECTOR
    risk_profile: str = RISK_PROFILE
    synthetic: bool = True
    seed: Dict[str, Any] = field(default_factory=dict)


# ─── Case construction ─────────────────────────────────────────────────────────

def _market(ticker: str) -> MarketAnalysisOutput:
    return MarketAnalysisOutput(
        sector=SECTOR,
        candidate_stocks=[CandidateStock(
            ticker=ticker, mention_count=None, average_sentiment=None, relevance_score=None,
            rationale=f"{ticker} is a large-cap {SECTOR} candidate chosen as the replay input for this case.",
        )],
        summary="Replay market record: one candidate, no sentiment measured, used only as the strategy input. " * 2,
        sentiment_available=False,
    )


def _technical(
    ticker: str, price: float, *, momentum: float, status: str, zone_low: float, zone_high: float,
    signal: str, risk_level: str, rsi: float, adx: float, trend: str, signals: List[str],
) -> TechnicalAnalysisOutput:
    return TechnicalAnalysisOutput(
        sector=SECTOR,
        summary="Replay technical record: one ticker with hand-built indicators and entry zone. " * 2,
        technical_analysis=[StockTechnicalAnalysis(
            ticker=ticker,
            current_price=price,
            raw_indicators=RawIndicators(
                rsi=rsi, adx=adx, macd_status="bullish", ma_status="above SMA50 and SMA200",
                stochastic_status="neutral",
            ),
            momentum_analysis=MomentumAnalysis(
                momentum_score=momentum,
                risk_level=risk_level,
                trend_strength=trend,
                key_signals=signals,
                support_resistance=SupportResistance(support=zone_low, resistance=zone_high),
                comprehensive_analysis=f"{ticker} replay indicators: momentum {momentum}, RSI {rsi}, ADX {adx}.",
                overall_signal=signal,
                entry_zone_status=status,
                entry_zone_low=zone_low,
                entry_zone_high=zone_high,
                regime="TRENDING",
            ),
            investment_recommendation=f"{ticker} replay technical view: {signal.lower()} signal, status {status}.",
        )],
    )


def _fundamental(
    ticker: str, *, valuation: str, quality: str, growth: str, metrics: ValuationMetrics,
    strengths: List[str], risks: List[str], thesis: str,
) -> FundamentalAnalysisOutput:
    return FundamentalAnalysisOutput(
        sector=SECTOR,
        summary="Replay fundamental record: one ticker with hand-built grades, data_status ok. " * 2,
        fundamental_analysis=[StockFundamentalAnalysis(
            ticker=ticker,
            company_name=ticker,
            valuation_metrics=metrics,
            fundamental_rating=FundamentalRating(valuation=valuation, quality=quality, growth=growth),
            key_strengths=strengths,
            key_risks=risks,
            investment_thesis=thesis,
            data_status="ok",
        )],
    )


def _build_conflict() -> ReplayCase:
    seed = SEED["conflict"]
    ticker, price = seed["ticker"], seed["price"]
    technical = _technical(
        ticker, price, momentum=8, status="CURRENT_ENTRY",
        zone_low=round(price * 0.98, 2), zone_high=round(price * 1.01, 2),
        signal="BULLISH", risk_level="Medium", rsi=61.0, adx=32.0, trend="Strong",
        signals=["MACD bullish crossover", "Price above SMA50 and SMA200", "RSI constructive at 61"],
    )
    fundamental = _fundamental(
        ticker, valuation="VERY_EXPENSIVE", quality="Low", growth="Declining",
        metrics=ValuationMetrics(
            pe_ratio=95.0, pb_ratio=14.0, price_to_sales=18.0, roe=0.04,
            revenue_growth_yoy=-0.06, earnings_growth_yoy=-0.12, debt_to_equity=1.8,
        ),
        strengths=["Large installed base"],
        risks=["Valuation far above peers", "Revenue and earnings are shrinking", "Low return on equity"],
        thesis="Replay thesis: the price implies growth that the reported numbers do not show.",
    )
    return ReplayCase(
        name="conflict", ticker=ticker, price=price, market=_market(ticker),
        technical=technical, fundamental=fundamental, seed=dict(seed),
    )


def _build_below_zone() -> ReplayCase:
    seed = SEED["below-zone"]
    ticker, price = seed["ticker"], seed["price"]
    zone_low = round(price / 0.98, 2)  # the price sits about 2 percent below the zone
    technical = _technical(
        ticker, price, momentum=8, status="BELOW_ZONE",
        zone_low=zone_low, zone_high=round(zone_low * 1.03, 2),  # a zone about 3 percent wide
        signal="BULLISH", risk_level="Medium", rsi=58.0, adx=30.0, trend="Strong",
        signals=["MACD bullish crossover", "Price dipped below the pullback zone", "RSI constructive at 58"],
    )
    fundamental = _fundamental(
        ticker, valuation="FAIR", quality="High", growth="High Growth",
        metrics=ValuationMetrics(
            pe_ratio=28.0, pb_ratio=6.0, price_to_sales=9.0, roe=0.35,
            revenue_growth_yoy=0.30, earnings_growth_yoy=0.35, debt_to_equity=0.4,
        ),
        strengths=["High return on equity", "Strong revenue and earnings growth"],
        risks=["Cyclical demand", "Customer concentration"],
        thesis="Replay thesis: growth and returns are strong and the valuation is in line with growth.",
    )
    return ReplayCase(
        name="below-zone", ticker=ticker, price=price, market=_market(ticker),
        technical=technical, fundamental=fundamental, seed=dict(seed),
    )


_BUILDERS = {"conflict": _build_conflict, "below-zone": _build_below_zone}


def build_case(name: str) -> ReplayCase:
    """The typed, SYNTHETIC records for ``name``; ValueError for an unknown case."""
    builder = _BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"Unknown case {name!r}. Valid cases: {', '.join(sorted(_BUILDERS))}")
    return builder()


# ─── Preflight, ledger, pass ───────────────────────────────────────────────────

def _prime(case: ReplayCase, flow: ProspectAIFlow) -> None:
    """Set the flow state a run would hold after the market, technical and fundamental phases."""
    flow.state.sector = case.sector
    flow.state.today = datetime.now().strftime("%Y-%m-%d")
    flow.state.risk_profile = case.risk_profile
    flow.state.market_output = case.market
    flow.state.technical_output = case.technical
    flow.state.fundamental_output = case.fundamental


def eligible_for(case: ReplayCase, fundamentals: Optional[Dict[str, str]] = None) -> List[str]:
    """Sorted eligible actions for the case's ticker, from the records alone (no flow, no LLM).

    ``fundamentals`` is the flow's ticker -> AVAILABLE | UNKNOWN map; without it the same
    rule the flow applies is read from the case's fundamental ratings.
    """
    if fundamentals is None:
        fundamentals = {
            a.ticker.upper(): fundamentals_status(a.fundamental_rating.quality, a.fundamental_rating.growth)
            for a in case.fundamental.fundamental_analysis
        }
    return sorted(eligible_by_ticker(case.technical, fundamentals, case.risk_profile)[case.ticker.upper()])


def preflight(case: ReplayCase, flow: ProspectAIFlow) -> List[str]:
    """Set the flow state from ``case`` and return the sorted eligible actions for its ticker."""
    _prime(case, flow)
    return eligible_for(case, flow._fundamentals_status_by_ticker())


def passes_used(out_dir: Path) -> int:
    """Passes recorded in the ledger of ``out_dir`` (0 when there is none)."""
    ledger = Path(out_dir) / LEDGER_NAME
    if not ledger.exists():
        return 0
    return sum(1 for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())


def phase_models(flow: ProspectAIFlow) -> Dict[str, str]:
    """Model id each replayed phase resolves to (agents.yaml with MODEL / AGENT_*_MODEL applied)."""
    return {phase: str(flow._factory._phase_config[phase]["agent"].llm.model) for phase in PHASES}


def _action_and_rationale(output: Any, ticker: str) -> Optional[Dict[str, Any]]:
    for position in output.positions if output is not None else []:
        if position.ticker.upper() == ticker.upper():
            return {"action": position.action, "rationale": position.rationale}
    return None


def _published(structured: Dict[str, Any], ticker: str) -> Optional[Dict[str, Any]]:
    for position in structured.get("positions", []):
        if str(position.get("ticker", "")).upper() == ticker.upper():
            return {key: position.get(key) for key in (
                "action", "current_price", "allocation_pct", "trade_setup", "fundamentals_status",
            )}
    return None


def checks(case: ReplayCase, evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Mechanical checks (and, for ``conflict``, two advisory hints) over a finished pass."""
    published = evidence.get("published")
    if published is None or evidence.get("error"):
        return {}
    result: Dict[str, Any] = {
        "action_eligible": published["action"] in evidence["eligible_actions"],
        "no_clamp": not evidence["clamps"],
        "bounds_ok": not evidence["bounds_violations"],
        "no_critical": not evidence["critical_issues"],
    }
    if case.name == "conflict":
        rationale = ((evidence.get("final") or {}).get("rationale") or "").lower()
        result["hint_mentions_technical"] = any(term in rationale for term in TECHNICAL_HINTS)
        result["hint_mentions_fundamental"] = any(term in rationale for term in FUNDAMENTAL_HINTS)
    if case.name == "below-zone":
        exercised = published["action"] == "LONG-BUY"
        setup = published.get("trade_setup") if exercised else None
        price = published.get("current_price")
        result["exercised"] = exercised  # informational: another action is a judgment, not a failure
        result["price_anchored"] = None
        result["stop_below_price_below_target"] = None
        if setup is not None and price is not None:
            low, high = setup["entry_zone_low"], setup["entry_zone_high"]
            result["price_anchored"] = abs(low - high) < 1e-6 and abs(low - price) < 0.01
            result["stop_below_price_below_target"] = setup["stop_loss"] < price < setup["take_profit"]
        elif exercised:
            result["price_anchored"] = result["stop_below_price_below_target"] = False  # LONG-BUY without a setup
    return result


def mechanical_ok(evidence: Dict[str, Any]) -> bool:
    """True when the pass had no exception and no mechanical check is False (advisory checks never fail it)."""
    if evidence.get("error"):
        return False
    skip = set(evidence.get("advisory_checks", [])) | set(evidence.get("informational_checks", []))
    return all(value is not False for key, value in evidence["checks"].items() if key not in skip)


def _redact(text: str) -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    return text.replace(key, "[redacted]") if key else text


async def _run_phases(flow: ProspectAIFlow, case: ReplayCase, evidence: Dict[str, Any]) -> None:
    """The three real phases, recording each phase's answer as soon as it exists."""
    await flow.draft_strategy()
    evidence["draft"] = _action_and_rationale(flow.state.draft_output, case.ticker)
    await flow.critique_review()
    critique = flow.state.critique_output
    evidence["critic"] = {"critiques": [
        {"ticker": c.ticker, "severity": c.severity, "issue_type": c.issue_type, "finding": c.finding}
        for c in (critique.per_ticker_critiques if critique is not None else [])
    ]}
    await flow.final_strategy()
    evidence["final"] = _action_and_rationale(flow.state.final_output, case.ticker)


def run_pass(case: ReplayCase, out_dir: Path, flow: ProspectAIFlow) -> Dict[str, Any]:
    """One pass: draft, critic and final on the flow, then finalize and the validators; write the evidence.

    The ledger line is written before the first phase. No LLM answer is repaired or
    normalised (D-11): an exception ends the pass and its class is the recorded error.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    number = passes_used(out_dir) + 1
    with open(out_dir / LEDGER_NAME, "a", encoding="utf-8") as ledger:
        ledger.write(json.dumps({
            "pass": number, "case": case.name,
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }) + "\n")

    eligible = preflight(case, flow)
    tracker = ExecutionTracker()
    tracker.set_sector(case.sector)
    tracker.start()
    flow._tracker = tracker
    evidence: Dict[str, Any] = {
        "case": case.name, "pass": number, "max_passes": MAX_PASSES,
        "synthetic": case.synthetic, "seed": dict(case.seed),
        "sector": case.sector, "risk_profile": case.risk_profile,
        "models": phase_models(flow), "eligible_actions": eligible,
        "draft": None, "critic": None, "final": None, "published": None,
        "bounds_violations": [], "critical_issues": [], "clamps": [], "validation_warnings": [],
        "checks": {}, "advisory_checks": [], "informational_checks": [],
        "tokens": None, "error": None,
    }
    sink = io.StringIO()
    logging.disable(logging.ERROR)  # library logs can carry model text; the evidence file is the record
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                asyncio.run(_run_phases(flow, case, evidence))
                structured = flow.state.final_output.model_dump(mode="json")
                structured = flow._finalize_and_validate_portfolio(structured, case.risk_profile)
                evidence["published"] = _published(structured, case.ticker)
                evidence["critical_issues"] = [
                    {"ticker": i.ticker, "field": i.field, "message": i.message}
                    for i in validate_portfolio(structured) if i.severity == "critical"
                ]
                evidence["validation_warnings"] = clamp_warnings(
                    flow.state.policy_clamps,
                    {str(p.get("ticker", "")).upper(): p.get("action") for p in structured.get("positions", [])},
                )
            except Exception as exc:  # the class only: messages can echo model output
                evidence["error"] = type(exc).__name__
                if isinstance(exc, BoundsViolationError):
                    evidence["bounds_violations"] = list(exc.violations)
                if hasattr(exc, "fields") and hasattr(exc, "phase"):
                    evidence["error_phase"] = {
                        "phase": exc.phase, "fields": list(exc.fields), "attempts": exc.attempts,
                    }
    finally:
        logging.disable(logging.NOTSET)
        tracker.finish()
    evidence["clamps"] = list(flow.state.policy_clamps)
    metrics = tracker.to_dict()
    evidence["tokens"] = {
        "totals": metrics["totals"],
        "attempts": {p["name"]: p["attempts"] for p in metrics["phases"] if p["name"] in PHASES},
    }
    evidence["checks"] = checks(case, evidence)
    evidence["advisory_checks"] = [k for k in ADVISORY_CHECKS if k in evidence["checks"]]
    evidence["informational_checks"] = [k for k in INFORMATIONAL_CHECKS if k in evidence["checks"]]

    evidence["evidence_file"] = f"pass-{number}-{case.name}.json"
    path = out_dir / evidence["evidence_file"]
    path.write_text(_redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n", encoding="utf-8")
    return evidence


# ─── Command line ──────────────────────────────────────────────────────────────

def _parse(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live replay of reasoning-depth action selection (one pass; at most 6 per out-dir).",
    )
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--out-dir", help="evidence directory (also holds the pass ledger); required unless --dry-run")
    parser.add_argument("--dry-run", action="store_true", help="run only the eligibility preflight; write nothing")
    args = parser.parse_args(argv)
    if not args.dry_run and not args.out_dir:
        parser.error("--out-dir is required unless --dry-run is given")
    return args


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse(argv)
    case = build_case(args.case)

    # 1. Preflight, from the records alone: the script exists to exercise the LLM's LONG-BUY judgment.
    eligible = eligible_for(case)
    print(
        f"Case: {case.name} ticker={case.ticker} seed_price={case.price} "
        f"(SYNTHETIC records seeded from a live report: {case.seed.get('source', 'n/a')})"
    )
    print("Eligible actions: " + ", ".join(eligible))
    if "LONG-BUY" not in eligible:
        print(
            f"Preflight refused: LONG-BUY is not eligible for {case.ticker}, so the clamp, not the LLM, "
            "would decide; no LLM call made."
        )
        return 2
    if args.dry_run:
        print("Dry run: preflight only, nothing written, no LLM call.")
        return 0

    # 2. The key, from the environment or ProspectAI/.env; never printed.
    load_dotenv(ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY (environment or .env) first.")

    # 3. The spend cap (D-09), before any flow is built.
    out_dir = Path(args.out_dir)
    if passes_used(out_dir) >= MAX_PASSES:
        print(f"CAP REACHED: {MAX_PASSES} of {MAX_PASSES} passes used; stop and report to the operator (D-09)")
        return 3

    flow = ProspectAIFlow()
    print("Resolved models: " + " ".join(f"{phase}={model}" for phase, model in phase_models(flow).items()))
    evidence = run_pass(case, out_dir, flow)
    number = evidence["pass"]
    print(f"Pass {number} of {MAX_PASSES} (hard cap per out-dir)")
    if evidence["error"]:
        print(f"Pass ended with {evidence['error']}")
    else:
        print(f"Final action: {evidence['final']['action']}")
        print("Checks: " + " ".join(f"{k}={v}" for k, v in evidence["checks"].items()))
        if evidence["advisory_checks"]:
            print("Advisory (operator decides coherence): " + ", ".join(evidence["advisory_checks"]))
    print(f"Evidence: {out_dir / evidence['evidence_file']}")
    status = f"ERROR {evidence['error']}" if evidence["error"] else "COMPLETED"
    print(f"REPLAY RESULT: {case.name} pass {number}/{MAX_PASSES} {status}")
    return 0 if mechanical_ok(evidence) else 1


if __name__ == "__main__":
    sys.exit(main())
