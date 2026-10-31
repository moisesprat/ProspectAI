"""Flow-built draft and final strategy and the merge with the LLM's narrative (CORR-10, D-08, D-15).

The draft phase (plan 02-17) and the final phase (plan 02-18) share every helper here: both
ask the LLM for a ``StrategyNarrativeOutput`` and the Flow builds the published
``InvestorStrategicOutput`` from it. The final phase reuses the Flow's composite scores from
the draft (``ProspectAIFlowState.composite_scores``, ``require_composite_scores`` fails closed
when one is missing) and records its own clamps next to the draft's, each tagged with its phase.

The Draft Strategist used to compose the composite-score input from context (number
reshaping), choose an action, compose the allocator input, copy the allocator's output
back and pick the portfolio ``risk_level``, which is a grade. Now the Flow does every
numeric step and the LLM keeps the one decision that is a judgment: the action per
ticker (``PositionNarrative`` in schemas/agent_outputs.py), with its rationale, its
monitoring triggers, a review cadence, and the ``overall_strategy`` text.

Order of work in ``ProspectAIFlow.draft_strategy``:

1. ``composite_inputs`` builds the input of ``compute_composite_scores`` from the typed
   market, technical and fundamental outputs; the Flow calls the tool before the LLM.
   Sentiment is passed as null for EVERY ticker when the market output says
   ``sentiment_available`` is false (the live Serper path, plan 02-16 decision A), so the
   composite score renormalises over the technical and fundamental components for all
   tickers alike and the scores stay comparable. A partly measured sentiment is never
   mixed into the scores. Null is never turned into 0.0.
2. ``scores_context`` shows the LLM each ticker's score, its components, its sentiment
   (or "no data") and its eligible actions, so a clamp is a backstop, not the normal path.
3. ``require_position_coverage`` is the ``validate=`` callback for
   ``utils.phase_runner.run_phase``: a ticker with data but no position, or a ticker named
   twice, spends the bounded retry budget instead of leaving a silent gap.
4. ``clamp_actions`` enforces the action policy table on the LLM's own choice (D-08). An
   action outside ``eligible_actions(entry_zone_status, risk_profile, fundamentals_status)``
   becomes MONITOR (both profiles' tables always contain it), the rationale gets the fixed
   sentence `` Action set to MONITOR by policy: <rule>.`` and a clamp record is returned
   (the Flow turns each into a validation warning, so a clamp is never silent). The rule
   text names the table dimension that restricted the action: the ``CURRENT_ENTRY``
   zone row ("waiting for entry" is a contradiction when price is already in the zone) or
   the ``FUNDAMENTALS_UNKNOWN`` row (quality or growth could not be graded). Because it
   reuses ``eligible_actions``, this covers the CURRENT_ENTRY / WAIT-FOR-ENTRY invariant
   that PortfolioBoundsValidator enforces fail-closed, so a run no longer fails in the
   validator after full spend on that class of mistake. A ticker whose price or
   indicators failed never reaches this phase: plan 02-15 records it in failed_tickers
   and excludes it upstream, which is why there is no price_data_error argument here.
   The monitoring triggers the LLM wrote for the original action are kept; the Critic
   reviews the clamped position like any other. Each clamp record carries its ``phase``
   and its message says "draft" or "final", so a warning never claims more than it
   describes; ``clamp_warnings`` adds the finally published action when a later phase
   changed the action again.
5. ``allocator_payload`` builds the allocator input from the clamped actions, the Flow's
   scores and the technical record (entry zone and price); the Flow calls the allocator.
6. ``assemble_strategy`` builds ``InvestorStrategicOutput``: ``composite_score`` from the
   Flow's scores, ``allocation_pct``, trade setups and the three capital buckets from the
   allocator, ``current_price`` from the technical record, ``fundamentals_status`` from the
   fundamental record, and the portfolio ``risk_level`` by the rule below. Nothing numeric
   or graded comes from the LLM's answer.

Portfolio risk_level rule (the planner's choice, the single source; see
02-LLM-ROLE-AUDIT.md). Weight each LONG-BUY and WAIT-FOR-ENTRY position whose
allocation_pct is above 0 by its allocation_pct, and score its technical risk_level
Low 1, Medium 2, High 3. With no such position the portfolio is "Low" (no capital is at
risk). Otherwise the weighted mean r gives:

    r <= 1.5   Low
    r <= 2.0   Medium
    r <= 2.6   High
    above 2.6  Very High

MONITOR and AVOID positions carry no allocation and never weigh in. The mean is rounded
to 6 decimals before it is compared, so the boundaries are exact.
"""
import json
import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from schemas.agent_outputs import (
    InvestorStrategicOutput,
    MarketAnalysisOutput,
    PositionNarrative,
    PositionRecommendation,
    StrategyNarrativeOutput,
)
from utils.action_policy_gate import (
    FUNDAMENTALS_UNKNOWN_ROW,
    VALID_ACTIONS,
    eligible_actions,
    resolve_allowed_actions,
)
from utils.phase_runner import PhaseOutputError
from utils.portfolio_bounds_validator import BoundsViolationError

