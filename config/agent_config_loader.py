"""
Agent Configuration Loader
Loads agent configurations from YAML files and provides easy access to agent parameters
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

class AgentConfigLoader:
    """Loads and manages agent configurations from YAML files"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config loader
        
        Args:
            config_path: Path to the YAML configuration file. 
                        Defaults to 'config/agents.yaml' relative to project root
        """
        if config_path is None:
            # Get the project root directory (assuming this file is in config/)
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "agents.yaml"
        
        self.config_path = Path(config_path)
        self.config_data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load the YAML configuration file"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            if not config or 'agents' not in config:
                raise ValueError("Invalid configuration file: missing 'agents' section")
            
            return config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading configuration: {e}")
    
    def get_agent_config(self, agent_key: str) -> Dict[str, Any]:
        """
        Get configuration for a specific agent
        
        Args:
            agent_key: The key of the agent (e.g., 'market_analyst', 'technical_analyst')
            
        Returns:
            Dictionary containing the agent's configuration
            
        Raises:
            KeyError: If the agent key doesn't exist
        """
        if 'agents' not in self.config_data:
            raise KeyError("No agents section found in configuration")
        
        if agent_key not in self.config_data['agents']:
            available_agents = list(self.config_data['agents'].keys())
            raise KeyError(f"Agent '{agent_key}' not found. Available agents: {available_agents}")
        
        return self.config_data['agents'][agent_key]
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global agent settings"""
        return self.config_data.get('global_settings', {})
    
    def get_all_agent_keys(self) -> list:
        """Get list of all available agent keys"""
        return list(self.config_data.get('agents', {}).keys())
    
    def get_agent_name(self, agent_key: str) -> str:
        """Get the display name of an agent"""
        config = self.get_agent_config(agent_key)
        return config.get('name', agent_key)
    
    def get_agent_role(self, agent_key: str) -> str:
        """Get the role of an agent"""
        config = self.get_agent_config(agent_key)
        return config.get('role', '')
    
    def get_agent_goal(self, agent_key: str) -> str:
        """Get the goal of an agent"""
        config = self.get_agent_config(agent_key)
        return config.get('goal', '')
    
    def get_agent_backstory(self, agent_key: str) -> str:
        """Get the backstory of an agent"""
        config = self.get_agent_config(agent_key)
        return config.get('backstory', '')
    
    def get_agent_settings(self, agent_key: str) -> Dict[str, Any]:
        """Get additional settings for an agent (verbose, allow_delegation, etc.)"""
        config = self.get_agent_config(agent_key)
        # Return only the settings, not the core identity fields
        core_fields = {'name', 'role', 'goal', 'backstory'}
        return {k: v for k, v in config.items() if k not in core_fields}
    
    def reload_config(self):
        """Reload the configuration from file (useful for development)"""
        self.config_data = self._load_config()
    
    def validate_config(self) -> bool:
        """Validate that the configuration has all required fields"""
        try:
            required_sections = ['agents']
            required_agent_fields = ['name', 'role', 'goal', 'backstory']
            
            # Check required sections
            for section in required_sections:
                if section not in self.config_data:
                    print(f"❌ Missing required section: {section}")
                    return False
            
            # Check each agent has required fields
            for agent_key, agent_config in self.config_data['agents'].items():
                for field in required_agent_fields:
                    if field not in agent_config:
                        print(f"❌ Agent '{agent_key}' missing required field: {field}")
                        return False
            
            print("✅ Configuration validation passed")
            return True
            
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
            return False

# Convenience function for quick access
def get_agent_config(agent_key: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick function to get agent configuration
    
    Args:
        agent_key: The key of the agent
        config_path: Optional path to config file
        
    Returns:
        Agent configuration dictionary
    """
    loader = AgentConfigLoader(config_path)
    return loader.get_agent_config(agent_key)
