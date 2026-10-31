"""Flow-built technical records and the merge with the LLM's narrative (CORR-10, CORR-01).

The Technical Analyst used to relay ``calculate_technical_indicators``, reshape its
JSON, copy prices and indicators, and invent ``trend_strength``,
``support_resistance`` and ``technical_score``. Now the Flow calls the tool itself
(utils/flow_tools.py) and this module turns its output into one record per ticker:
current price, raw indicators, momentum score, risk level, entry zone, regime and
``trend_strength``. The LLM only writes the fields in ``TechnicalNarrative``
(schemas/agent_outputs.py): ``overall_signal``, ``key_signals``,
``comprehensive_analysis``, ``investment_recommendation`` and the summary.
``merge_technical`` joins the two into the published ``TechnicalAnalysisOutput``.
Nothing the LLM answers can reach a number or a label except ``overall_signal``,
which is the analyst's reading of the indicators and is a strict four-value Literal.

trend_strength comes from the ADX value, never from the tool's ADX label and never
from the model. The tool labels ADX "Strong Trend" / "Moderate Trend" / "Weak
Trend"; "Moderate" is not a ``trend_strength`` value, and the model reproducing that
label was the likely origin of the Phase 1 Semiconductors failure (RESEARCH F8d).
Thresholds (the planner's choice, documented here as the single source):

    ADX < 15            Very Weak
    15 <= ADX < 20      Weak
    20 <= ADX < 25      Neutral
    25 <= ADX < 40      Strong
    ADX >= 40           Very Strong
    ADX missing         None (never a default grade, D-07)

A ticker whose indicators fail, or whose tool entry lacks a value a published field
needs (price, momentum score, risk level, entry zone, regime), is a failed ticker:
it is listed in ``TechnicalAnalysisOutput.failed_tickers`` with the tool's error text
cut to 200 characters and is excluded from the published analyses. Indicators are
never invented for it.

``require_technical_coverage`` is the ``validate=`` callback for
``utils.phase_runner.run_phase``: a ticker with data but no narrative entry is a
validation failure that spends the bounded retry budget, not a silent gap.
"""
import json
import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from schemas.agent_outputs import (
    FailedTicker,
    MomentumAnalysis,
    RawIndicators,
    StockTechnicalAnalysis,
    TechnicalAnalysisOutput,
    TechnicalNarrativeOutput,
)
from utils.phase_runner import PhaseOutputError

logger = logging.getLogger(__name__)

PHASE = "technical_analysis"

ERROR_CAP = 200

# (exclusive upper bound, label), in ascending order; at or above the last bound is "Very Strong".
_ADX_BANDS: Tuple[Tuple[float, str], ...] = (
    (15.0, "Very Weak"),
    (20.0, "Weak"),
    (25.0, "Neutral"),
    (40.0, "Strong"),
)
_ADX_TOP = "Very Strong"

_RISK_LEVELS = ("Low", "Medium", "High")
_ENTRY_STATUSES = ("PULLBACK_ENTRY", "CURRENT_ENTRY", "BELOW_ZONE")
_REGIMES = ("TRENDING", "REVERTING", "NEUTRAL")
# The tool's own wording for "not enough history"; that is absence of data, so null.
_NO_DATA_STATUS = "Insufficient Data"


