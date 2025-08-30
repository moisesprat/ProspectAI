from typing import Dict, Any, List
from .base_agent import BaseAgent
from crewai import Agent

class FundamentalAnalystAgent(BaseAgent):
    """Agent responsible for fundamental analysis of selected stocks"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            agent_key="fundamental_analyst",
            config_path=config_path
        )
    
    def create_agent(self) -> Agent:
        """Create the Fundamental Analyst Agent"""
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=False,
            llm=self._get_llm()
        )
    