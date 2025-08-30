from abc import ABC, abstractmethod
from typing import Dict, Any, List
from crewai import Agent
from config.config import Config
from config.agent_config_loader import AgentConfigLoader
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM

class BaseAgent(ABC):
    """Base class for all ProspectAI agents"""
    
    def __init__(self, agent_key: str, config_path: str = None):
        """
        Initialize the base agent with configuration from YAML
        
        Args:
            agent_key: The key identifier for the agent (e.g., 'market_analyst')
            config_path: Optional path to custom config file
        """
        self.agent_key = agent_key
        self.config_loader = AgentConfigLoader(config_path)
        self.agent_config = self.config_loader.get_agent_config(agent_key)
        
        # Extract configuration values
        self.name = self.agent_config['name']
        self.role = self.agent_config['role']
        self.goal = self.agent_config['goal']
        self.backstory = self.agent_config['backstory']
        
        # Get additional settings
        self.settings = self.config_loader.get_agent_settings(agent_key)
        self.verbose = self.settings.get('verbose', True)
        self.allow_delegation = self.settings.get('allow_delegation', False)
        self.temperature = self.settings.get('temperature', 0.1)
        
        self.agent = None
        self.config = Config()
        
    def _get_llm(self):
        """Get the appropriate LLM based on configuration"""
        if self.config.MODEL_PROVIDER == "ollama":
            # Use the format that litellm expects for Ollama
            return OllamaLLM(
                base_url=self.config.OLLAMA_BASE_URL,
                model=f"ollama/{self.config.OLLAMA_MODEL}",  # Add ollama/ prefix
                temperature=self.temperature,
                format="json"
            )
        else:
            # Default to OpenAI
            return ChatOpenAI(
                model=self.config.OPENAI_MODEL,
                temperature=self.temperature,
                api_key=self.config.OPENAI_API_KEY
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
        
        # Update instance variables
        self.name = self.agent_config['name']
        self.role = self.agent_config['role']
        self.goal = self.agent_config['goal']
        self.backstory = self.agent_config['backstory']
        
        self.settings = self.config_loader.get_agent_settings(self.agent_key)
        self.verbose = self.settings.get('verbose', True)
        self.allow_delegation = self.settings.get('allow_delegation', False)
        self.temperature = self.settings.get('temperature', 0.1)
