"""Parse a raw CrewAI result object into a dict.

This helper has no production caller: the Flow validates each phase through
``utils.phase_runner.extract_model``. It stays a public helper because DEBT-01 names it
(moved unchanged in phase 5 from ``ProspectAIFlow._parse_crew_result``).
"""
import json
from typing import Any, Dict


def parse_pipeline_result(crew_result) -> Dict[str, Any]:
    """Extract a JSON dict from a CrewAI result object.

    Handles pydantic task output, json_dict shortcut, markdown fences, and
    plain JSON strings. Falls back to a minimal error dict on parse failure.
    """
    if hasattr(crew_result, "json_dict") and crew_result.json_dict:
        return crew_result.json_dict

    tasks_output = getattr(crew_result, "tasks_output", None)
    if tasks_output:
        last = tasks_output[-1]
        if getattr(last, "pydantic", None):
            return last.pydantic.model_dump(mode="json")
        if getattr(last, "json_dict", None):
            return last.json_dict

    raw = getattr(crew_result, "raw", None) or str(crew_result)
    cleaned = raw.strip()
    for fence in ("```json", "```python", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "pipeline_version": "2.0",
            "parse_error": True,
            "raw_output": raw,
            "portfolio_summary": {"portfolio_rationale": raw[:500]},
        }
