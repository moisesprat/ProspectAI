from abc import ABC, abstractmethod
from typing import Dict, Any, List
from crewai import Agent
from config.config import Config
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM

class BaseAgent(ABC):
    """Base class for all ProspectAI agents"""
    
    def __init__(self, name: str, role: str, goal: str, backstory: str):
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.agent = None
        self.config = Config()
        
    def _get_llm(self):
        """Get the appropriate LLM based on configuration"""
        if self.config.MODEL_PROVIDER == "ollama":
            # Use the format that litellm expects for Ollama
            return OllamaLLM(
                base_url=self.config.OLLAMA_BASE_URL,
                model=f"ollama/{self.config.OLLAMA_MODEL}",  # Add ollama/ prefix
                temperature=0.1,
                format="json"
            )
        else:
            # Default to OpenAI
            return ChatOpenAI(
                model=self.config.OPENAI_MODEL,
                temperature=0.1,
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
