# ProspectAI - Multi-Agent Investment Analysis System

## Overview

ProspectAI is a multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow. The system supports Anthropic Claude models (default) and local Ollama models.

**🎉 First Official Release - v1.0.0**

### ⚠️ Important Disclaimer

**ProspectAI is built for educational purposes to help developers get initiated in Agentic AI development.**

**🚨 INVESTMENT WARNING: This tool should NOT be used as an investment tool without proper knowledge of the investment domain. The analysis provided is for educational demonstration of AI capabilities and should not be considered as financial advice. Always consult with qualified financial professionals before making investment decisions.**

## Features

- **🤖 Multi-Agent System**: Four specialized AI agents for different aspects of investment analysis
- **🧠 Anthropic Claude**: Powered by Claude models (Sonnet, Opus) by default
- **🦙 Ollama Support**: Run fully locally with Ollama models
- **📊 Real Reddit Integration**: Live Reddit sentiment analysis for trending stocks (top 5 per sector)
- **🏭 Sector Analysis**: Analyze 5 major sectors (Technology, Healthcare, Finance, Energy, Consumer)
- **⚡ Command-Line Interface**: Easy-to-use CLI with flexible configuration
- **🔒 Environment-Based Config**: Secure `.env`-based configuration with startup validation
- **📈 Structured Output**: Consistent, machine-readable JSON analysis results
- **🚀 CrewAI Framework**: Professional multi-agent orchestration via LiteLLM

## Architecture

The system consists of four specialized agents working in sequence:

### Agent Pipeline

```
MarketAnalystAgent → TechnicalAnalystAgent → FundamentalAnalystAgent → InvestorStrategicAgent
```

Each agent receives the full output of all prior agents as context.

### Market Analyst Agent 📊
- **Purpose**: Entry point of the investment pipeline
- **Function**: Analyzes Reddit discussions to identify trending stocks at the current moment in time, incorporating macro/geopolitical context
- **Data Sources**: Reddit API (PRAW) with Serper web search as fallback
- **Output**: Top 5 candidate stocks with sentiment scores and relevance metrics
- **Sectors**: Technology, Healthcare, Finance, Energy, Consumer

### Technical Analyst Agent 📈
- **Purpose**: Quantitative technical analysis
- **Function**: Runs 13+ technical indicators per ticker using `yfinance` + `ta` library
- **Indicators**: RSI, MACD, Bollinger Bands, ATR, SMA, EMA, VWAP, ADX, and more
- **Output**: Per-stock signals, momentum scores (1–10), risk levels, entry zones, stop-loss levels

### Fundamental Analyst Agent 🏢
- **Purpose**: Financial statement and valuation analysis
- **Function**: Fetches real P/E, margins, debt ratios, FCF, and growth rates via `yfinance`
- **Output**: Valuation grades (CHEAP/FAIR/EXPENSIVE), financial health ratings, growth outlook

### Investor Strategic Agent 🎯
- **Purpose**: Final synthesis and portfolio construction
- **Function**: Applies the composite score formula and builds portfolio allocations
- **Composite Score**: 30 pts sentiment + 40 pts momentum + 30 pts fundamentals (max 100)
- **Recommendations**: `STRONG_BUY / BUY / HOLD / REDUCE / AVOID`
- **Output**: Machine-readable JSON with allocation percentages summing to 100%

## Project Structure

```
ProspectAI/
├── agents/                          # AI agent implementations
│   ├── base_agent.py                # Abstract base class; LLM instantiation via crewai.LLM
│   ├── market_analyst_agent.py
│   ├── technical_analyst_agent.py
│   ├── fundamental_analyst_agent.py
│   └── investor_strategic_agent.py
├── config/
│   ├── agents.yaml                  # Primary place to tune agent behavior
│   ├── agent_config_loader.py       # Reads agents.yaml
│   └── config.py                    # Config class — reads env vars, no defaults
├── utils/
│   ├── reddit_sentiment_tool.py     # PRAW-based Reddit sentiment tool
│   ├── technical_analysis_tool.py   # yfinance + ta indicators
│   └── fundamental_data_tool.py     # yfinance fundamentals
├── tests/                           # Test suite
├── main.py                          # CLI entry point; .env validation
├── prospect_ai_crew.py              # CrewAI orchestration
├── requirements.txt
├── env.example                      # Template — copy to .env
└── README.md
```

## Installation

### Prerequisites
- Python 3.9+
- An Anthropic API key **or** a local Ollama installation

