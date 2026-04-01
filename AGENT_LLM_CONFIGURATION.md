# Agent-Specific LLM Configuration

This document explains how to configure LLMs for each agent in ProspectAI.

## Overview

ProspectAI supports two LLM providers:

| Provider | How to activate | Requires |
|---|---|---|
| **Anthropic** (default) | Run normally / `--anthropic` flag | `ANTHROPIC_API_KEY` in `.env` |
| **Ollama** (local) | `--ollama` flag | Running Ollama service + `OLLAMA_MODEL` in `.env` |

All LLM calls go through `crewai.LLM`, which is backed by LiteLLM. No direct langchain dependencies.

## Global Provider Selection

The active provider is set by the CLI flag, which writes `MODEL_PROVIDER` to the environment:

```bash
python main.py                        # Anthropic (default)
python main.py --model claude-opus-4-6 # Anthropic with model override
python main.py --ollama               # Ollama (uses OLLAMA_MODEL from .env)
python main.py --ollama --model llama3.2:8b  # Ollama with model override
```

## Per-Agent Model Configuration (`config/agents.yaml`)

Each agent has an `llm:` block. The `model` field is used when the active provider matches `provider`:

```yaml
agents:
  market_analyst:
    llm:
      provider: "anthropic"
      model: "claude-opus-4-6"   # Used when running with Anthropic
      api_key: null              # null = read from ANTHROPIC_API_KEY env var
      base_url: null

  technical_analyst:
    llm:
      provider: "anthropic"
      model: "claude-sonnet-4-6"
      api_key: null
      base_url: null
```

When `--ollama` is passed, all agents use `OLLAMA_MODEL` from `.env` regardless of the yaml `model` field (since Ollama model names differ from Anthropic ones).

## Provider Precedence

```
CLI flag (MODEL_PROVIDER env var)  ←  always wins
  └── per-agent yaml model name    ←  used only when provider matches
        └── .env ANTHROPIC_MODEL / OLLAMA_MODEL  ←  fallback
```

## Anthropic Model Options

| Model ID | Notes |
|---|---|
| `claude-sonnet-4-6` | Default — best balance of quality and speed |
| `claude-opus-4-6` | Highest quality, best for complex reasoning |
| `claude-haiku-4-5-20251001` | Fastest and cheapest |

Example — use Opus only for the most reasoning-heavy agent:

```yaml
agents:
  investor_strategic:
    llm:
      provider: "anthropic"
      model: "claude-opus-4-6"   # Final synthesis agent gets the best model

  market_analyst:
    llm:
      provider: "anthropic"
      model: "claude-sonnet-4-6" # Cheaper model for data extraction tasks

  technical_analyst:
    llm:
      provider: "anthropic"
      model: "claude-sonnet-4-6"

  fundamental_analyst:
    llm:
      provider: "anthropic"
      model: "claude-sonnet-4-6"
```

## Ollama Model Options

| Model | Notes |
|---|---|
| `qwen3.5:9b` | Good reasoning, recommended |
| `llama3.2:8b` | General purpose |
| `llama3.2:3b` | Lightweight, faster |
| `mistral:7b` | Good for analytical tasks |

Pull a model before use:
```bash
ollama pull qwen3.5:9b
```

## Environment Variables Reference

| Variable | Provider | Required | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic | Yes | API key |
| `ANTHROPIC_MODEL` | Anthropic | Yes | Default model for all agents |
| `OLLAMA_BASE_URL` | Ollama | With `--ollama` | Server URL (e.g. `http://localhost:11434`) |
| `OLLAMA_MODEL` | Ollama | With `--ollama` | Model name (e.g. `qwen3.5:9b`) |

## How `_get_llm()` Works

`BaseAgent._get_llm()` in `agents/base_agent.py`:

1. Reads `MODEL_PROVIDER` from the environment (set by CLI flag, default `anthropic`)
2. If `ollama`: builds `crewai.LLM(model="ollama/<OLLAMA_MODEL>", base_url=...)`
3. If `anthropic`: uses the yaml `model` field if the yaml `provider` also says `anthropic`, otherwise falls back to `ANTHROPIC_MODEL` from `.env`

```python
provider = os.getenv("MODEL_PROVIDER", "anthropic")

if provider == "ollama":
    return LLM(model=f"ollama/{self.config.OLLAMA_MODEL}", ...)

# Anthropic
model = self.llm_model if self.llm_provider == "anthropic" and self.llm_model \
        else self.config.ANTHROPIC_MODEL
return LLM(model=f"anthropic/{model}", ...)
```
