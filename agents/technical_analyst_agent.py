#!/usr/bin/env python3
"""
Technical Analyst Agent - Analyzes technical indicators and generates momentum analysis
"""

from agents.base_agent import BaseAgent
from crewai import Agent

class TechnicalAnalystAgent(BaseAgent):
    """Technical Analyst Agent that analyzes stock momentum using technical indicators"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            agent_key="technical_analyst",
            config_path=config_path
        )
        
    
    def create_agent(self) -> Agent:
        """Create and return a CrewAI Agent instance"""
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=self.verbose,
            allow_delegation=self.allow_delegation,
            llm=self._get_llm(),
            max_iter=self.max_iter,
        )
    