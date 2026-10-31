"""Flow-built fundamental records and the merge with the LLM's narrative (CORR-10, CORR-11).

The Fundamental Analyst used to relay two tools and copy their numbers and
grades into a schema. Now the Flow calls ``fetch_fundamental_data`` and
``grade_fundamental_data`` itself (utils/flow_tools.py) and this module turns
their output into one record per ticker: company name, ``ValuationMetrics``, the
three grade labels and ``data_status``. The LLM only writes the four narrative
fields in ``FundamentalNarrative`` (schemas/agent_outputs.py); ``merge_fundamental``
joins the two into the published ``FundamentalAnalysisOutput``. Nothing the LLM
answers can reach a number, a label or ``data_status`` (D-06, D-15).

Absence of data is never graded (CORR-11, D-07). A ticker whose fetch failed,
whose grade is missing, or whose grade carries a value outside the schema's
vocabulary is ``failed``: UNKNOWN labels, empty metrics (every field null, never
0.0) and fixed "Fundamental data unavailable" text written here, not by the model.
A ticker the fetch never returned is treated the same way.

``require_narrative_coverage`` is the ``validate=`` callback for
``utils.phase_runner.run_phase``: a ticker with data but no narrative entry is a
validation failure that spends the bounded retry budget, not a silent gap.
"""
import json
import logging
import math
from typing import Any, Dict, Iterable, List, Optional

from pydantic import ValidationError

from schemas.agent_outputs import (
    FundamentalAnalysisOutput,
    FundamentalNarrativeOutput,
    FundamentalRating,
    StockFundamentalAnalysis,
    ValuationMetrics,
)
from utils.phase_runner import PhaseOutputError

logger = logging.getLogger(__name__)

PHASE = "fundamental_analysis"

UNAVAILABLE_STRENGTHS: List[str] = ["Fundamental data unavailable"]
UNAVAILABLE_THESIS = "No fundamental data available for this ticker."
UNAVAILABLE_SUMMARY = (
    "Fundamental data could not be retrieved for any candidate in this run, so no "
    "valuation, quality or growth grade is available. Every ticker is reported as "
    "UNKNOWN rather than graded."
)

_DATA_STATUSES = ("ok", "partial", "failed")


