"""STALL-01 per-tool timing: phase attribution under concurrent real crews, and TaskFactory wiring."""

import asyncio
import time
from typing import Any, List, Optional

import pytest
from crewai import Agent, Crew, Task
from crewai.llms.base_llm import BaseLLM
from crewai.tools import BaseTool

from utils.execution_tracker import ExecutionTracker
from utils.tool_timing import instrument_tool


class EchoTool(BaseTool):
    name: str = "Echo Tool"
    description: str = "Echoes its input after a short delay. Args: text (str)."

    def _run(self, text: str = "") -> str:
        time.sleep(0.2)
        return "ok:" + str(text)


class ScriptLLM(BaseLLM):
    """Offline stub LLM: one ReAct tool turn, then a Final Answer."""

    def __init__(self) -> None:
        super().__init__(model="stub-model")
        self.turns = 0

    def _next(self) -> str:
        self.turns += 1
        if self.turns == 1:
            return (
                "Thought: I should call the tool.\n"
                "Action: Echo Tool\n"
                'Action Input: {"text": "hello"}'
            )
        return "Thought: I now know the final answer\nFinal Answer: done"

    def call(self, messages: Any, *args: Any, **kwargs: Any) -> str:
        return self._next()

    async def acall(self, messages: Any, *args: Any, **kwargs: Any) -> str:
        return self._next()

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 8192


async def _run_crew(tool: Any) -> Any:
    agent = Agent(
        role="Tester",
        goal="Call the tool once",
        backstory="Offline test agent",
        llm=ScriptLLM(),
        tools=[tool],
        allow_delegation=False,
        max_iter=3,
    )
    task = Task(description="Use the tool", expected_output="done", agent=agent, tools=[tool])
    crew = Crew(agents=[agent], tasks=[task], cache=False, verbose=False)
    return await crew.akickoff()


class TestConcurrentPhaseAttribution:
    def test_calls_attributed_to_own_phase_under_concurrency(self):
        tracker = ExecutionTracker()
        tracker.start()
        technical = instrument_tool(EchoTool(), "technical_analysis", lambda: tracker)
        fundamental = instrument_tool(EchoTool(), "fundamental_analysis", lambda: tracker)

        async def both():
            return await asyncio.gather(_run_crew(technical), _run_crew(fundamental))

        asyncio.run(both())
        tracker.finish()

        calls = tracker.to_dict()["tool_calls"]
        assert sorted(c["phase"] for c in calls) == ["fundamental_analysis", "technical_analysis"]
        for c in calls:
            assert c["tool"] == "Echo Tool"
            assert c["ok"] is True
            assert c["error"] is None
            assert c["elapsed_sec"] > 0
            assert c["output_chars"] == len("ok:hello")
        assert all(c["phase"] is not None for c in calls)

    def test_tool_result_passes_through_wrapper_unchanged(self):
        tool = instrument_tool(EchoTool(), "market_analysis", lambda: None)
        assert tool._run("x") == "ok:x"


class TestTaskFactoryWiring:
    def test_every_phase_tool_marked_with_its_phase_and_idempotent(self, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
        monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
        from prospect_ai_crew import TaskFactory

        tracker = ExecutionTracker()
        factory = TaskFactory(tracker_getter=lambda: tracker)
        seen = 0
        for phase, cfg in factory._phase_config.items():
            for tool in [*cfg["agent_tools"], *cfg["flow_tools"].values()]:
                seen += 1
                assert tool._prospectai_timed_phase == phase
                assert instrument_tool(tool, phase, lambda: tracker) is tool
        assert seen == 7
        assert factory.search_tool in factory._phase_config["market_analysis"]["agent_tools"]

    def test_wrapping_twice_records_one_call_per_invocation(self):
        tracker = ExecutionTracker()
        tool = EchoTool()
        instrument_tool(tool, "draft_strategy", lambda: tracker)
        instrument_tool(tool, "draft_strategy", lambda: tracker)
        tool._run("a")
        assert len(tracker.to_dict()["tool_calls"]) == 1

    def test_zero_arg_factory_records_nothing_and_still_builds(self, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
        monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
        from prospect_ai_crew import TaskFactory

        factory = TaskFactory()
        tool = factory._phase_config["technical_analysis"]["agent_tools"][0]
        assert tool._prospectai_timed_phase == "technical_analysis"
