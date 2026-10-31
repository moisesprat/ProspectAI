"""One-vocabulary guard for fundamental labels (CORR-02, D-10).

The schema (schemas/agent_outputs.py) is the only source of the label names and
values. These tests pin the grader, the scoring tables, the composite tool, the
Flow's slim context, the Critic reference table and tasks.yaml to it, so a drift
in any one of them fails here instead of silently translating at runtime.
"""

import inspect
import itertools
import json
import re
from pathlib import Path
from typing import get_args
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

import prospect_ai_flow
from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import (
    CandidateStock,
    DataStatus,
    FundamentalAnalysisOutput,
    FundamentalRating,
    FundamentalsStatus,
    GrowthLabel,
    MarketAnalysisOutput,
    MomentumAnalysis,
    QualityLabel,
    RawIndicators,
    StockFundamentalAnalysis,
    StockTechnicalAnalysis,
    SupportResistance,
    TechnicalAnalysisOutput,
    ValuationLabel,
    ValuationMetrics,
)
from utils.composite_score_tool import CompositeScoreTool
from utils.fundamental_grader_tool import FundamentalGraderTool, fundamentals_status
from utils.scoring_constants import _GROWTH_SCORE, _QUALITY_SCORE

TASKS_YAML = Path(__file__).resolve().parent.parent / "config" / "tasks.yaml"

_ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "MODEL": "claude-haiku-4-5-20251001",
    "REDDIT_CLIENT_ID": "test-id",
    "REDDIT_CLIENT_SECRET": "test-secret",
}


def _members(literal) -> set:
    return set(get_args(literal))


# ── Tables and grader ────────────────────────────────────────────────────────

def test_scoring_tables_match_schema():
    assert set(_QUALITY_SCORE) == _members(QualityLabel) - {"UNKNOWN"}
    assert set(_GROWTH_SCORE) == _members(GrowthLabel) - {"UNKNOWN"}


def test_unknown_is_in_every_fundamental_literal():
    for literal in (ValuationLabel, QualityLabel, GrowthLabel):
        assert "UNKNOWN" in _members(literal)
    assert _members(DataStatus) == {"ok", "partial", "failed"}
    assert _members(FundamentalsStatus) == {"AVAILABLE", "UNKNOWN"}


def _entry(pe, ps, cr, de, fcf, rev) -> dict:
    return {
        "ticker": "T",
        "valuation": {"pe_ratio": pe, "ps_ratio": ps},
        "balance_sheet": {"current_ratio": cr, "debt_to_equity": de, "free_cash_flow": fcf},
        "growth": {"revenue_growth_yoy": rev},
    }


def test_grader_values_in_schema():
    grid = itertools.product(
        (None, 5.0, 20.0, 30.0, 60.0),   # pe
        (None, 2.0, 4.0, 9.0),           # ps
        (None, 0.5, 1.2, 2.0),           # current ratio
        (None, 0.5, 1.5, 4.0),           # debt to equity
        (None, -1.0, 5.0),               # fcf
        (None, -0.1, 0.02, 0.1, 0.3),    # revenue growth
    )
    tool = FundamentalGraderTool()
    seen_quality, seen_growth = set(), set()
    for combo in grid:
        g = tool._grade_one(_entry(*combo))
        assert g["valuation"] in _members(ValuationLabel), combo
        assert g["quality"] in _members(QualityLabel), combo
        assert g["growth"] in _members(GrowthLabel), combo
        assert g["data_status"] in _members(DataStatus), combo
        # Building the schema model proves the labels validate end to end.
        FundamentalRating(valuation=g["valuation"], quality=g["quality"], growth=g["growth"])
        seen_quality.add(g["quality"])
        seen_growth.add(g["growth"])
    assert seen_quality == _members(QualityLabel)
    assert seen_growth == _members(GrowthLabel)


def test_grader_failed_entry_values_in_schema():
    g = FundamentalGraderTool()._grade_one({"ticker": "X", "error": "boom"})
    assert g["data_status"] in _members(DataStatus)
    FundamentalRating(valuation=g["valuation"], quality=g["quality"], growth=g["growth"])


def test_grader_output_keys_are_the_documented_contract():
    g = FundamentalGraderTool()._grade_one(_entry(20, None, 2.0, 0.5, 1.0, 0.1))
    assert set(g) == {
        "ticker", "valuation", "quality", "growth", "data_status",
        "quality_score", "growth_score", "fundamental_component", "fundamental_unknown",
    }


# ── Composite tool (the grader's JSON feeds it) ──────────────────────────────

def _composite(*stocks) -> dict:
    return json.loads(CompositeScoreTool()._run(json.dumps(list(stocks))))


