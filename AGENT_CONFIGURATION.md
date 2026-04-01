# Agent Configuration Guide

This guide explains how to use the YAML-based configuration system for ProspectAI agents.

## Overview

All agent behavior is defined in `config/agents.yaml`. You can change roles, goals, backstories, temperature, and LLM settings without touching any Python code.

## Configuration File: `config/agents.yaml`

```yaml
agents:
  market_analyst:
    name: "Market Analyst Agent"
    role: "Reddit Sentiment Analyst and Stock Screener"
    goal: "Identify the top 5 most-discussed stocks..."
    backstory: |
      You are a specialist in retail investor sentiment analysis...
    verbose: true
    allow_delegation: false
    temperature: 0.1
    max_tokens: 10000
    llm:
      provider: "anthropic"
      model: "claude-sonnet-4-6"
      api_key: null       # null = use ANTHROPIC_API_KEY env var
      base_url: null

global_settings:
  default_temperature: 0.1
  default_verbose: true
  default_allow_delegation: false
  max_iterations: 5
  memory: false
```

## Configuration Fields

### Required (per agent)
| Field | Description |
|---|---|
| `name` | Display name of the agent |
| `role` | The agent's role in the system |
| `goal` | What the agent is trying to accomplish |
| `backstory` | The agent's expertise and workflow instructions |

### Optional (per agent)
| Field | Default | Description |
|---|---|---|
| `verbose` | `true` | Print agent reasoning |
| `allow_delegation` | `false` | Whether the agent can delegate sub-tasks |
| `temperature` | `0.1` | LLM temperature (0.1 = focused, 0.7 = creative) |
| `max_tokens` | `null` | Max tokens per LLM response |
| `llm.provider` | `"anthropic"` | `"anthropic"` or `"ollama"` |
| `llm.model` | from `.env` | Model name; used when provider matches active provider |
| `llm.api_key` | `null` | Override API key (null = use env var) |
| `llm.base_url` | `null` | Override Ollama base URL |

### Global Settings
| Field | Description |
|---|---|
| `default_temperature` | Fallback temperature for agents that don't specify one |
| `max_iterations` | Maximum tool-use iterations per task |
| `memory` | Enable CrewAI agent memory |

## Adding a New Agent

**Step 1** — Add to `config/agents.yaml`:

```yaml
agents:
  news_analyst:
    name: "News Analyst Agent"
    role: "Financial News Analyst"
    goal: "Identify market-moving news for the given sector stocks"
    backstory: |
      You are a financial journalist who scans news sources for
      catalysts, earnings surprises, and regulatory developments.
    verbose: true
    allow_delegation: false
    temperature: 0.1
    max_tokens: 8000
    llm:
      provider: "anthropic"
      model: "claude-sonnet-4-6"
      api_key: null
      base_url: null
```

**Step 2** — Create `agents/news_analyst_agent.py`:

```python
from .base_agent import BaseAgent
from crewai import Agent

class NewsAnalystAgent(BaseAgent):
    def __init__(self, config_path: str = None):
        super().__init__(agent_key="news_analyst", config_path=config_path)

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

**Step 3** — Wire into `ProspectAICrew` in `prospect_ai_crew.py`:

```python
from agents.news_analyst_agent import NewsAnalystAgent

class ProspectAICrew:
    def __init__(self):
        ...
        self.news_analyst = NewsAnalystAgent()
```

Then add a `Task` for it in `create_tasks()` with appropriate `context=`.

## Modifying Existing Agents

Edit `config/agents.yaml` — no code changes needed:

```yaml
agents:
  market_analyst:
    temperature: 0.3          # More creative rationales
    max_tokens: 15000         # Longer output
    llm:
      model: "claude-opus-4-6" # Upgrade to Opus for this agent only
```

## Temperature Guidelines

| Value | Use Case |
|---|---|
| `0.1` | Analytical, data-driven tasks (recommended for all agents) |
| `0.3` | Creative analysis and narrative writing |
| `0.5` | Exploratory or brainstorming tasks |
| `0.7+` | Highly creative content |

## Troubleshooting

| Issue | Fix |
|---|---|
| `KeyError: 'agent_key'` | Check that the key in `agents.yaml` matches `agent_key` in the class |
| YAML parse error | Validate indentation — YAML is whitespace-sensitive |
| Agent using wrong model | Check `llm.provider` matches the active `MODEL_PROVIDER` |
| Missing required field | Ensure `name`, `role`, `goal`, and `backstory` are all present |

## Validation

```python
from config.agent_config_loader import AgentConfigLoader

loader = AgentConfigLoader()
if loader.validate_config():
    print("Configuration is valid")
```