logger = logging.getLogger(__name__)

PHASE = "draft_strategy"

CLAMP_ACTION = "MONITOR"
CLAMP_SENTENCE = " Action set to MONITOR by policy: {rule}."

# technical risk_level -> points; thresholds are inclusive upper bounds (module docstring).
_RISK_POINTS = {"Low": 1, "Medium": 2, "High": 3}
_RISK_BANDS: Tuple[Tuple[float, str], ...] = ((1.5, "Low"), (2.0, "Medium"), (2.6, "High"))
_RISK_TOP = "Very High"
_DEPLOYED_ACTIONS = ("LONG-BUY", "WAIT-FOR-ENTRY")

_NO_DATA = "no data"
_ERROR_CAP = 200


def _ticker(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


def _ordered(actions: Iterable[str]) -> List[str]:
    """Actions in the canonical order of VALID_ACTIONS."""
    present = set(actions)
    return [a for a in VALID_ACTIONS if a in present]


# ── Composite scores ───────────────────────────────────────────────────────────

def composite_inputs(
    market: Optional[MarketAnalysisOutput], technical: Any, fundamental: Any,
) -> List[Dict[str, Any]]:
    """Input items for ``compute_composite_scores``, one per ticker with technical data, in technical order.

    ``average_sentiment`` is null for every ticker unless the market output says
    ``sentiment_available`` (module docstring). A ticker with no fundamental record gets
    quality and growth UNKNOWN, which the tool scores as a missing dimension.
    """
    sentiments: Dict[str, Optional[float]] = {}
    if market is not None and market.sentiment_available:
        sentiments = {_ticker(c.ticker): c.average_sentiment for c in market.candidate_stocks}
    ratings = {
        _ticker(a.ticker): a.fundamental_rating
        for a in (fundamental.fundamental_analysis if fundamental is not None else [])
    }
    inputs: List[Dict[str, Any]] = []
    for analysis in technical.technical_analysis:
        ticker = _ticker(analysis.ticker)
        rating = ratings.get(ticker)
        inputs.append({
            "ticker": ticker,
            "average_sentiment": sentiments.get(ticker),
            "momentum_score": analysis.momentum_analysis.momentum_score,
            "quality": rating.quality if rating is not None else "UNKNOWN",
            "growth": rating.growth if rating is not None else "UNKNOWN",
        })
    return inputs


def _load_json(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def parse_composite_scores(raw: Any, tickers: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Composite entries by upper-case ticker from the tool result; RuntimeError naming the phase on any gap."""
    data = _load_json(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"{PHASE}: composite scoring returned an unreadable result")
    if "error" in data:
        raise RuntimeError(f"{PHASE}: composite scoring failed: {str(data['error'])[:_ERROR_CAP]}")
    entries = data.get("scores")
    scores: Dict[str, Dict[str, Any]] = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        value = entry.get("composite_score")
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        if valid and 0.0 <= value <= 100.0:
            scores.setdefault(_ticker(entry.get("ticker")), entry)
    missing = [t for t in tickers if t not in scores]
    if missing:
        raise RuntimeError(f"{PHASE}: composite scoring returned no valid score for {', '.join(missing)}")
    return {t: scores[t] for t in tickers}


def require_composite_scores(composite_by_ticker: Dict[str, Dict[str, Any]], tickers: Sequence[str]) -> None:
    """Fail closed (BoundsViolationError, rule ``composite_score_missing``) when a ticker has no Flow score.

    The score is never defaulted: a missing one means the Flow's own scoring did not cover the
    ticker, and a published number must come from a tool, not from 0.0 or from the LLM.
    """
    missing = [t for t in tickers if not isinstance((composite_by_ticker.get(t) or {}).get("composite_score"), (int, float))]
    if missing:
        raise BoundsViolationError([
            {"ticker": t, "rule": "composite_score_missing",
             "expected": "a composite score computed by the Flow", "actual": "none"}
            for t in missing
        ])


# ── Policy: eligible actions and the clamp ─────────────────────────────────────

def policy_context_by_ticker(
    technical: Any, fundamentals_status: Dict[str, str], risk_profile: str,
) -> Dict[str, Dict[str, Optional[str]]]:
    """ticker -> the position context the action policy table reads.

    A ticker with no fundamental record has ``fundamentals_status`` None: permissive, the
    same as the Critic gate and the bounds validator (the policy never blocks on missing data).
    """
    return {
        _ticker(a.ticker): {
            "entry_zone_status": a.momentum_analysis.entry_zone_status,
            "risk_profile": risk_profile,
            "fundamentals_status": fundamentals_status.get(_ticker(a.ticker)),
        }
        for a in technical.technical_analysis
    }


def eligible_by_ticker(
    technical: Any, fundamentals_status: Dict[str, str], risk_profile: str,
) -> Dict[str, frozenset]:
    """ticker -> the actions it may take: ``eligible_actions(entry_zone_status, risk_profile, fundamentals_status)``."""
    return {
        ticker: eligible_actions(
            ctx["entry_zone_status"], risk_profile, ctx["fundamentals_status"],
        )
        for ticker, ctx in policy_context_by_ticker(technical, fundamentals_status, risk_profile).items()
    }


def policy_rule(
    action: str, entry_zone_status: Optional[str], risk_profile: str, fundamentals_status: Optional[str],
) -> str:
    """Why ``action`` is ineligible, naming each table row that excludes it (reads the table, no copy of it)."""
    parts: List[str] = []
    if action not in resolve_allowed_actions(entry_zone_status, risk_profile):
        parts.append(
            f"entry_zone_status {entry_zone_status} does not allow {action} for the {risk_profile} profile"
        )
    if fundamentals_status == "UNKNOWN":
        row = resolve_allowed_actions(None, risk_profile, "UNKNOWN")
        if action not in row:
            parts.append(
                f"{FUNDAMENTALS_UNKNOWN_ROW}: fundamentals could not be graded, so only "
                f"{' or '.join(_ordered(row))} are allowed"
            )
    return "; ".join(parts) or f"{action} is not an eligible action for this ticker"


def _stage(phase: str) -> str:
    """'draft_strategy' -> 'draft', 'final_strategy' -> 'final' (the word a clamp message uses)."""
    return phase.split("_", 1)[0]


def clamp_actions(
    positions: Sequence[PositionNarrative],
    eligible: Dict[str, frozenset],
    context: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    phase: str = PHASE,
) -> Tuple[List[PositionNarrative], List[Dict[str, Any]]]:
    """(positions, clamp records): an ineligible action becomes MONITOR with a fixed rationale sentence.

    ``context`` (from ``policy_context_by_ticker``) lets the rule name the restricting row;
    without it the rule lists the eligible actions. A ticker with no entry in ``eligible``
    is left alone. Inputs are not mutated; a clamped position is a copy. ``phase`` is the
    phase whose action was clamped; it is recorded and named in the message ("draft action"
    or "final action").
    """
    out: List[PositionNarrative] = []
    clamps: List[Dict[str, Any]] = []
    for position in positions:
        ticker = _ticker(position.ticker)
        allowed = eligible.get(ticker)
        if allowed is None or position.action in allowed:
            out.append(position)
            continue
        ctx = (context or {}).get(ticker)
        if ctx is not None:
            rule = policy_rule(
                position.action, ctx.get("entry_zone_status"), ctx.get("risk_profile") or "conservative",
                ctx.get("fundamentals_status"),
            )
        else:
            rule = f"{position.action} is not among the eligible actions {_ordered(allowed)}"
        out.append(position.model_copy(update={
            "action": CLAMP_ACTION,
            "rationale": position.rationale + CLAMP_SENTENCE.format(rule=rule),
        }))
        clamps.append({
            "ticker": ticker,
            "from_action": position.action,
            "to_action": CLAMP_ACTION,
            "rule": rule,
            "phase": phase,
            "message": f"{ticker}: {_stage(phase)} action {position.action} set to {CLAMP_ACTION} by policy: {rule}",
        })
        logger.warning("%s: %s", phase, clamps[-1]["message"])
    return out, clamps


def clamp_warnings(
    clamps: Sequence[Dict[str, Any]], published_actions: Dict[str, str],
) -> List[Dict[str, Any]]:
    """One validation warning per clamp record (a clamp is never silent, D-08).

    ``published_actions`` maps ticker to the action the report finally publishes. A clamp
    describes the phase that made it, so when a later phase published a different action for
    that ticker the warning ends with "The published action is X." and never leaves the reader
    to assume the clamped action is the one in the report. A ticker with no published position
    gets the clamp's own message unchanged.
    """
    warnings: List[Dict[str, Any]] = []
    for clamp in clamps:
        message = clamp["message"]
        published = published_actions.get(clamp["ticker"])
        if published is not None and published != clamp["to_action"]:
            message += f" The published action is {published}."
        warnings.append({"severity": "warning", "ticker": clamp["ticker"], "field": "action", "message": message})
    return warnings


# ── What the LLM reads, and what it must cover ─────────────────────────────────

def excluded_tickers(market: Optional[MarketAnalysisOutput], technical: Any) -> List[str]:
    """Market candidates that have no technical record (their indicators failed), in market order."""
    have = {_ticker(a.ticker) for a in technical.technical_analysis}
    return [
        t for t in dict.fromkeys(_ticker(c.ticker) for c in (market.candidate_stocks if market else []))
        if t and t not in have
    ]


def scores_context(
    inputs: Sequence[Dict[str, Any]],
    composite: Dict[str, Dict[str, Any]],
    eligible: Dict[str, frozenset],
    excluded: Sequence[str],
) -> str:
    """JSON the LLM reads: each ticker's score, components, sentiment or "no data", and eligible actions."""
    rows: List[Dict[str, Any]] = []
    for item in inputs:
        ticker = item["ticker"]
        entry = composite[ticker]
        sentiment = item["average_sentiment"]
        rows.append({
            "ticker": ticker,
            "composite_score": entry["composite_score"],
            "score_components": {
                "sentiment": entry.get("sentiment_component"),
                "technical": entry.get("technical_component"),
                "fundamental": entry.get("fundamental_component"),
            },
            "sentiment": sentiment if sentiment is not None else _NO_DATA,
            "fundamentals_unknown": bool(entry.get("fundamental_unknown")),
            "eligible_actions": _ordered(eligible.get(ticker, VALID_ACTIONS)),
        })
    return json.dumps({
        "note": (
            "Write one position for every ticker in tickers and for no other ticker. "
            "Choose each action from that ticker's eligible_actions."
        ),
        "tickers": rows,
        "excluded": [
            {"ticker": t, "note": "No indicator data this run. Write no position for this ticker."}
            for t in excluded
        ],
    })


def _coverage_error(fields: List[str], what: str, advice: str, phase: str = PHASE) -> PhaseOutputError:
    return PhaseOutputError(
        f"{phase}: {what}; fields: {', '.join(fields)}",
        fields,
        [{"loc": (f,), "msg": advice} for f in fields],
    )


def require_position_coverage(
    narrative: Optional[StrategyNarrativeOutput], tickers: Sequence[str], phase: str = PHASE,
) -> None:
    """Raise PhaseOutputError naming ``positions[T]`` for each ticker without a position or named twice.

    A position for a ticker outside ``tickers`` is not an error here; ``ordered_positions`` drops it.
    """
    seen: Dict[str, int] = {}
    for position in narrative.positions if narrative is not None else []:
        key = _ticker(position.ticker)
        seen[key] = seen.get(key, 0) + 1
    missing = [f"positions[{t}]" for t in tickers if t not in seen]
    if missing:
        raise _coverage_error(
            missing, "positions missing for tickers with scores", "add this ticker's position", phase,
        )
    twice = [f"positions[{t}]" for t in tickers if seen.get(t, 0) > 1]
    if twice:
        raise _coverage_error(
            twice, "tickers named more than once", "keep exactly one position for this ticker", phase,
        )


def ordered_positions(narrative: StrategyNarrativeOutput, tickers: Sequence[str]) -> List[PositionNarrative]:
    """The narrative's positions in ``tickers`` order; a position for any other ticker is ignored and logged."""
    by_ticker: Dict[str, PositionNarrative] = {}
    for position in narrative.positions:
        key = _ticker(position.ticker)
        if key not in tickers:
            logger.info("%s: position for a ticker without scores ignored: %.20s", PHASE, key)
            continue
        by_ticker.setdefault(key, position)
    return [by_ticker[t] for t in tickers if t in by_ticker]


# ── Allocation ─────────────────────────────────────────────────────────────────

def allocator_payload(
    positions: Sequence[PositionNarrative],
    composite_by_ticker: Dict[str, Dict[str, Any]],
    technical_by_ticker: Dict[str, Any],
    risk_profile: str,
) -> Dict[str, Any]:
    """Input of ``allocate_portfolio``: the clamped actions, the Flow's scores, and the technical zone and price.

    Entry zones and the price come from the technical record, never from the LLM. A zone bound
    the record lacks is left out, so the allocator falls back to the current price itself.
    """
    stocks: List[Dict[str, Any]] = []
    for position in positions:
        ticker = _ticker(position.ticker)
        technical = technical_by_ticker[ticker]
        momentum = technical.momentum_analysis
        item: Dict[str, Any] = {
            "ticker": ticker,
            "action": position.action,
            "composite_score": float(composite_by_ticker[ticker]["composite_score"]),
            "current_price": technical.current_price,
        }
        if momentum.entry_zone_low is not None:
            item["entry_zone_low"] = momentum.entry_zone_low
        if momentum.entry_zone_high is not None:
            item["entry_zone_high"] = momentum.entry_zone_high
        stocks.append(item)
    return {"risk_profile": risk_profile, "stocks": stocks}


def parse_allocation(raw: Any) -> Dict[str, Any]:
    """The allocator result as a dict; BoundsViolationError on an error result (as _reprice_final_output does)."""
    result = _load_json(raw)
    if not isinstance(result, dict) or "error" in result or not isinstance(result.get("stocks"), list):
        actual = result.get("error") if isinstance(result, dict) and "error" in result else "unreadable result"
        raise BoundsViolationError([{
            "ticker": None, "rule": "allocator_invocation_error",
            "expected": "successful allocate_portfolio result", "actual": str(actual)[:_ERROR_CAP],
        }])
    return result


# ── Risk level and assembly ────────────────────────────────────────────────────

def derive_portfolio_risk_level(positions: Sequence[Any], technical_by_ticker: Dict[str, Any]) -> str:
    """Portfolio risk_level by the rule in the module docstring.

    ``positions`` need ``ticker``, ``action`` and ``allocation_pct``; ``technical_by_ticker``
    values need ``momentum_analysis.risk_level``. A deployed position with no technical record
    is a ValueError naming the ticker: a grade is never guessed.
    """
    weighted = 0.0
    total = 0.0
    for position in positions:
        if position.action not in _DEPLOYED_ACTIONS or not position.allocation_pct > 0:
            continue
        ticker = _ticker(position.ticker)
        technical = technical_by_ticker.get(ticker)
        if technical is None:
            raise ValueError(f"{PHASE}: no technical record to derive the risk level for {ticker}")
        weighted += position.allocation_pct * _RISK_POINTS[technical.momentum_analysis.risk_level]
        total += position.allocation_pct
    if total <= 0:
        return "Low"
    mean = round(weighted / total, 6)
    for bound, label in _RISK_BANDS:
        if mean <= bound:
            return label
    return _RISK_TOP


def assemble_strategy(
    sector: str,
    risk_profile: str,
    positions: Sequence[PositionNarrative],
    composite_by_ticker: Dict[str, Dict[str, Any]],
    technical_by_ticker: Dict[str, Any],
    fundamentals_status: Dict[str, str],
    allocation: Dict[str, Any],
    overall_strategy: str,
) -> InvestorStrategicOutput:
    """The published draft: the LLM's action, rationale, triggers and cadence plus the Flow's numbers."""
    allocated = {_ticker(o.get("ticker")): o for o in allocation["stocks"] if isinstance(o, dict)}
    built: List[PositionRecommendation] = []
    for position in positions:
        ticker = _ticker(position.ticker)
        outcome = allocated.get(ticker)
        if outcome is None:
            raise BoundsViolationError([{
                "ticker": ticker, "rule": "allocator_missing_ticker",
                "expected": "an allocation for every position", "actual": "none",
            }])
        built.append(PositionRecommendation(
            ticker=ticker,
            action=position.action,
            composite_score=composite_by_ticker[ticker]["composite_score"],
            allocation_pct=outcome["allocation_pct"],
            current_price=technical_by_ticker[ticker].current_price,
            trade_setup=outcome.get("trade_setup"),
            rationale=position.rationale,
            monitoring_triggers=list(position.monitoring_triggers),
            review_frequency=position.review_frequency,
            fundamentals_status=fundamentals_status.get(ticker),
        ))
    return InvestorStrategicOutput(
        sector=sector,
        risk_profile=risk_profile,
        positions=built,
        deployed_pct=allocation["deployed_pct"],
        reserved_pct=allocation["reserved_pct"],
        total_allocated_pct=allocation["total_allocated_pct"],
        cash_reserve_pct=allocation["cash_reserve_pct"],
        overall_strategy=overall_strategy,
        risk_level=derive_portfolio_risk_level(built, technical_by_ticker),
    )
