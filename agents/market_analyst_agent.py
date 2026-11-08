from .base_agent import BaseAgent
from crewai import Agent

class MarketAnalystAgent(BaseAgent):
    """Agent responsible for picking trending stocks from the web search results the Flow collects"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            agent_key="market_analyst",
            config_path=config_path
        )
        
    def create_agent(self) -> Agent:
        """Create the Market Analyst Agent (no tools; the Flow supplies the search results)"""
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=self.verbose,
            allow_delegation=self.allow_delegation,
            llm=self._get_llm(),
            max_iter=self.max_iter,
        )