def test_composite_accepts_every_schema_label():
    for q in _members(QualityLabel):
        for gr in _members(GrowthLabel):
            out = _composite({"ticker": "A", "average_sentiment": 0.0,
                              "momentum_score": 5, "quality": q, "growth": gr})
            assert "error" not in out, (q, gr)


def test_composite_rejects_legacy_labels():
    out = _composite({"ticker": "nvda", "average_sentiment": 0.0, "momentum_score": 5,
                      "quality": "STRONG", "growth": "High Growth"})
    assert "error" in out
    assert "NVDA" in out["error"] and "STRONG" in out["error"]
    out = _composite({"ticker": "AMD", "average_sentiment": 0.0, "momentum_score": 5,
                      "quality": "High", "growth": "MODERATE"})
    assert "AMD" in out["error"] and "MODERATE" in out["error"]


def test_composite_rejects_lowercase_labels():
    # Strict validation (D-11): no case or whitespace normalisation.
    out = _composite({"ticker": "A", "average_sentiment": 0.0, "momentum_score": 5,
                      "quality": "high", "growth": "Stable"})
    assert "error" in out and "high" in out["error"]
    out = _composite({"ticker": "A", "average_sentiment": 0.0, "momentum_score": 5,
                      "quality": "High ", "growth": "Stable"})
    assert "error" in out


def test_composite_missing_keys_are_unknown():
    out = _composite({"ticker": "A", "average_sentiment": 0.0, "momentum_score": 5})
    row = out["scores"][0]
    assert row["fundamental_component"] is None
    assert row["fundamental_unknown"] is True


def test_composite_missing_sentiment_key_is_unavailable_not_zero():
    out = _composite({"ticker": "A", "momentum_score": 5, "quality": "High", "growth": "Stable"})
    row = out["scores"][0]
    assert row["sentiment_unavailable"] is True
    assert row["sentiment_component"] is None


def test_composite_missing_momentum_is_an_error_naming_the_ticker():
    out = _composite({"ticker": "zzz", "average_sentiment": 0.0,
                      "quality": "High", "growth": "Stable"})
    assert "error" in out and "ZZZ" in out["error"]


# ── Flow context and Critic reference table ──────────────────────────────────

def _market() -> MarketAnalysisOutput:
    return MarketAnalysisOutput(
        sector="Technology",
        candidate_stocks=[CandidateStock(
            ticker="AAA", mention_count=3, average_sentiment=0.25, relevance_score=0.8,
            rationale="A candidate rationale that is comfortably longer than fifty characters.",
        )],
        summary="s" * 120,
    )


def _technical() -> TechnicalAnalysisOutput:
    return TechnicalAnalysisOutput(
        sector="Technology",
        technical_analysis=[StockTechnicalAnalysis(
            ticker="AAA", current_price=10.0,
            raw_indicators=RawIndicators(rsi=55.0, stochastic_status="Neutral", macd_status="Bullish"),
            momentum_analysis=MomentumAnalysis(
                momentum_score=6.5, risk_level="Medium", trend_strength="Strong",
                key_signals=["x"], support_resistance=SupportResistance(support=9.0, resistance=12.0),
                comprehensive_analysis="c" * 60, entry_zone_status="CURRENT_ENTRY",
            ),
            investment_recommendation="r" * 60,
        )],
        summary="s" * 120,
    )


def _fundamental(valuation="EXPENSIVE", quality="Medium", growth="Stable",
                 data_status="partial") -> FundamentalAnalysisOutput:
    return FundamentalAnalysisOutput(
        sector="Technology",
        fundamental_analysis=[StockFundamentalAnalysis(
            ticker="AAA", company_name="Triple A",
            valuation_metrics=ValuationMetrics(pe_ratio=30.0),
            fundamental_rating=FundamentalRating(valuation=valuation, quality=quality, growth=growth),
            key_strengths=["strength"], key_risks=["risk"], investment_thesis="a thesis text",
            data_status=data_status,
        )],
        summary="s" * 120,
    )


@pytest.fixture
def flow():
    with patch.dict("os.environ", _ANTHROPIC_ENV), \
         patch("prospect_ai_flow.TaskFactory") as MockFactory:
        MockFactory.return_value = MagicMock()
        f = ProspectAIFlow()
        f._tracker = None
        f.state.sector = "Technology"
        f.state.today = "2026-04-29"
        yield f


