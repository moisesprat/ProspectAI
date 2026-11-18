"""Tests for parse_pipeline_result (phase 5, DEBT-01; moved from tests/test_flow_phases.py)."""
import json
from unittest.mock import MagicMock

from pydantic import BaseModel

from utils.pipeline_result_parser import parse_pipeline_result


class TestParsePipelineResult:
    def test_parses_plain_json(self):
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = None
        result.raw = json.dumps({"sector": "Technology", "positions": []})
        out = parse_pipeline_result(result)
        assert out["sector"] == "Technology"

    def test_json_dict_shortcut(self):
        result = MagicMock()
        result.json_dict = {"sector": "Finance"}
        out = parse_pipeline_result(result)
        assert out["sector"] == "Finance"

    def test_strips_markdown_fences(self):
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = None
        result.raw = "```json\n" + json.dumps({"sector": "Energy"}) + "\n```"
        out = parse_pipeline_result(result)
        assert out["sector"] == "Energy"

    def test_parse_error_on_bad_raw(self):
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = None
        result.raw = "not json"
        out = parse_pipeline_result(result)
        assert out.get("parse_error") is True

    def test_pydantic_shortcut_on_last_task_output(self):
        class _Out(BaseModel):
            sector: str
            count: int

        last = MagicMock()
        last.pydantic = _Out(sector="Health", count=3)
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = [last]
        out = parse_pipeline_result(result)
        assert out == {"sector": "Health", "count": 3}
