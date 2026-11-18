from .base_agent import BaseAgent
from crewai import Agent

class InvestorStrategicAgent(BaseAgent):
    """Agent responsible for final investment recommendations and strategy"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            agent_key="investor_strategic",
            config_path=config_path
        )
    
    def create_agent(self) -> Agent:
        """Create the Investor Strategic Agent"""
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=self.verbose,
            allow_delegation=self.allow_delegation,
            llm=self._get_llm(),
            max_iter=self.max_iter,
        )
