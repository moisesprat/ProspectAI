# ProspectAI - Multi-Agent Investment Analysis System

## 🚀 Try It Now

**[Try the ProspectAI Web Demo](https://prospect-ai.moisesprat.dev)** — Experience the agentic system in action!

## Overview

ProspectAI is a multi-agent investment analysis system built on the CrewAI framework. It leverages five specialized AI agents running a six-task pipeline to produce investment recommendations through a systematic analysis workflow. The system supports Anthropic Claude models (default) and local Ollama models.

**Current release: v1.13.3**

### ⚠️ Important Disclaimer

**ProspectAI is built for educational purposes to help developers get initiated in Agentic AI development.**

**🚨 INVESTMENT WARNING: This tool should NOT be used as an investment tool without proper knowledge of the investment domain. The analysis provided is for educational demonstration of AI capabilities and should not be considered as financial advice. Always consult with qualified financial professionals before making investment decisions.**

## Features

- **Multi-Agent System**: Five specialized AI agents across a six-task pipeline for rigorous investment analysis
- **Anthropic Claude**: Powered by Claude models (Haiku 5.5 for the market, technical and fundamental steps, Sonnet 5.5 for the draft, critic and final steps; other Sonnet and Opus models supported)
- **Ollama Support**: Run fully locally with Ollama models
- **Serper Web Search Discovery**: Candidate stocks come from three fixed Serper web searches per run
- **News Sentiment**: Each picked stock gets the Marketaux news sentiment score for the last 7 days (optional `NEWS_SENTIMENT_API_KEY`; null when absent or when too few articles exist)
- **Sector Analysis**: Analyze 5 major sectors (Technology, Healthcare, Finance, Energy, Consumer)
- **Command-Line Interface**: Easy-to-use CLI with flexible configuration
- **Environment-Based Config**: Secure `.env`-based configuration with startup validation
- **Structured Output**: Consistent, machine-readable JSON analysis results
- **CrewAI Framework**: Professional multi-agent orchestration via LiteLLM

## Architecture

The system runs five specialized agents across a six-task sequential pipeline. Each task receives the full output of all prior tasks as context.

```
MarketAnalyst → TechnicalAnalyst → FundamentalAnalyst → DraftStrategist → Critic → FinalStrategist
    Task 1           Task 2             Task 3              Task 4         Task 5      Task 6
```

### Pipeline Tasks & Agents

| Task | Agent | Tools | Input context |
|---|---|---|---|
| 1. Market Analysis | MarketAnalyst | `PatientSerperDevTool` | — |
| 2. Technical Analysis | TechnicalAnalyst | `TechnicalAnalysisTool`, `TechnicalInterpretationTool` | Task 1 |
| 3. Fundamental Analysis | FundamentalAnalyst | `FundamentalDataTool`, `FundamentalGraderTool` | Tasks 1–2 |
| 4. Draft Strategy | InvestorStrategic | — (the pipeline runs `CompositeScoreTool` and `PortfolioAllocatorTool` itself) | Tasks 1–3 |
| 5. Critic Review | Critic | — (synthesis only) | Tasks 1–4 |
| 6. Final Strategy | InvestorStrategic | — (the pipeline runs `CompositeScoreTool` and `PortfolioAllocatorTool` itself) | Tasks 1–5 |

### Agent Descriptions

#### Market Analyst Agent (Task 1)
- **Purpose**: Entry point — identifies candidate stocks from live market signals
- **Function**: The Flow searches the web and the model picks trending stocks from the results, incorporating macro/geopolitical context at execution time
- **Data Sources**: Serper web search (three fixed queries)
- **Sentiment**: After the model chooses its picks, the pipeline looks up each pick's news sentiment from Marketaux (recent articles about the company, cached per symbol per UTC day). The model never writes a score. A stock with no articles in the window, or no lookup, has a null sentiment and the run continues
- **Output**: Top 5 candidate stocks with sentiment scores (null when unavailable) and relevance metrics

#### Technical Analyst Agent (Task 2)
- **Purpose**: Quantitative technical analysis
- **Function**: Runs 13+ technical indicators per ticker using `yfinance` + `ta` library, then interprets signals using `TechnicalInterpretationTool`
- **Indicators**: RSI, MACD, Bollinger Bands, ATR, SMA, EMA, VWAP, ADX, and more
- **Output**: Per-stock signals, momentum scores (1–10), market regime (TRENDING/REVERTING), entry zones, stop-loss levels

#### Fundamental Analyst Agent (Task 3)
- **Purpose**: Financial statement and valuation analysis
- **Function**: Fetches real P/E, margins, debt ratios, FCF, and growth rates via `yfinance`; grades each metric using `FundamentalGraderTool`
- **Output**: Valuation grades (CHEAP/FAIR/EXPENSIVE), financial health ratings, growth outlook

#### Investor Strategic Agent — Draft (Task 4)
- **Purpose**: First-pass portfolio construction
- **Function**: The pipeline computes composite scores and allocations; the model picks one action per stock from `LONG-BUY`, `WAIT-FOR-ENTRY`, `MONITOR` and `AVOID`
- **Composite Score**: 30 pts sentiment + 40 pts momentum + 30 pts fundamentals (max 100)
- **Position cap**: 15% per position for the conservative profile, 30% for the aggressive profile
- **Trade setups**: exist for `LONG-BUY` and `WAIT-FOR-ENTRY`

#### Critic Agent (Task 5)
- **Purpose**: Adversarial quality gate between the draft and final strategy
- **Function**: Reviews the draft portfolio against 12 failure-mode checks (schema validity, allocation math, entry zone logic, R/R ratios, regime consistency, etc.) and emits structured directives for correction
- **Output**: `CriticOutput` — list of `CritiqueItem` objects with `field`, `severity`, and `directive`; `approved` flag if no issues

#### Investor Strategic Agent — Final (Task 6)
- **Purpose**: Revised, production-ready portfolio
- **Function**: Incorporates all Critic directives and produces the definitive `InvestorStrategicOutput` — identical schema to the draft but corrected
- **Output**: Machine-readable JSON (`pipeline_version: "2.0"`) with allocation percentages summing to 100%, post-generation validation warnings attached

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

# Optional on Anthropic: a global model id for all agents (raw id, no provider prefix).
# Unset, each agent uses its model from config/agents.yaml (claude-haiku-5-5 for market,
# technical and fundamental; claude-sonnet-5-5 for investor_strategic and critic).
# MODEL=claude-sonnet-4-6

# Required when MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here

# Optional: override MODEL for a specific agent only
# AGENT_MARKET_ANALYST_MODEL=claude-sonnet-4-6
# AGENT_TECHNICAL_ANALYST_MODEL=
# AGENT_FUNDAMENTAL_ANALYST_MODEL=
# AGENT_INVESTOR_STRATEGIC_MODEL=

# Market data — Serper web search (required)
SERPER_API_KEY=your_key_here

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
| `MODEL` | Ollama only | Optional on Anthropic (each agent defaults to its `config/agents.yaml` model: `claude-haiku-5-5` for market, technical and fundamental, `claude-sonnet-5-5` for investor_strategic and critic); a global override for all agents when set. Required with `--ollama` (e.g. `qwen3.5:9b`) |
| `ANTHROPIC_API_KEY` | If `MODEL_PROVIDER=anthropic` | Anthropic API key |
| `OLLAMA_BASE_URL` | If `MODEL_PROVIDER=ollama` | Ollama server URL |
| `AGENT_MARKET_ANALYST_MODEL` | No | Overrides `MODEL` for the Market Analyst agent only |
| `AGENT_TECHNICAL_ANALYST_MODEL` | No | Overrides `MODEL` for the Technical Analyst agent only |
| `AGENT_FUNDAMENTAL_ANALYST_MODEL` | No | Overrides `MODEL` for the Fundamental Analyst agent only |
| `AGENT_INVESTOR_STRATEGIC_MODEL` | No | Overrides `MODEL` for the Investor Strategic agent only |
| `ANTHROPIC_MODEL` | No | Legacy fallback if `MODEL` is unset (Anthropic path) |
| `OLLAMA_MODEL` | No | Legacy fallback if `MODEL` is unset (Ollama path) |

\*For Ollama, set `MODEL` or the legacy `OLLAMA_MODEL`.

### Other environment variables

| Variable | Required | Description |
|---|---|---|
| `SERPER_API_KEY` | Yes | Serper web search, the only discovery source for the market phase |
| `NEWS_SENTIMENT_API_KEY` | Optional | Per-stock news sentiment (Marketaux); without it sentiment is null. The free tier allows 100 requests a day shared by everyone using the key: when a day's quota runs out, the report shows null sentiment and `execution_metrics.sentiment_lookup.stopped_reason` says why. A stock needs at least one article from the last 7 days to get a score |

### Anthropic Claude Models

| Model | Use Case |
|---|---|
| `claude-haiku-5-5` | Default for the market, technical and fundamental steps (set in `config/agents.yaml`) |
| `claude-sonnet-5-5` | Default for the draft, critic and final steps (set in `config/agents.yaml`) |
| `claude-sonnet-4-6` | Higher quality, slower and costlier |
| `claude-opus-4-6` | Highest quality, deeper reasoning |

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
├── agents/                              # AI agent implementations
│   ├── base_agent.py
│   ├── market_analyst_agent.py
│   ├── technical_analyst_agent.py
│   ├── fundamental_analyst_agent.py
│   ├── investor_strategic_agent.py
│   └── critic_agent.py                 # Adversarial reviewer (v1.5.0+)
├── config/
│   ├── agents.yaml                     # Agent behavior (role, goal, model, thinking)
│   ├── tasks.yaml                      # Task definitions (descriptions, output schemas)
│   ├── agent_config_loader.py
│   ├── task_config_loader.py
│   └── config.py
├── schemas/
│   └── agent_outputs.py                # Pydantic output schemas for all 5 agents
├── utils/
│   ├── technical_analysis_tool.py      # 13+ indicator calculator
│   ├── technical_interpretation_tool.py
│   ├── fundamental_data_tool.py        # yfinance financial data fetcher
│   ├── fundamental_grader_tool.py      # Grades individual fundamental metrics
│   ├── composite_score_tool.py         # 30/40/30 composite scoring
│   ├── portfolio_allocator_tool.py     # Allocation math with a per-profile cap
│   └── recommendation_validator.py    # Post-generation validation
├── scripts/
│   └── deploy.sh                       # Bump version, build, publish to PyPI, deploy Modal
├── tests/
├── main.py                             # CLI entry point (prospectai command)
├── prospect_ai_crew.py                 # CrewAI orchestration (6-task pipeline)
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
python tests/test_skeleton.py
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
| No stocks found from search | Check `SERPER_API_KEY` and the Serper quota |
| Sentiment is always empty (null, `sentiment_available` false) | Check that `NEWS_SENTIMENT_API_KEY` is set and valid, then read `execution_metrics.sentiment_lookup`: `status` `no_key` means no key, `stopped_reason` `quota` or `rate_limited` means the provider's daily free-tier quota ran out (it resets daily; results already looked up that UTC day are cached), `access_denied` means the key was refused, and `scores` below the number of picks means those stocks had no article in the last 7 days |
| A stock mentioned in the search is missing from the report | Read `execution_metrics.sector_check`: `dropped` lists stocks outside the sector with their listed sector and industry, and `skipped` lists stocks kept because their sector could not be read |
| The market step's text says its stocks come from a curated list | No stock found in the web search could be confirmed in the sector after the retries. Read `execution_metrics.market_fallback` (`tickers` are the curated stocks used, `dropped` counts why the chosen stocks were set aside) and `execution_metrics.market_corpus.queries` for what was searched |

## Release Notes

### Unreleased — Analyses run in the hours after the market closes
- An analysis started after the market closes, before Yahoo Finance records that day's closing price, no longer stops with "no valid current price" for every stock.
- In that window each stock's price and indicators come from the most recent trading day that has a closing price, usually the day before. No price is filled in or estimated.

### v1.13.3 — Better stock searches, and a safe list when the search finds none
- The web searches for each sector now use plain sector terms and name a few of the sector's best-known stocks, so an analysis such as Financials finds bank and financial stocks to choose from instead of general market news.
- When none of the stocks chosen from the web search can be confirmed as part of the sector you picked, the analysis now continues with five well-known stocks of that sector instead of stopping with an error, and the market step's text says the stocks came from this list.
- Those five stocks show no mention count, relevance or news sentiment, because they were not found in the web search, and the run record notes that the list was used and why.

### v1.13.2 — Stock picks stay in the chosen sector
- A stock found in the web search is now kept only when its listed sector or industry belongs to the sector you chose, so a web-search mention of a company such as Apple or Nvidia no longer puts it in a Financials analysis.
- The new check never sets aside a sector's well-known stocks, and it keeps a stock whose listed sector cannot be read, so a slow or failed lookup never stops the analysis.
- The run record now lists the stocks the check set aside for being outside the sector, with their listed sector and industry.

### v1.13.1 — Clearer handling of missing prices, funds and share-class tickers
- A buy or wait-for-entry pick whose price cannot be read is now shown as monitor with "price unavailable" and a dash for the price, and the analysis still finishes.
- A buy can no longer be published without its entry, stop and target.
- Sector funds such as XLF and XLY are no longer picked as stocks for Financials and Consumer Discretionary.
- Share-class tickers such as BRK.B now get their price and company data.
- The search text the model reads now has a fixed size limit.

### v1.13.0 — News sentiment for each picked stock
- Each stock the analysis picks now gets a news sentiment score from Marketaux, based on recent articles about the company, and the report shows it next to the stock.
- A stock with too few recent articles, or a day when the news source is unavailable or out of free requests, shows no score instead of an invented one, and the analysis still finishes.
- Stock picks come from web search alone, and the old forum source that had stopped returning data is gone, so runs no longer wait on it.

### v1.12.3 — Analyses that run at the same time stay separate
- When several analyses run at the same moment, each now keeps its own price and company data, so one analysis starting can no longer discard data another is still using.
- Within a single analysis nothing changes: each stock's data is still fetched once and reused across the steps.

## Roadmap

### Next — Multi-sector analysis
- Support analyzing up to 3 sectors in a single pipeline run
- Stocks from all sectors compete on composite score for portfolio slots
- Cross-sector portfolio diversification rules

### Future
- Integration with financial news APIs (Bloomberg, Reuters)
- Monte Carlo simulations for portfolio scenarios
- Advanced risk metrics (VaR, CVaR, Sharpe ratios)
- PDF report generation with charts

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
