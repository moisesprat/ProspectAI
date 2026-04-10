from .base_agent import BaseAgent
from crewai import Agent


class CriticAgent(BaseAgent):
    """Adversarial reviewer that challenges the Draft Strategist's portfolio."""

    def __init__(self, config_path: str = None):
        super().__init__(agent_key="critic", config_path=config_path)

    def create_agent(self) -> Agent:
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=False,
            llm=self._get_llm(),
        )