def _num(value: Any) -> Optional[float]:
    """A finite number, else None (bool, strings, NaN and inf are absence of data)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _section(entry: Any, name: str) -> Dict[str, Any]:
    section = entry.get(name) if isinstance(entry, dict) else None
    return section if isinstance(section, dict) else {}


def _ticker(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


def _short(text: Any) -> str:
    return (text if isinstance(text, str) and text else "unknown error")[:ERROR_CAP]


def _status(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value and value != _NO_DATA_STATUS else None


def trend_strength_from_adx(adx: Any) -> Optional[str]:
    """Trend-strength label for an ADX value (table in the module docstring); None when missing."""
    value = _num(adx)
    if value is None:
        return None
    for bound, label in _ADX_BANDS:
        if value < bound:
            return label
    return _ADX_TOP


def _failed(ticker: str, error: Any) -> FailedTicker:
    return FailedTicker(ticker=ticker, error=_short(error))


def _record(ticker: str, entry: Dict[str, Any]) -> "Dict[str, Any] | FailedTicker":
    """A record dict for a successful entry, else the FailedTicker explaining why not."""
    if "error" in entry:
        return _failed(ticker, entry.get("error"))
    price = _num(_section(entry, "stock_data").get("current_price"))
    if price is None or price <= 0:
        return _failed(ticker, "no valid current price in the indicator result")
    interp = _section(entry, "interpretation")
    if not interp:
        return _failed(ticker, "no interpretation in the indicator result")
    if "error" in interp:
        return _failed(ticker, interp.get("error"))

    momentum_score = _num(interp.get("momentum_score"))
    low = _num(interp.get("entry_zone_low"))
    high = _num(interp.get("entry_zone_high"))
    bad = [
        name for name, ok in (
            ("momentum_score", momentum_score is not None and 0.0 <= momentum_score <= 10.0),
            ("risk_level", interp.get("risk_level") in _RISK_LEVELS),
            ("entry_zone_status", interp.get("entry_zone_status") in _ENTRY_STATUSES),
            ("regime", interp.get("regime") in _REGIMES),
            ("entry_zone_low", low is not None),
            ("entry_zone_high", high is not None),
        ) if not ok
    ]
    if bad:
        return _failed(ticker, "indicator interpretation missing or invalid: " + ", ".join(bad))

    indicators = _section(entry, "technical_indicators")
    momentum = _section(indicators, "momentum")
    trend = _section(indicators, "trend")
    adx = _num(_section(trend, "adx").get("current"))
    raw = RawIndicators(
        rsi=_num(_section(momentum, "rsi").get("current")),
        stochastic_status=_status(_section(momentum, "stochastic").get("status")),
        macd_status=_status(_section(momentum, "macd").get("status")),
        ma_status=_status(_section(trend, "moving_averages").get("status")),
        adx=adx,
    )
    return {
        "current_price": price,
        "raw_indicators": raw,
        "trend_strength": trend_strength_from_adx(adx),
        "momentum_analysis": {
            "momentum_score": momentum_score,
            "risk_level": interp["risk_level"],
            "entry_zone_status": interp["entry_zone_status"],
            "entry_zone_low": low,
            "entry_zone_high": high,
            "regime": interp["regime"],
        },
    }


def build_technical_records(
    tool_result: Any, tickers: Optional[Iterable[str]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[FailedTicker]]:
    """(records by upper-case ticker, failed tickers) from a calculate_technical_indicators result.

    ``tickers`` are the requested tickers: one the tool never returned is failed,
    and a whole-call error (no per-ticker list) fails every requested ticker with
    the tool's error text. Without ``tickers`` only what the tool returned is judged.
    """
    requested = [t for t in (_ticker(x) for x in (tickers or [])) if t]
    entries = tool_result.get("technical_analysis") if isinstance(tool_result, dict) else None
    records: Dict[str, Dict[str, Any]] = {}
    failed: Dict[str, FailedTicker] = {}

    if not isinstance(entries, list):
        error = tool_result.get("error") if isinstance(tool_result, dict) else None
        return {}, [_failed(t, error or "no result from the indicator tool") for t in dict.fromkeys(requested)]

    for entry in entries:
        ticker = _ticker(entry.get("ticker")) if isinstance(entry, dict) else ""
        if not ticker or ticker in records or ticker in failed:
            continue
        if requested and ticker not in requested:
            continue
        outcome = _record(ticker, entry)
        if isinstance(outcome, FailedTicker):
            failed[ticker] = outcome
        else:
            records[ticker] = outcome
    for ticker in requested:
        if ticker not in records and ticker not in failed:
            failed[ticker] = _failed(ticker, "no result returned for this ticker")
    return records, list(failed.values())


def narrative_context(records: Dict[str, Dict[str, Any]], failed: List[FailedTicker]) -> str:
    """JSON the LLM reads: the Flow's numbers and labels per ticker.

    The model may cite these in prose. It cannot change them: the published values
    come from ``records``, not from its answer.
    """
    rows: List[Dict[str, Any]] = []
    for ticker, rec in records.items():
        momentum = rec["momentum_analysis"]
        ri = rec["raw_indicators"]
        rows.append({
            "ticker": ticker,
            "current_price": rec["current_price"],
            "indicators": {
                "rsi": ri.rsi,
                "stochastic_status": ri.stochastic_status,
                "macd_status": ri.macd_status,
                "ma_status": ri.ma_status,
                "adx": ri.adx,
                "trend_strength": rec["trend_strength"],
            },
            "momentum_score": momentum["momentum_score"],
            "risk_level": momentum["risk_level"],
            "entry_zone": {
                "low": momentum["entry_zone_low"],
                "high": momentum["entry_zone_high"],
                "status": momentum["entry_zone_status"],
            },
            "regime": momentum["regime"],
        })
    return json.dumps({
        "stock_technicals": rows,
        "no_data": [
            {"ticker": f.ticker, "note": "No indicator data this run. Write no analysis for this ticker."}
            for f in failed
        ],
    })


def require_technical_coverage(
    narrative: Optional[TechnicalNarrativeOutput], records: Dict[str, Dict[str, Any]],
) -> None:
    """Raise PhaseOutputError naming ``analyses[T]`` for each record ticker without a narrative."""
    present = {_ticker(a.ticker) for a in narrative.analyses} if narrative is not None else set()
    missing = [t for t in records if t not in present]
    if not missing:
        return
    fields = [f"analyses[{t}]" for t in missing]
    raise PhaseOutputError(
        f"{PHASE}: narrative missing for tickers with data; fields: {', '.join(fields)}",
        fields,
        [{"loc": (f,), "msg": "add this ticker's narrative entry"} for f in fields],
    )


def merge_technical(
    sector: str,
    tickers: List[str],
    records: Dict[str, Dict[str, Any]],
    narrative: TechnicalNarrativeOutput,
    failed: List[FailedTicker],
) -> TechnicalAnalysisOutput:
    """Published output in ``tickers`` (market) order: Flow records plus the LLM's narrative text.

    Narrative entries for failed tickers, or for tickers outside ``tickers``, are
    ignored. Raises RuntimeError when no requested ticker has a record.
    """
    requested = {t: records[t] for t in tickers if t in records}
    if not requested:
        raise RuntimeError(f"{PHASE}: no ticker has indicator data; refusing to publish invented indicators")
    require_technical_coverage(narrative, requested)

    by_ticker: Dict[str, Any] = {}
    for item in narrative.analyses:
        key = _ticker(item.ticker)
        if key not in requested:
            logger.info("%s: narrative for a ticker without indicator data ignored: %.20s", PHASE, key)
            continue
        by_ticker.setdefault(key, item)

    analyses: List[StockTechnicalAnalysis] = []
    for ticker, record in requested.items():
        item = by_ticker[ticker]
        analyses.append(StockTechnicalAnalysis(
            ticker=ticker,
            current_price=record["current_price"],
            raw_indicators=record["raw_indicators"],
            momentum_analysis=MomentumAnalysis(
                trend_strength=record["trend_strength"],
                support_resistance=None,
                key_signals=list(item.key_signals),
                comprehensive_analysis=item.comprehensive_analysis,
                overall_signal=item.overall_signal,
                **record["momentum_analysis"],
            ),
            investment_recommendation=item.investment_recommendation,
        ))
    return TechnicalAnalysisOutput(
        sector=sector,
        technical_analysis=analyses,
        summary=narrative.summary,
        failed_tickers=list(failed),
    )
