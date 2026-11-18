"""Shared scoring weights used by FundamentalGraderTool and CompositeScoreTool.

It also holds the ATR volatility thresholds shared by TechnicalAnalysisTool (the
status label) and TechnicalInterpretationTool (risk_level), so the two labels
cannot drift apart (phase 5, D-03).

The keys are exactly the schema Literals in schemas/agent_outputs.py
(QualityLabel / GrowthLabel) minus "UNKNOWN" (CORR-02, D-10). UNKNOWN has no
points: a dimension with no data has a null score, never a default one
(CORR-11). tests/test_vocabulary.py pins the keys to the Literals.
"""

_QUALITY_SCORE = {"High": 20, "Medium": 10, "Low": 5}
_GROWTH_SCORE = {"High Growth": 10, "Moderate Growth": 7, "Stable": 3, "Declining": 1}

# ATR divided by current price. Above HIGH is high volatility, below LOW is low,
# both bounds strict. LOW is the interpretation tool's cutoff, which drives the
# published risk_level; the status label follows it (phase 5, D-03).
ATR_RATIO_HIGH = 0.03
ATR_RATIO_LOW = 0.015
