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
from schemas.agent_outputs import (
    MarketAnalysisOutput,
    TechnicalAnalysisOutput,
    FundamentalAnalysisOutput,
    InvestorStrategicOutput,
    CriticOutput,
)


class TaskFactory:
    """Agent and task factory used by ProspectAIFlow."""

    def __init__(self):
        self.config = Config()

        # Agents (created once, reused across build_task calls)
        self.market_analyst = MarketAnalystAgent()
        self.technical_analyst = TechnicalAnalystAgent()
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.investor_strategist = InvestorStrategicAgent()
        self.critic = CriticAgent()

        self.search_tool = PatientSerperDevTool()

        # Phase config built once; tools are shared instances
        self._phase_config = {
            "market_analysis": {
                "agent":  self.market_analyst.get_agent(),
                "tools":  [RedditSentimentTool(), self.search_tool],
                "schema": MarketAnalysisOutput,
            },
            "technical_analysis": {
                "agent":  self.technical_analyst.get_agent(),
                "tools":  [TechnicalAnalysisTool()],
                "schema": TechnicalAnalysisOutput,
            },
            "fundamental_analysis": {
                "agent":  self.fundamental_analyst.get_agent(),
                "tools":  [FundamentalDataTool(), FundamentalGraderTool()],
                "schema": FundamentalAnalysisOutput,
            },
            "draft_strategy": {
                "agent":  self.investor_strategist.get_agent(),
                "tools":  [CompositeScoreTool(), PortfolioAllocatorTool()],
                "schema": InvestorStrategicOutput,
            },
            "critique_review": {
                "agent":  self.critic.get_agent(),
                "tools":  [],
                "schema": CriticOutput,
            },
            "final_strategy": {
                "agent":  self.investor_strategist.get_agent(),
                "tools":  [],
                "schema": InvestorStrategicOutput,
            },
        }

    def build_task(self, phase: str, sector: str, today: str, prior_context: str = "", risk_profile: str = "conservative") -> Task:
        """Build a single Task for `phase`. prior_context is appended to the description."""
        if phase not in self._phase_config:
            raise ValueError(f"Unknown pipeline phase: {phase!r}")
        pc = self._phase_config[phase]
        cfg = TaskConfigLoader().render(phase, sector=sector, today=today, risk_profile=risk_profile)
        description = cfg["description"]
        if prior_context:
            description = description + "\n\n" + prior_context
        return Task(
            description=description,
            agent=pc["agent"],
            tools=pc["tools"],
            expected_output=cfg["expected_output"],
            output_pydantic=pc["schema"],
        )
