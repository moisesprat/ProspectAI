import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from crewai import Agent, LLM
from config.config import Config
from config.agent_config_loader import AgentConfigLoader

class BaseAgent(ABC):
    """Base class for all ProspectAI agents"""

    def __init__(self, agent_key: str, config_path: str = None):
        self.agent_key = agent_key
        self.config_loader = AgentConfigLoader(config_path)
        self.agent_config = self.config_loader.get_agent_config(agent_key)

        self.name = self.agent_config['name']
        self.role = self.agent_config['role']
        self.goal = self.agent_config['goal']
        self.backstory = self.agent_config['backstory']

        self.settings = self.config_loader.get_agent_settings(agent_key)
        self.verbose = self.settings.get('verbose', True)
        self.allow_delegation = self.settings.get('allow_delegation', False)
        self.temperature = self.settings.get('temperature', 0.1)
        self.max_tokens = self.settings.get('max_tokens', None)

        self.llm_config = self.settings.get('llm', {})
        self.llm_provider = self.llm_config.get('provider', 'anthropic')
        self.llm_model = self.llm_config.get('model')
        self.llm_api_key = self.llm_config.get('api_key')
        self.llm_base_url = self.llm_config.get('base_url')

        self.agent = None
        self.config = Config()

    def _get_llm(self):
        """Get the appropriate LLM. MODEL_PROVIDER env var (set by CLI) always wins."""
        provider = os.getenv("MODEL_PROVIDER", "anthropic")

        if provider == "ollama":
            return LLM(
                model=f"ollama/{self.config.OLLAMA_MODEL}",
                base_url=self.llm_base_url or self.config.OLLAMA_BASE_URL,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        # Anthropic (default)
        model = self.llm_model if self.llm_provider == "anthropic" and self.llm_model else self.config.ANTHROPIC_MODEL
        return LLM(
            model=f"anthropic/{model}",
            api_key=self.llm_api_key or self.config.ANTHROPIC_API_KEY,
            temperature=self.temperature,
            max_tokens=self.max_tokens or 10000,
        )

    @abstractmethod
    def create_agent(self) -> Agent:
        """Create and return a CrewAI Agent instance"""
        pass

    def get_agent(self) -> Agent:
        """Get the CrewAI Agent instance"""
        if not self.agent:
            self.agent = self.create_agent()
        return self.agent

    def get_config(self) -> Dict[str, Any]:
        """Get the full agent configuration"""
        return self.agent_config

    def reload_config(self):
        """Reload configuration from file"""
        self.config_loader.reload_config()
        self.agent_config = self.config_loader.get_agent_config(self.agent_key)

        self.name = self.agent_config['name']
        self.role = self.agent_config['role']
        self.goal = self.agent_config['goal']
        self.backstory = self.agent_config['backstory']

        self.settings = self.config_loader.get_agent_settings(self.agent_key)
        self.verbose = self.settings.get('verbose', True)
        self.allow_delegation = self.settings.get('allow_delegation', False)
        self.temperature = self.settings.get('temperature', 0.1)
