"""Shared scoring weights used by FundamentalGraderTool and CompositeScoreTool.

The keys are exactly the schema Literals in schemas/agent_outputs.py
(QualityLabel / GrowthLabel) minus "UNKNOWN" (CORR-02, D-10). UNKNOWN has no
points: a dimension with no data has a null score, never a default one
(CORR-11). tests/test_vocabulary.py pins the keys to the Literals.
"""

_QUALITY_SCORE = {"High": 20, "Medium": 10, "Low": 5}
_GROWTH_SCORE = {"High Growth": 10, "Moderate Growth": 7, "Stable": 3, "Declining": 1}
