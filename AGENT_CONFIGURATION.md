# Agent Configuration Guide

This guide explains how to use the YAML-based configuration system for ProspectAI agents.

## Overview

The YAML configuration system allows you to:
- **Centralize** all agent parameters in one place
- **Easily modify** agent roles, goals, and backstories without code changes
- **Maintain consistency** across all agents
- **Quickly iterate** on agent personalities and behaviors

## Configuration Files

### Main Configuration: `config/agents.yaml`

This file contains all agent configurations:

```yaml
agents:
  market_analyst:
    name: "Market Analyst Agent"
    role: "Sector-focused Reddit analyst"
    goal: "Identify trending stocks from Reddit discussions for further analysis"
    backstory: |
      You are a sharp market researcher who listens to retail investors 
      and sentiment on Reddit, extracting the most discussed and promising stocks in a sector.
    verbose: true
    allow_delegation: false
    temperature: 0.1

  technical_analyst:
    name: "Technical Analyst Agent"
    role: "Technical analysis specialist"
    goal: "Provide comprehensive technical analysis and trading signals for stocks"
    backstory: |
      You are an expert technical analyst with deep knowledge of chart patterns, 
      indicators, and market dynamics.
    verbose: true
    allow_delegation: false
    temperature: 0.1

# ... more agents

global_settings:
  default_temperature: 0.1
  default_verbose: true
  default_allow_delegation: false
  max_iterations: 3
  memory: true
```

## Configuration Fields

### Required Fields (for each agent)
- **`name`**: Display name of the agent
- **`role`**: The agent's role in the system
- **`goal`**: What the agent is trying to accomplish
- **`backstory`**: The agent's personality and expertise

### Optional Fields (for each agent)
- **`verbose`**: Whether the agent should be verbose (default: true)
- **`allow_delegation`**: Whether the agent can delegate tasks (default: false)
- **`temperature`**: LLM temperature for creativity (default: 0.1)

### Global Settings
- **`default_temperature`**: Default temperature for all agents
- **`default_verbose`**: Default verbosity setting
- **`default_allow_delegation`**: Default delegation setting
- **`max_iterations`**: Maximum iterations for agent tasks
- **`memory`**: Whether to enable agent memory

## Usage Examples

### Basic Agent Creation

```python
from agents.market_analyst_agent import MarketAnalystAgent

# Create agent with default configuration
agent = MarketAnalystAgent()

# Access configuration values
print(f"Agent: {agent.name}")
print(f"Role: {agent.role}")
print(f"Goal: {agent.goal}")
print(f"Temperature: {agent.temperature}")
```

### Custom Configuration Path

```python
# Use a custom configuration file
agent = MarketAnalystAgent(config_path="path/to/custom_agents.yaml")
```

### Accessing Full Configuration

```python
# Get the complete configuration
config = agent.get_config()
print(f"Full config: {config}")

# Get specific settings
settings = agent.settings
print(f"Settings: {settings}")
```

### Reloading Configuration

```python
# Reload configuration from file (useful during development)
agent.reload_config()
```

## Configuration Management

### Adding New Agents

1. **Add to YAML file**:
```yaml
agents:
  new_agent:
    name: "New Agent"
    role: "New role description"
    goal: "New goal description"
    backstory: "New backstory description"
    verbose: true
    allow_delegation: false
    temperature: 0.1
```

2. **Create agent class**:
```python
from .base_agent import BaseAgent

class NewAgent(BaseAgent):
    def __init__(self, config_path: str = None):
        super().__init__(
            agent_key="new_agent",
            config_path=config_path
        )
    
    def create_agent(self) -> Agent:
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=self.verbose,
            allow_delegation=self.allow_delegation,
            llm=self._get_llm(),
        )
```

### Modifying Existing Agents

Simply edit the YAML file - no code changes needed:

```yaml
agents:
  market_analyst:
    # Change the role
    role: "Enhanced Reddit sentiment analyst with social media expertise"
    
    # Update the goal
    goal: "Identify trending stocks and analyze social media sentiment across multiple platforms"
    
    # Modify temperature for more creative responses
    temperature: 0.3
```

### Validation

The system automatically validates configurations:

```python
from config.agent_config_loader import AgentConfigLoader

loader = AgentConfigLoader()
if loader.validate_config():
    print("✅ Configuration is valid")
else:
    print("❌ Configuration has errors")
```

## Best Practices

### 1. **Descriptive Backstories**
Write detailed, specific backstories that give agents clear personality and expertise:

```yaml
backstory: |
  You are a senior technical analyst with 15+ years of experience in equity markets.
  You specialize in momentum analysis using RSI, MACD, and Bollinger Bands.
  You have a track record of identifying trend reversals and breakout opportunities.
  Your analysis combines quantitative data with market psychology insights.
```

### 2. **Clear Goals**
Make goals specific and actionable:

```yaml
goal: "Analyze technical indicators to identify momentum shifts and provide entry/exit recommendations with risk management guidelines"
```

### 3. **Consistent Temperature Settings**
- **0.1**: For analytical, factual tasks
- **0.3**: For creative analysis and insights
- **0.5**: For brainstorming and exploration
- **0.7+**: For highly creative content generation

### 4. **Logical Delegation**
Set `allow_delegation: true` for agents that should coordinate with others:

```yaml
investor_strategic:
  allow_delegation: true  # Can delegate to other analysts
  role: "Investment strategy coordinator"
```

## Troubleshooting

### Common Issues

1. **Configuration not found**:
   - Check file path in `AgentConfigLoader`
   - Ensure YAML syntax is correct

2. **Missing required fields**:
   - Run validation: `loader.validate_config()`
   - Check that all agents have name, role, goal, and backstory

3. **YAML syntax errors**:
   - Use a YAML validator
   - Check indentation and quotes

### Debug Mode

Enable debug output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

loader = AgentConfigLoader()
print(f"Config path: {loader.config_path}")
print(f"Available agents: {loader.get_all_agent_keys()}")
```

## Migration from Hardcoded Configuration

If you're migrating from hardcoded agent configurations:

1. **Extract** current values to YAML
2. **Update** agent classes to use `BaseAgent`
3. **Test** with the new system
4. **Remove** old hardcoded values

## Benefits

- **Maintainability**: Change agent behavior without code changes
- **Consistency**: All agents follow the same configuration pattern
- **Flexibility**: Easy to experiment with different agent personalities
- **Scalability**: Add new agents quickly with consistent structure
- **Version Control**: Track configuration changes separately from code

## Next Steps

- Customize agent configurations for your specific use case
- Experiment with different temperature and delegation settings
- Add new agents as needed
- Consider environment-specific configurations (dev, staging, prod)
