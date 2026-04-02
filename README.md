# ProspectAI - Multi-Agent Investment Analysis System

## 🚀 Try It Now

**[Try the ProspectAI Web Demo](https://prospectai-web.pages.dev)** — Experience the agentic system in action!

## Overview

ProspectAI is a multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow. The system supports Anthropic Claude models (default) and local Ollama models.

**Current release: v1.1.4**

### ⚠️ Important Disclaimer

**ProspectAI is built for educational purposes to help developers get initiated in Agentic AI development.**

**🚨 INVESTMENT WARNING: This tool should NOT be used as an investment tool without proper knowledge of the investment domain. The analysis provided is for educational demonstration of AI capabilities and should not be considered as financial advice. Always consult with qualified financial professionals before making investment decisions.**

## Features

- **Multi-Agent System**: Four specialized AI agents for different aspects of investment analysis
- **Anthropic Claude**: Powered by Claude models (Sonnet, Opus) by default
- **Ollama Support**: Run fully locally with Ollama models
- **Real Reddit Integration**: Live Reddit sentiment analysis using public JSON endpoints — no credentials required
- **Sector Analysis**: Analyze 5 major sectors (Technology, Healthcare, Finance, Energy, Consumer)
- **Command-Line Interface**: Easy-to-use CLI with flexible configuration
- **Environment-Based Config**: Secure `.env`-based configuration with startup validation
- **Structured Output**: Consistent, machine-readable JSON analysis results
- **CrewAI Framework**: Professional multi-agent orchestration via LiteLLM

## Architecture

The system consists of four specialized agents working in sequence:

```
MarketAnalystAgent → TechnicalAnalystAgent → FundamentalAnalystAgent → InvestorStrategicAgent
```

Each agent receives the full output of all prior agents as context.

### Market Analyst Agent
- **Purpose**: Entry point of the investment pipeline
- **Function**: Analyzes Reddit discussions to identify trending stocks at the current moment in time, incorporating macro/geopolitical context
- **Data Sources**: Reddit public JSON API with Serper web search as fallback
- **Output**: Top 5 candidate stocks with sentiment scores and relevance metrics

### Technical Analyst Agent
- **Purpose**: Quantitative technical analysis
- **Function**: Runs 13+ technical indicators per ticker using `yfinance` + `ta` library
- **Indicators**: RSI, MACD, Bollinger Bands, ATR, SMA, EMA, VWAP, ADX, and more
- **Output**: Per-stock signals, momentum scores (1–10), risk levels, entry zones, stop-loss levels

### Fundamental Analyst Agent
- **Purpose**: Financial statement and valuation analysis
- **Function**: Fetches real P/E, margins, debt ratios, FCF, and growth rates via `yfinance`
- **Output**: Valuation grades (CHEAP/FAIR/EXPENSIVE), financial health ratings, growth outlook

### Investor Strategic Agent
- **Purpose**: Final synthesis and portfolio construction
- **Function**: Applies the composite score formula and builds portfolio allocations
- **Composite Score**: 30 pts sentiment + 40 pts momentum + 30 pts fundamentals (max 100)
- **Recommendations**: `STRONG_BUY / BUY / HOLD / REDUCE / AVOID`
- **Output**: Machine-readable JSON with allocation percentages summing to 100%

## Installation

### Prerequisites
- Python 3.9+
- An Anthropic API key **or** a local Ollama installation

### Install via pip

```bash
pip install prospectai
```

That's it. All dependencies (CrewAI, yfinance, ta, requests, etc.) are installed automatically.

### Configure Environment

Create a `.env` file in the directory where you'll run `prospectai` (see `env.example` for the full template):

```bash
# LLM backend: anthropic | ollama
MODEL_PROVIDER=anthropic

# Global default model id for all agents (raw id, no provider prefix)
MODEL=claude-sonnet-4-6

# Required when MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here

# Optional: override MODEL for a specific agent only
# AGENT_MARKET_ANALYST_MODEL=claude-3-5-haiku-20241022
# AGENT_TECHNICAL_ANALYST_MODEL=
# AGENT_FUNDAMENTAL_ANALYST_MODEL=
# AGENT_INVESTOR_STRATEGIC_MODEL=

# Market data — Reddit and/or Serper (at least one source required by the app)
# SERPER_API_KEY=your_key_here

# When MODEL_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
```

**Model resolution (simple rule):** `AGENT_*_MODEL` (if set for that agent) → `MODEL` → legacy `ANTHROPIC_MODEL` / `OLLAMA_MODEL` if you still use older `.env` files. `MODEL_PROVIDER` selects Anthropic vs Ollama routing.

When you run the CLI, `MODEL` is also set to `provider/model_id` for CrewAI’s environment fallback; the app still resolves **raw** ids for each agent from the variables above.

#### Getting your API keys

- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)
- **Serper** (optional fallback): [serper.dev](https://serper.dev)

#### Ollama setup (optional — local models)

```bash
# Install Ollama
# https://ollama.com/download

ollama serve
ollama pull qwen3.5:9b
```

## Usage

```bash
# Analyze Technology sector (default)
prospectai

# Analyze a specific sector
prospectai --sector Healthcare
prospectai --sector Finance
prospectai --sector Energy
prospectai --sector Consumer

# Override the global MODEL for a single run
prospectai --model claude-opus-4-6 --sector Technology

# Use a local Ollama model
prospectai --ollama --sector Technology
prospectai --ollama --model llama3.2:8b --sector Healthcare
prospectai --ollama --url http://192.168.1.100:11434 --sector Finance
```

### CLI Reference

| Flag | Description |
|---|---|
| `--sector` | Sector to analyze: Technology, Healthcare, Finance, Energy, Consumer (default: Technology) |
| `--model` | Override global `MODEL` for this run (raw model id) |
| `--ollama` | Use local Ollama instead of Anthropic |
| `--url` | Ollama server URL (overrides `OLLAMA_BASE_URL`) |

## Configuration

### LLM environment variables

| Variable | Required | Description |
|---|---|---|
| `MODEL_PROVIDER` | Yes | `anthropic` or `ollama` (CLI `--ollama` sets `ollama`) |
| `MODEL` | Yes* | Global default model id for all agents (raw id, e.g. `claude-sonnet-4-6` or `qwen3.5:9b`) |
| `ANTHROPIC_API_KEY` | If `MODEL_PROVIDER=anthropic` | Anthropic API key |
| `OLLAMA_BASE_URL` | If `MODEL_PROVIDER=ollama` | Ollama server URL |
| `AGENT_MARKET_ANALYST_MODEL` | No | Overrides `MODEL` for the Market Analyst agent only |
| `AGENT_TECHNICAL_ANALYST_MODEL` | No | Overrides `MODEL` for the Technical Analyst agent only |
| `AGENT_FUNDAMENTAL_ANALYST_MODEL` | No | Overrides `MODEL` for the Fundamental Analyst agent only |
| `AGENT_INVESTOR_STRATEGIC_MODEL` | No | Overrides `MODEL` for the Investor Strategic agent only |
| `ANTHROPIC_MODEL` | No | Legacy fallback if `MODEL` is unset (Anthropic path) |
| `OLLAMA_MODEL` | No | Legacy fallback if `MODEL` is unset (Ollama path) |

\*Or set a legacy model var above instead of `MODEL`.

### Other environment variables

| Variable | Required | Description |
|---|---|---|
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | One source\* | Reddit API (preferred for sentiment) |
| `SERPER_API_KEY` | One source\* | Web search fallback when Reddit is unavailable |

\*The app requires **at least one** of: Reddit credentials **or** Serper.

### Anthropic Claude Models

| Model | Use Case |
|---|---|
| `claude-sonnet-4-6` | Best balance of quality and speed (default) |
| `claude-opus-4-6` | Highest quality, deeper reasoning |
| `claude-haiku-4-5-20251001` | Fastest, lowest cost |

### Ollama Models

| Model | Notes |
|---|---|
| `qwen3.5:9b` | Good reasoning, recommended for analysis |
| `llama3.2:8b` | General purpose |
| `llama3.2:3b` | Lightweight, fast |
| `mistral:7b` | Good for analytical tasks |

### Per-agent model overrides

**Preferred:** set optional `AGENT_*_MODEL` variables in `.env` or your host secrets (e.g. Modal). Each variable overrides the global `MODEL` for that agent only.

**Fallback:** you can still set `llm.model` per agent in `config/agents.yaml` if no env-based id is resolved for that agent.

See [AGENT_LLM_CONFIGURATION.md](AGENT_LLM_CONFIGURATION.md) for additional notes on agent LLM configuration.

## Development

To contribute or run from source:

```bash
git clone https://github.com/moisesprat/ProspectAI.git
cd ProspectAI
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
```

After installing in editable mode the `prospectai` command is available and picks up any local changes immediately.

### Project Structure

```
ProspectAI/
├── agents/                          # AI agent implementations
│   ├── base_agent.py
│   ├── market_analyst_agent.py
│   ├── technical_analyst_agent.py
│   ├── fundamental_analyst_agent.py
│   └── investor_strategic_agent.py
├── config/
│   ├── agents.yaml                  # Agent behavior (role, goal, model, temperature)
│   ├── tasks.yaml                   # Task definitions (descriptions, output schemas)
│   ├── agent_config_loader.py
│   ├── task_config_loader.py
│   └── config.py
├── utils/
│   ├── reddit_sentiment_tool.py     # Reddit public JSON sentiment tool
│   ├── technical_analysis_tool.py
│   └── fundamental_data_tool.py
├── tests/
├── main.py                          # CLI entry point (prospectai command)
├── prospect_ai_crew.py              # CrewAI orchestration
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
python tests/test_skeleton.py
python tests/test_reddit_output.py Technology
python tests/test_technical_analyst.py
python tests/test_market_analyst_llm.py
```

### Building and Publishing

```bash
pip install build twine
python -m build
twine upload dist/*
```

## Troubleshooting

| Issue | Fix |
|---|---|
| `prospectai: command not found` | Run `pip install prospectai` or activate the venv where it's installed |
| `.env file not found` | Create a `.env` file in your current working directory |
| Missing keys error at startup | Check the listed keys against your `.env` (especially `MODEL` / `MODEL_PROVIDER` and market data keys) |
| `ANTHROPIC_API_KEY` invalid | Verify key at [console.anthropic.com](https://console.anthropic.com) |
| Ollama connection refused | Run `ollama serve` and verify `OLLAMA_BASE_URL` |
| Ollama model not found | Run `ollama pull <model-name>` |
| No stocks found from Reddit | Reddit public API may be rate-limited; add `SERPER_API_KEY` as fallback |

## Roadmap

### v1.1 - Enhanced Market Analysis
- Integration with financial news APIs (Bloomberg, Reuters)
- Real-time market sentiment from multiple sources
- Enhanced sector rotation analysis

### v1.2 - Agent Improvements
- Enhanced financial modeling capabilities
- More sophisticated valuation algorithms
- Advanced portfolio optimization

### v1.3 - Advanced Risk Management
- Monte Carlo simulations for portfolio scenarios
- Advanced risk metrics (VaR, CVaR, Sharpe ratios)
- Dynamic risk adjustment based on market conditions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests where applicable
4. Submit a pull request

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built on the [CrewAI](https://github.com/joaomdmoura/crewAI) framework
- LLM routing via [LiteLLM](https://github.com/BerriAI/litellm)
- Inspired by modern multi-agent AI systems
- [Author webpage](https://moisesprat.dev