def _num(value: Any) -> Optional[float]:
    """A finite number, else None (bool, strings, NaN and inf are absence of data)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _section(entry: Dict[str, Any], name: str) -> Dict[str, Any]:
    section = entry.get(name)
    return section if isinstance(section, dict) else {}


def _ticker(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


def failed_record(ticker: str) -> Dict[str, Any]:
    """UNKNOWN labels, null metrics, data_status failed (D-07)."""
    return {
        "company_name": ticker,
        "valuation_metrics": ValuationMetrics(),
        "fundamental_rating": FundamentalRating(
            valuation="UNKNOWN", quality="UNKNOWN", growth="UNKNOWN",
        ),
        "data_status": "failed",
    }


def _metrics(entry: Dict[str, Any]) -> ValuationMetrics:
    valuation = _section(entry, "valuation")
    profitability = _section(entry, "profitability")
    growth = _section(entry, "growth")
    balance = _section(entry, "balance_sheet")
    dividend = _section(entry, "dividend")
    dividend_yield = _num(dividend.get("dividend_yield"))
    return ValuationMetrics(
        pe_ratio=_num(valuation.get("pe_ratio")),
        pb_ratio=_num(valuation.get("pb_ratio")),
        ev_ebitda=_num(valuation.get("ev_ebitda")),
        price_to_sales=_num(valuation.get("ps_ratio")),
        debt_to_equity=_num(balance.get("debt_to_equity")),
        roe=_num(profitability.get("return_on_equity")),
        revenue_growth_yoy=_num(growth.get("revenue_growth_yoy")),
        earnings_growth_yoy=_num(growth.get("earnings_growth_yoy")),
        free_cash_flow=_num(balance.get("free_cash_flow")),
        dividend_yield=dividend_yield if dividend_yield is not None and dividend_yield >= 0 else None,
    )


def _loads(text: Any) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _grades_by_ticker(grades_json: str) -> Dict[str, Dict[str, Any]]:
    parsed = _loads(grades_json)
    grades = parsed.get("grades") if isinstance(parsed, dict) else None
    if not isinstance(grades, list):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for grade in grades:
        if isinstance(grade, dict) and _ticker(grade.get("ticker")):
            out.setdefault(_ticker(grade["ticker"]), grade)
    return out


def _record(ticker: str, entry: Dict[str, Any], grade: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if "error" in entry or grade is None:
        return failed_record(ticker)
    status = grade.get("data_status")
    if status not in _DATA_STATUSES or status == "failed":
        return failed_record(ticker)
    try:
        rating = FundamentalRating(
            valuation=grade.get("valuation"), quality=grade.get("quality"), growth=grade.get("growth"),
        )
    except ValidationError:
        # A grade outside the schema vocabulary is not trusted and not guessed at.
        logger.warning("%s: grade for %s is outside the schema vocabulary; treated as failed", PHASE, ticker)
        return failed_record(ticker)
    name = _section(entry, "meta").get("company_name")
    return {
        "company_name": name.strip() if isinstance(name, str) and name.strip() else ticker,
        "valuation_metrics": _metrics(entry),
        "fundamental_rating": rating,
        "data_status": status,
    }


def build_fundamental_records(fetch_json: str, grades_json: str) -> Dict[str, Dict[str, Any]]:
    """One record per fetched ticker, keyed by upper-case ticker, in fetch order.

    A whole-call fetch error yields no records (``merge_fundamental`` then treats
    every requested ticker as failed). A ticker missing from the grades, or with
    an unusable grade, is a failed record.
    """
    fetched = _loads(fetch_json)
    entries = fetched.get("fundamentals") if isinstance(fetched, dict) else None
    if not isinstance(entries, list):
        return {}
    grades = _grades_by_ticker(grades_json)
    records: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not _ticker(entry.get("ticker")):
            continue
        ticker = _ticker(entry["ticker"])
        records.setdefault(ticker, _record(ticker, entry, grades.get(ticker)))
    return records


def _is_failed(records: Dict[str, Dict[str, Any]], ticker: str) -> bool:
    record = records.get(ticker)
    return record is None or record["data_status"] == "failed"


def narrative_context(tickers: Iterable[str], records: Dict[str, Dict[str, Any]]) -> str:
    """JSON the LLM reads: the Flow's numbers, labels and data_status per ticker.

    The model may cite these in prose. It cannot change them: the published
    values come from ``records``, not from its answer.
    """
    rows: List[Dict[str, Any]] = []
    for ticker in tickers:
        if _is_failed(records, ticker):
            rows.append({
                "ticker": ticker,
                "data_status": "failed",
                "note": "No fundamental data this run. Write no narrative for this ticker.",
            })
            continue
        record = records[ticker]
        rating = record["fundamental_rating"]
        rows.append({
            "ticker": ticker,
            "company_name": record["company_name"],
            "data_status": record["data_status"],
            "valuation": rating.valuation,
            "quality": rating.quality,
            "growth": rating.growth,
            "metrics": record["valuation_metrics"].model_dump(exclude_none=True),
        })
    return json.dumps({"stock_fundamentals": rows})


def require_narrative_coverage(
    narrative: FundamentalNarrativeOutput, records: Dict[str, Dict[str, Any]],
) -> None:
    """Raise PhaseOutputError naming ``analyses[T]`` for each non-failed ticker without a narrative."""
    present = {_ticker(a.ticker) for a in narrative.analyses} if narrative is not None else set()
    missing = [t for t in records if not _is_failed(records, t) and t not in present]
    if not missing:
        return
    fields = [f"analyses[{t}]" for t in missing]
    raise PhaseOutputError(
        f"{PHASE}: narrative missing for tickers with data; fields: {', '.join(fields)}",
        fields,
        [{"loc": (f,), "msg": "add this ticker's narrative entry"} for f in fields],
    )


def merge_fundamental(
    sector: str,
    tickers: List[str],
    records: Dict[str, Dict[str, Any]],
    narrative: Optional[FundamentalNarrativeOutput],
) -> FundamentalAnalysisOutput:
    """Published output in ``tickers`` order: Flow records plus the LLM's narrative text.

    Failed tickers get the fixed unavailable text; narrative entries for them, and
    for tickers outside ``tickers``, are ignored. ``narrative`` may be None only
    when no ticker has data.
    """
    requested = {t: records[t] for t in tickers if t in records}
    require_narrative_coverage(narrative, requested)

    by_ticker: Dict[str, Any] = {}
    for item in (narrative.analyses if narrative is not None else []):
        key = _ticker(item.ticker)
        if key not in tickers:
            logger.info("%s: narrative for a ticker outside the candidate list ignored: %.20s", PHASE, key)
            continue
        by_ticker.setdefault(key, item)

    analyses: List[StockFundamentalAnalysis] = []
    for ticker in tickers:
        if _is_failed(records, ticker):
            record = failed_record(ticker)
            analyses.append(StockFundamentalAnalysis(
                ticker=ticker,
                company_name=record["company_name"],
                valuation_metrics=record["valuation_metrics"],
                fundamental_rating=record["fundamental_rating"],
                key_strengths=list(UNAVAILABLE_STRENGTHS),
                key_risks=list(UNAVAILABLE_STRENGTHS),
                investment_thesis=UNAVAILABLE_THESIS,
                data_status="failed",
            ))
            continue
        record = records[ticker]
        item = by_ticker[ticker]
        analyses.append(StockFundamentalAnalysis(
            ticker=ticker,
            company_name=record["company_name"],
            valuation_metrics=record["valuation_metrics"],
            fundamental_rating=record["fundamental_rating"],
            key_strengths=list(item.key_strengths),
            key_risks=list(item.key_risks),
            investment_thesis=item.investment_thesis,
            data_status=record["data_status"],
        ))
    return FundamentalAnalysisOutput(
        sector=sector,
        fundamental_analysis=analyses,
        summary=narrative.summary if narrative is not None else UNAVAILABLE_SUMMARY,
    )
