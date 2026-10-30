from abc import ABC, abstractmethod
from typing import Dict, Any, List
from crewai import Agent, LLM
from agents.caching_llm import make_caching_llm, THINKING_MODES
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
        self.thinking = self._read_thinking()
        self.max_tokens = self.settings.get('max_tokens', None)
        global_settings = self.config_loader.get_global_settings()
        self.max_iter = self.settings.get(
            'max_iter', global_settings.get('max_iterations', 15)
        )

        self.llm_config = self.settings.get('llm', {})
        self.llm_provider = self.llm_config.get('provider', 'anthropic')
        self.llm_model = self.llm_config.get('model')
        self.llm_api_key = self.llm_config.get('api_key')
        self.llm_base_url = self.llm_config.get('base_url')

        self.agent = None
        self.config = Config()

    def _read_thinking(self) -> str:
        """Per-agent thinking mode from agents.yaml (D-03): 'off' (default) or 'low'."""
        value = self.settings.get('thinking', 'off')
        if value not in THINKING_MODES:
            raise ValueError(
                f"agents.yaml: {self.agent_key}.thinking must be one of "
                f"{', '.join(THINKING_MODES)}; got {value!r}"
            )
        return value

    def use_config(self, config: Config) -> None:
        """Inject the pipeline Config (model/provider/base URL). Must precede get_agent()."""
        if self.agent is not None:
            raise RuntimeError("use_config must be called before get_agent()")
        self.config = config

    def _get_llm(self):
        """Resolve LLM from config provider + AGENT_*_MODEL/MODEL (yaml llm.model is fallback)."""
        provider = self.config.provider

        resolved = self.config.model_id_for_agent(self.agent_key)
        model = resolved or self.llm_model
        if provider == "ollama":
            return LLM(
                model=f"ollama/{model}",
                base_url=self.llm_base_url or self.config.OLLAMA_BASE_URL,
                max_tokens=self.max_tokens,
            )

        api_key = self.llm_api_key if self.llm_api_key else self.config.ANTHROPIC_API_KEY
        return make_caching_llm(
            model=f"anthropic/{model}",
            api_key=api_key,
            max_tokens=self.max_tokens or 10000,
            thinking=self.thinking,
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
        self.thinking = self._read_thinking()