### 1. Clone and Set Up

```bash
git clone <your-repo-url>
cd ProspectAI
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp env.example .env
```

Then open `.env` and fill in your values. The app will fail at startup with a clear error listing any missing required keys.

### 3. Anthropic API Setup (Default Provider)

1. Get your API key from [console.anthropic.com](https://console.anthropic.com)
2. Add to `.env`:
   ```bash
   ANTHROPIC_API_KEY=your_key_here
   ANTHROPIC_MODEL=claude-sonnet-4-6
   ```

### 4. Market Data Setup (at least one required)

**Option A — Reddit API (preferred):**
1. Visit [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) and create a "script" app
2. Add to `.env`:
   ```bash
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT=ProspectAI/1.0
   ```
See [REDDIT_API_SETUP.md](REDDIT_API_SETUP.md) for detailed instructions.

**Option B — Serper web search fallback:**
1. Get your key at [serper.dev](https://serper.dev)
2. Add to `.env`:
   ```bash
   SERPER_API_KEY=your_key_here
   ```

### 5. Ollama Setup (Optional — Local Models)

1. Install Ollama: [ollama.com/download](https://ollama.com/download)
2. Start the service:
   ```bash
   ollama serve
   ```
3. Pull a model:
   ```bash
   ollama pull qwen3.5:9b
   # or: llama3.2:8b, mistral:7b, etc.
   ```
4. Add to `.env`:
   ```bash
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen3.5:9b
   ```

## Usage

### Basic Usage

```bash
# Analyze Technology sector with Anthropic Claude (default)
python main.py

# Analyze a specific sector
python main.py --sector Healthcare
python main.py --sector Finance
python main.py --sector Energy
python main.py --sector Consumer

# Override the Claude model for a single run
python main.py --model claude-opus-4-6 --sector Technology

# Use a local Ollama model
python main.py --ollama --sector Technology

# Use Ollama with a specific model or remote server
python main.py --ollama --model llama3.2:8b --sector Healthcare
python main.py --ollama --url http://192.168.1.100:11434 --sector Finance
```

### CLI Reference

| Flag | Description |
|---|---|
| `--sector` | Sector to analyze: Technology, Healthcare, Finance, Energy, Consumer (default: Technology) |
| `--model` | Override model name from `.env` |
| `--ollama` | Use local Ollama instead of Anthropic |
| `--url` | Ollama server URL (overrides `OLLAMA_BASE_URL`) |

### Testing

```bash
python tests/test_skeleton.py
python tests/test_reddit_output.py [sector]
python tests/test_technical_analyst.py
python tests/test_market_analyst_llm.py
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `ANTHROPIC_MODEL` | Yes | Claude model (e.g. `claude-sonnet-4-6`) |
| `REDDIT_CLIENT_ID` | One of A or B | Reddit API client ID |
| `REDDIT_CLIENT_SECRET` | One of A or B | Reddit API client secret |
| `REDDIT_USER_AGENT` | No | Defaults to `ProspectAI/1.0` |
| `SERPER_API_KEY` | One of A or B | Serper web search key (fallback) |
| `OLLAMA_BASE_URL` | If `--ollama` | Ollama server URL |
| `OLLAMA_MODEL` | If `--ollama` | Ollama model name |

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

### Per-Agent Model Override

Each agent can use a different model by editing `config/agents.yaml`:

```yaml
market_analyst:
  llm:
    provider: "anthropic"
    model: "claude-opus-4-6"   # Use Opus for the most context-heavy agent

technical_analyst:
  llm:
    provider: "anthropic"
    model: "claude-sonnet-4-6" # Sonnet for the rest
```

See [AGENT_LLM_CONFIGURATION.md](AGENT_LLM_CONFIGURATION.md) for full details.

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

## Troubleshooting

| Issue | Fix |
|---|---|
| `.env file not found` | Run `cp env.example .env` and fill in your keys |
| Missing keys error at startup | Check the listed keys against your `.env` |
| `ANTHROPIC_API_KEY` invalid | Verify key at [console.anthropic.com](https://console.anthropic.com) |
| Ollama connection refused | Run `ollama serve` and verify `OLLAMA_BASE_URL` |
| Ollama model not found | Run `ollama pull <model-name>` |
| Reddit 401 error | Verify `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` |
| No stocks found | Check Reddit credentials or add `SERPER_API_KEY` as fallback |

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
- [Author webpage](https://moisesprat.github.io)
