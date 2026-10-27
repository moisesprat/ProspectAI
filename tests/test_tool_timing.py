"""Tests for utils/tool_timing.py instrument_tool (STALL-01): native path, errors, privacy, idempotency."""

import logging

import pytest
from crewai.tools import BaseTool

from utils.execution_tracker import ExecutionTracker
from utils.tool_timing import instrument_tool

SECRET_ARG = "SECRET-ARG-VALUE-123"
SECRET_ERR = "https://example.test/search?key=SECRET-API-KEY"


class _OkTool(BaseTool):
    name: str = "Ok Tool"
    description: str = "Returns a fixed string. Args: query (str)."

    def _run(self, query: str = "") -> str:
        return "result-" + "x" * 20


class _BoomTool(BaseTool):
    name: str = "Boom Tool"
    description: str = "Always raises. Args: query (str)."

    def _run(self, query: str = "") -> str:
        raise ConnectionError(SECRET_ERR)


def _calls(tracker):
    return tracker.to_dict()["tool_calls"]


class TestInstrumentTool:

    def test_native_run_path_is_recorded(self):
        tracker = ExecutionTracker()
        tool = instrument_tool(_OkTool(), "technical_analysis", lambda: tracker)
        out = tool.run(query="abc")  # BaseTool.run -> self._run (native function-calling path)
        assert out == "result-" + "x" * 20
        calls = _calls(tracker)
        assert len(calls) == 1
        assert calls[0]["phase"] == "technical_analysis"
        assert calls[0]["tool"] == "Ok Tool"
        assert calls[0]["ok"] is True

    def test_output_chars_is_length_of_result(self):
        tracker = ExecutionTracker()
        tool = instrument_tool(_OkTool(), "p", lambda: tracker)
        result = tool._run("q")
        assert _calls(tracker)[0]["output_chars"] == len(str(result))

    def test_error_records_class_name_only_and_reraises(self):
        tracker = ExecutionTracker()
        tool = instrument_tool(_BoomTool(), "market_analysis", lambda: tracker)
        with pytest.raises(ConnectionError) as info:
            tool._run("q")
        assert str(info.value) == SECRET_ERR  # original exception unchanged
        rec = _calls(tracker)[0]
        assert rec["ok"] is False
        assert rec["error"] == "ConnectionError"
        assert rec["output_chars"] is None
        assert "SECRET" not in repr(tracker.to_dict())

    def test_native_run_error_does_not_leak_message(self):
        tracker = ExecutionTracker()
        tool = instrument_tool(_BoomTool(), "market_analysis", lambda: tracker)
        try:
            tool.run(query=SECRET_ARG)
        except Exception:
            pass
        assert _calls(tracker)[0]["error"] == "ConnectionError"
        assert "SECRET" not in repr(tracker.to_dict())

    def test_idempotent_wrapping_records_once(self):
        tracker = ExecutionTracker()
        tool = _OkTool()
        assert instrument_tool(tool, "p", lambda: tracker) is tool
        assert instrument_tool(tool, "p", lambda: tracker) is tool
        tool._run("q")
        assert len(_calls(tracker)) == 1

    def test_none_tracker_is_safe(self):
        tool = instrument_tool(_OkTool(), "p", lambda: None)
        assert tool._run("q").startswith("result-")

    def test_tracker_is_late_bound(self):
        holder = {"t": None}
        tool = instrument_tool(_OkTool(), "p", lambda: holder["t"])
        tool._run("before")
        holder["t"] = ExecutionTracker()
        tool._run("after")
        assert len(_calls(holder["t"])) == 1

    def test_log_lines_carry_no_arguments_or_exception_text(self, caplog):
        tracker = ExecutionTracker()
        ok = instrument_tool(_OkTool(), "technical_analysis", lambda: tracker)
        boom = instrument_tool(_BoomTool(), "technical_analysis", lambda: tracker)
        with caplog.at_level(logging.INFO, logger="utils.tool_timing"):
            ok._run(SECRET_ARG)
            with pytest.raises(ConnectionError):
                boom._run(SECRET_ARG)
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert "tool_start phase=technical_analysis tool=Ok Tool" in text
        assert "tool_end phase=technical_analysis tool=Boom Tool" in text
        assert "ok=False" in text
        assert "SECRET" not in text
        assert SECRET_ERR not in text
