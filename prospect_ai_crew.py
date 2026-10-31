from typing import Any, Callable, Optional

from crewai import Task

from agents.market_analyst_agent import MarketAnalystAgent
from agents.technical_analyst_agent import TechnicalAnalystAgent
from agents.fundamental_analyst_agent import FundamentalAnalystAgent
from agents.investor_strategic_agent import InvestorStrategicAgent
from agents.critic_agent import CriticAgent
from config.config import Config
from config.task_config_loader import TaskConfigLoader

from utils.reddit_sentiment_tool import RedditSentimentTool
from utils.technical_analysis_tool import TechnicalAnalysisTool
from utils.fundamental_data_tool import FundamentalDataTool
from utils.fundamental_grader_tool import FundamentalGraderTool
from utils.composite_score_tool import CompositeScoreTool
from utils.portfolio_allocator_tool import PortfolioAllocatorTool
from utils.patient_serper_tool import PatientSerperDevTool
from utils.tool_timing import instrument_tool
from schemas.agent_outputs import (
    MarketNarrativeOutput,
    TechnicalNarrativeOutput,
    FundamentalNarrativeOutput,
    StrategyNarrativeOutput,
    CriticOutput,
)

# phase -> the model the LLM is asked to produce. The single source for each Task's
# output_pydantic, for the $allowed_values in its prompt, and for the output_example
# contract test (tests/test_task_output_specs.py): the schema is the source of truth
# (D-10). For market_analysis, technical_analysis and fundamental_analysis that is the
# narrative model; the Flow merges it into MarketAnalysisOutput / TechnicalAnalysisOutput /
# FundamentalAnalysisOutput. For draft_strategy and final_strategy it is StrategyNarrativeOutput;
# the Flow clamps the action and allocates after the LLM and assembles the published
# InvestorStrategicOutput (the draft also scores before it, the final reuses those scores).
# critique_review is the one phase whose model is also the published shape (CriticOutput carries
# no number that reaches the report).
PHASE_OUTPUT_MODELS = {
    "market_analysis":      MarketNarrativeOutput,
    "technical_analysis":   TechnicalNarrativeOutput,
    "fundamental_analysis": FundamentalNarrativeOutput,
    "draft_strategy":       StrategyNarrativeOutput,
    "critique_review":      CriticOutput,
    "final_strategy":       StrategyNarrativeOutput,
}


class TaskFactory:
    """Agent and task factory used by ProspectAIFlow."""

    def __init__(
        self,
        config: Optional[Config] = None,
        tracker_getter: Optional[Callable[[], Any]] = None,
    ):
        self.config = config if config is not None else Config()
        # Late-bound: the ExecutionTracker is created in run_analysis(), after the factory.
        self._tracker_getter = tracker_getter or (lambda: None)

        # Agents (created once, reused across build_task calls)
        self.market_analyst = MarketAnalystAgent()
        self.technical_analyst = TechnicalAnalystAgent()
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.investor_strategist = InvestorStrategicAgent()
        self.critic = CriticAgent()
        # Inject the shared Config before any get_agent() builds an LLM (DEPL-03).
        for agent in (
            self.market_analyst, self.technical_analyst, self.fundamental_analyst,
            self.investor_strategist, self.critic,
        ):
            agent.use_config(self.config)

        # crewai's own retry re-runs the whole task blind and its counter lives on the
        # Agent, so draft and final (one shared agent) would share a budget. Retries are
        # counted per phase by utils/phase_runner.run_phase instead (STALL-04).
        for agent in (
            self.market_analyst, self.technical_analyst, self.fundamental_analyst,
            self.investor_strategist, self.critic,
        ):
            agent.get_agent().max_retry_limit = 0

        # Same instance is shared with the phase config below (now instrumented).
        self.search_tool = instrument_tool(PatientSerperDevTool(), "market_analysis", self._tracker_getter)

        # Phase config built once; tools are shared instances.
        #   agent_tools: handed to the crewai Task, so the LLM calls them.
        #   flow_tools:  name -> instrumented instance the Flow calls itself through
        #                utils.flow_tools.call_tool (CORR-10). The LLM never sees them.
        # What the LLM answers is PHASE_OUTPUT_MODELS[phase], not stored here.
        self._phase_config = {
            "market_analysis": {
                "agent":       self.market_analyst.get_agent(),
                "agent_tools": [],
                "flow_tools":  self._timed_by_name("market_analysis", [RedditSentimentTool(), self.search_tool]),
            },
            "technical_analysis": {
                "agent":       self.technical_analyst.get_agent(),
                "agent_tools": [],
                "flow_tools":  self._timed_by_name("technical_analysis", [TechnicalAnalysisTool()]),
            },
            "fundamental_analysis": {
                "agent":       self.fundamental_analyst.get_agent(),
                "agent_tools": [],
                "flow_tools":  self._timed_by_name(
                    "fundamental_analysis", [FundamentalDataTool(), FundamentalGraderTool()],
                ),
            },
            "draft_strategy": {
                "agent":       self.investor_strategist.get_agent(),
                "agent_tools": [],
                "flow_tools":  self._timed_by_name(
                    "draft_strategy", [CompositeScoreTool(), PortfolioAllocatorTool()],
                ),
            },
            "critique_review": {
                "agent":       self.critic.get_agent(),
                "agent_tools": [],
                "flow_tools":  {},
            },
            "final_strategy": {
                "agent":       self.investor_strategist.get_agent(),
                "agent_tools": [],
                "flow_tools":  self._timed_by_name("final_strategy", [PortfolioAllocatorTool()]),
            },
        }

    def _timed(self, phase: str, tools: list) -> list:
        """Instrument every tool in `phase` once (idempotent) with its phase label."""
        return [instrument_tool(t, phase, self._tracker_getter) for t in tools]

    def _timed_by_name(self, phase: str, tools: list) -> dict:
        """Like _timed, keyed by tool name (the tools the Flow calls itself)."""
        return {t.name: t for t in self._timed(phase, tools)}

    def flow_tool(self, phase: str, name: str):
        """The instrumented tool instance the Flow calls in `phase` (KeyError if unknown)."""
        return self._phase_config[phase]["flow_tools"][name]

    def build_task(
        self,
        phase: str,
        sector: str,
        today: str,
        prior_context: str = "",
        risk_profile: str = "conservative",
        feedback: str = "",
    ) -> Task:
        """Build a single Task for `phase`.

        prior_context is appended to the description, then feedback (the failing
        fields of a previous attempt, see utils/phase_runner.py) when non-empty.
        """
        if phase not in self._phase_config:
            raise ValueError(f"Unknown pipeline phase: {phase!r}")
        pc = self._phase_config[phase]
        output_model = PHASE_OUTPUT_MODELS[phase]
        cfg = TaskConfigLoader().render(
            phase, output_model=output_model, sector=sector, today=today, risk_profile=risk_profile,
        )
        description = cfg["description"]
        if prior_context:
            description = description + "\n\n" + prior_context
        if feedback:
            description = description + "\n\n" + feedback
        return Task(
            description=description,
            agent=pc["agent"],
            tools=pc["agent_tools"],
            expected_output=cfg["expected_output"],
            output_pydantic=output_model,
        )
