# Agent-Specific LLM Configuration

This document explains how to configure different LLMs for each agent in ProspectAI.

## Overview

Each agent can now have its own LLM configuration specified in the `config/agents.yaml` file. This allows you to:
- Use different models for different agents
- Mix OpenAI and Ollama models
- Set agent-specific API keys and base URLs
- Override global environment settings per agent

## Configuration Format

Each agent can include an `llm` section in their configuration:

```yaml
agent_name:
  # ... other agent settings ...
  llm:
    provider: "openai"  # or "ollama"
    model: "gpt-4"      # model name
    api_key: null       # null = use env variable
    base_url: null      # for ollama, null = use env variable
```

## Configuration Options

### Provider Options
- `"openai"` - Use OpenAI models
- `"ollama"` - Use Ollama models

### Model Examples
- **OpenAI**: `"gpt-4"`, `"gpt-3.5-turbo"`, `"gpt-4-turbo"`
- **Ollama**: `"llama3.2:3b"`, `"llama3.2:7b"`, `"mistral:7b"`

### API Key and Base URL
- Set to `null` to use environment variables
- Set to specific values to override environment variables

## Example Configurations

### Mixed Provider Setup
```yaml
agents:
  market_analyst:
    # ... other settings ...
    llm:
      provider: "openai"
      model: "gpt-4"
      api_key: null
      base_url: null

  technical_analyst:
    # ... other settings ...
    llm:
      provider: "openai"
      model: "gpt-3.5-turbo"  # Cheaper model for technical analysis
      api_key: null
      base_url: null

  investor_strategic:
    # ... other settings ...
    llm:
      provider: "ollama"  # Local model for final recommendations
      model: "llama3.2:7b"
      api_key: null
      base_url: "http://localhost:11434"
```

### Custom API Keys
```yaml
agents:
  market_analyst:
    # ... other settings ...
    llm:
      provider: "openai"
      model: "gpt-4"
      api_key: "sk-your-custom-key"  # Override env variable
      base_url: null
```

### Fallback Behavior
If an agent doesn't specify LLM configuration, it will fall back to:
1. Global environment variables (`MODEL_PROVIDER`, `OPENAI_MODEL`, etc.)
2. Default values from the Config class

## Environment Variables (Fallback)
```bash
# Global fallback settings
MODEL_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

## Benefits

1. **Cost Optimization**: Use cheaper models for simpler tasks
2. **Performance Tuning**: Use faster models for real-time analysis
3. **Privacy**: Use local Ollama models for sensitive data
4. **Flexibility**: Mix different providers based on agent needs
5. **Testing**: Easily switch models for testing different configurations

## Usage

The configuration is automatically loaded when creating agents. No code changes needed - just update the YAML file and restart your application.

```python
from agents.market_analyst_agent import MarketAnalystAgent

# Agent will automatically use its configured LLM
agent = MarketAnalystAgent()
llm = agent._get_llm()  # Returns the configured LLM instance
```
