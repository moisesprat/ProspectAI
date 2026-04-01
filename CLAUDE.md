# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # then fill in API keys

# Run analysis (Anthropic, default)
python main.py --sector Technology

# Run with a specific Claude model
python main.py --model claude-opus-4-6 --sector Finance

# Run with Ollama local model
python main.py --ollama --model qwen3.5:9b --sector Finance

# Run tests
python tests/test_skeleton.py
python tests/test_reddit_output.py [sector]      # sector optional, defaults to Technology
python tests/test_technical_analyst.py
python tests/test_market_analyst_llm.py

# Supported sectors
# Technology, Healthcare, Finance, Energy, Consumer
```

## Required API Keys (in `.env`)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | LLM calls (default provider) |
| `ANTHROPIC_MODEL` | Yes | Claude model name (e.g. `claude-sonnet-4-6`) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | One of these two | Market Analyst Reddit data |
| `SERPER_API_KEY` | One of these two | Web search fallback when Reddit is unavailable |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Only with `--ollama` | Local Ollama inference |

The app validates `.env` at startup and exits with a clear error listing any missing keys.

## Architecture

ProspectAI is a **CrewAI multi-agent pipeline** that sequentially runs 4 specialized agents to produce investment recommendations for a given market sector.

### Agent Pipeline (sequential, each receives prior output as context)

```
MarketAnalystAgent → TechnicalAnalystAgent → FundamentalAnalystAgent → InvestorStrategicAgent
```

1. **MarketAnalystAgent** — scrapes Reddit sentiment via PRAW, identifies top 5 stocks by mention count and sentiment score. Reflects current market conditions and macro/geopolitical context at execution time.
2. **TechnicalAnalystAgent** — runs 13+ technical indicators (RSI, MACD, BB, ATR, etc.) using `yfinance` + `ta` library via `TechnicalAnalysisTool`
3. **FundamentalAnalystAgent** — analyzes financial statements, valuation metrics, competitive positioning
4. **InvestorStrategicAgent** — synthesizes all prior analysis into portfolio allocation recommendations

### Key Files

- `main.py` — CLI entry point; validates `.env`, sets `MODEL_PROVIDER`, calls `ProspectAICrew.run_analysis()`
- `prospect_ai_crew.py` — `ProspectAICrew` class: instantiates agents, creates `Task` objects with `context=` chaining, assembles and kicks off the `Crew`. `_parse_result()` extracts structured JSON from final task output.
- `agents/base_agent.py` — `BaseAgent` ABC; loads config from YAML, exposes `_get_llm()` which returns a `crewai.LLM` instance (Anthropic or Ollama) based on `MODEL_PROVIDER` env var
- `config/agents.yaml` — **primary place to change agent behavior** (role, goal, backstory, temperature, model, max_tokens). Goals and backstories encode the pipeline data contract.
- `config/agent_config_loader.py` — reads `agents.yaml` and exposes per-agent config dicts
- `config/config.py` — `Config` class exposing env vars as properties; no hardcoded defaults
- `utils/reddit_sentiment_tool.py` — `RedditSentimentTool`: PRAW-based, returns top-5 stocks per sector by Reddit mention count + sentiment. Sets `fallback_required=True` when credentials are missing.
- `utils/technical_analysis_tool.py` — `TechnicalAnalysisTool`: yfinance + ta library, calculates 13+ indicators.
- `utils/fundamental_data_tool.py` — `FundamentalDataTool`: yfinance-based, returns real P/E, margins, debt ratios, FCF, growth rates per ticker.

### Task → Tool mapping

| Task | Agent | Tools | Context from |
|---|---|---|---|
| 1 Market Analysis | MarketAnalyst | `RedditSentimentTool`, `SerperDevTool` (fallback) | — |
| 2 Technical Analysis | TechnicalAnalyst | `TechnicalAnalysisTool` | Task 1 |
| 3 Fundamental Analysis | FundamentalAnalyst | `FundamentalDataTool` | Tasks 1 + 2 |
| 4 Investment Strategy | InvestorStrategic | none (synthesis only) | Tasks 1 + 2 + 3 |

### Final Pipeline Output Schema (Task 4)

Structured JSON with `pipeline_version: "2.0"` containing `stock_recommendations` (ticker, recommendation, composite_score, allocation_pct, entry_zone, stop_loss, key_risks, key_catalysts) and `portfolio_summary`. Composite score formula: 30 pts sentiment + 40 pts momentum + 30 pts fundamentals. Recommendations: `STRONG_BUY / BUY / HOLD / REDUCE / AVOID`.

### Adding a New Agent

1. Add an entry to `config/agents.yaml` with the required fields: `name`, `role`, `goal`, `backstory`
2. Create `agents/new_agent.py` subclassing `BaseAgent`, implement `create_agent()` returning a `crewai.Agent`
3. Instantiate it in `ProspectAICrew.__init__()` and wire it into `create_tasks()` with appropriate `context=`

### LLM Configuration

- **Global**: `MODEL_PROVIDER` env var (`anthropic` or `ollama`) controls the provider for all agents. Set by the CLI flag.
- **Per-agent**: each agent in `agents.yaml` has an `llm:` block (`provider`, `model`, `api_key`, `base_url`). The `model` field is respected when it matches the active provider.
- All LLM calls go through `crewai.LLM` backed by LiteLLM — no direct langchain dependencies.
- All 4 agents default to `anthropic / claude-sonnet-4-6`.