def test_flow_has_no_translation_maps():
    legacy = re.compile(r"\b(STRONG|ADEQUATE|MODERATE|DECLINING)\b")
    for fn in (ProspectAIFlow._slim_fundamental, ProspectAIFlow._critic_reference_table):
        src = inspect.getsource(fn)
        assert not legacy.search(src), fn.__name__
        assert "_quality_map" not in src and "_growth_map" not in src, fn.__name__
    assert not hasattr(prospect_ai_flow, "_quality_map")


def test_slim_fundamental_uses_schema_keys(flow):
    flow.state.fundamental_output = _fundamental()
    slim = json.loads(flow._slim_fundamental())
    assessment = slim["stock_analyses"][0]["assessment"]
    assert set(assessment) == {
        "valuation", "quality", "growth", "data_status", "fundamentals_status",
        "fundamental_summary", "risk_factors", "catalysts",
    }
    assert assessment["valuation"] == "EXPENSIVE"
    assert assessment["quality"] == "Medium"
    assert assessment["growth"] == "Stable"
    assert assessment["data_status"] == "partial"
    assert assessment["fundamentals_status"] == "AVAILABLE"


def test_slim_fundamental_copies_unknown_verbatim(flow):
    flow.state.fundamental_output = _fundamental(
        valuation="UNKNOWN", quality="UNKNOWN", growth="UNKNOWN", data_status="failed")
    assessment = json.loads(flow._slim_fundamental())["stock_analyses"][0]["assessment"]
    assert assessment["quality"] == "UNKNOWN"
    assert assessment["data_status"] == "failed"
    assert assessment["fundamentals_status"] == "UNKNOWN"


def test_reference_table_uses_schema_keys(flow):
    flow.state.market_output = _market()
    flow.state.technical_output = _technical()
    flow.state.fundamental_output = _fundamental(valuation="VERY_EXPENSIVE", quality="Low")
    rows = json.loads(flow._critic_reference_table())["reference_table"]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {
        "ticker", "rsi", "stochastic_status", "macd_status", "entry_zone_status",
        "momentum_score", "average_sentiment", "valuation", "quality", "fundamentals_status",
    }
    assert row["valuation"] in _members(ValuationLabel)
    assert row["quality"] in _members(QualityLabel)
    assert (row["valuation"], row["quality"]) == ("VERY_EXPENSIVE", "Low")
    assert row["fundamentals_status"] == "AVAILABLE"


def test_fundamentals_status_helper_matches_flow_usage():
    assert fundamentals_status("Low", "Declining") == "AVAILABLE"
    assert fundamentals_status("UNKNOWN", "Declining") == "UNKNOWN"


# ── Prompts ──────────────────────────────────────────────────────────────────

def test_tasks_yaml_has_no_legacy_labels():
    text = TASKS_YAML.read_text(encoding="utf-8")
    assert not re.search(r"\b(STRONG|ADEQUATE|WEAK|MODERATE|DECLINING)\b", text)
    for legacy_key in ("financial_health", "growth_outlook", "valuation_grade"):
        assert legacy_key not in text, legacy_key


def test_critic_checks_use_schema_labels():
    from config.task_config_loader import TaskConfigLoader

    desc = TaskConfigLoader().get_task_config("critique_review")["description"]
    assert "valuation=VERY_EXPENSIVE" in desc
    assert "quality=Low" in desc


def test_prompt_enum_hints_match_schema():
    text = TASKS_YAML.read_text(encoding="utf-8")
    quality_hint = "|".join(sorted(_members(QualityLabel), key=["High", "Medium", "Low", "UNKNOWN"].index))
    growth_order = ["High Growth", "Moderate Growth", "Stable", "Declining", "UNKNOWN"]
    growth_hint = "|".join(sorted(_members(GrowthLabel), key=growth_order.index))
    assert f'"quality": "<{quality_hint}>"' in text
    assert f'"growth": "<{growth_hint}>"' in text


# ── Technical risk_level (D-11) ──────────────────────────────────────────────

def test_risk_level_labels_match_schema():
    from utils import technical_interpretation_tool

    src = inspect.getsource(technical_interpretation_tool)
    emitted = set(re.findall(r'risk_level = "([^"]+)"', src))
    schema = _members(MomentumAnalysis.model_fields["risk_level"].annotation)
    assert emitted == schema == {"Low", "Medium", "High"}


def test_risk_level_is_strict():
    base = dict(
        momentum_score=5.0, trend_strength="Neutral", key_signals=["x"],
        support_resistance=SupportResistance(support=1.0, resistance=2.0),
        comprehensive_analysis="c" * 60,
    )
    assert MomentumAnalysis(risk_level="High", **base).risk_level == "High"
    for bad in ("HIGH", "high", "MEDIUM"):
        with pytest.raises(ValidationError):
            MomentumAnalysis(risk_level=bad, **base)
