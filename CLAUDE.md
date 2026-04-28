# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # then fill in API keys

# Run analysis (Anthropic, default)
python3 main.py --sector Technology

# Run with a specific Claude model
python3 main.py --model claude-opus-4-6 --sector Finance

# Run with Ollama local model
python3 main.py --ollama --model qwen3.5:9b --sector Finance

# Run tests
pytest tests/ -v
pytest tests/test_crew.py -v          # orchestration tests
pytest tests/test_schemas.py -v       # Pydantic schema tests
pytest tests/test_tools_reddit.py -v
pytest tests/test_tools_technical.py -v
pytest tests/test_tools_fundamental.py -v
pytest tests/test_execution_tracker.py -v

# Supported sectors
# Technology, Healthcare, Finance, Energy, Consumer, Industrials, Real Estate, Utilities
```

## Required API Keys (in `.env`)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (default provider) | LLM calls |
| `MODEL` | Yes | Global model override (e.g. `claude-sonnet-4-6`). Falls back to legacy `ANTHROPIC_MODEL` / `OLLAMA_MODEL` |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | One of these two | Market Analyst Reddit data |
| `SERPER_API_KEY` | One of these two | Web search fallback when Reddit is unavailable |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Only with `--ollama` | Local Ollama inference |

The app validates `.env` at startup and exits with a clear error listing any missing keys.

## Architecture

ProspectAI is a **CrewAI Flow multi-agent pipeline** that runs 6 phases (with two phases in parallel) to produce investment recommendations for a given market sector.

### Agent Pipeline

```
MarketAnalystAgent
        │
  ┌─────┴──────┐  (parallel)
  ▼            ▼
TechnicalAnalystAgent   FundamentalAnalystAgent
  └─────┬──────┘
        ▼
InvestorStrategicAgent (draft)
        │
        ▼
CriticAgent (adversarial review)
        │
        ▼
InvestorStrategicAgent (final revision)
```

1. **MarketAnalystAgent** — calls `RedditSentimentTool` (or `SerperDevTool` fallback), identifies top 5 stocks by mention count + sentiment score.
2. **TechnicalAnalystAgent** — calls `TechnicalAnalysisTool` (batch, all tickers at once); 13+ indicators (RSI, MACD, BB, ATR, etc.) via `yfinance` + `ta`.
3. **FundamentalAnalystAgent** — calls `FundamentalDataTool` then `FundamentalGraderTool` (both batch). Phases 2 and 3 run in parallel after Phase 1.
4. **InvestorStrategicAgent (draft)** — calls `CompositeScoreTool` then `PortfolioAllocatorTool`; decides action + allocation per ticker.
5. **CriticAgent** — adversarial review of the draft; outputs `revision_directives` and `per_ticker_critiques`.
6. **InvestorStrategicAgent (final)** — applies critic directives (or defends with data); optionally re-calls `PortfolioAllocatorTool` if actions change.

### Key Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point; validates `.env`, sets `MODEL_PROVIDER`, calls `ProspectAIFlow.run_analysis()` |
| `prospect_ai_flow.py` | **Current orchestrator** — `ProspectAIFlow(Flow[ProspectAIFlowState])`: 6-phase CrewAI Flow, state model, context slimming helpers, `_extract_pydantic()` for schema validation |
| `prospect_ai_crew.py` | Legacy single-Crew orchestrator (no longer called by main) |
| `agents/base_agent.py` | `BaseAgent` ABC; loads YAML config, `_get_llm()` returns `crewai.LLM` based on `MODEL_PROVIDER` |
| `agents/critic_agent.py` | `CriticAgent(BaseAgent)` — adversarial reviewer |
| `config/agents.yaml` | **Primary place to change agent behavior**: role, goal, backstory, temperature, model, max_tokens |
| `config/tasks.yaml` | Task descriptions and expected outputs with `$sector` / `$today` template variables |
| `config/agent_config_loader.py` | Reads `agents.yaml`, exposes per-agent config dicts |
| `config/task_config_loader.py` | `TaskConfigLoader.render(task_key, **kwargs)` — substitutes template variables |
| `config/config.py` | `Config` class: env var properties, `default_model_id()`, `model_id_for_agent(agent_key)` |
| `schemas/agent_outputs.py` | Pydantic output contracts for all 5 agent outputs |
| `utils/reddit_sentiment_tool.py` | `RedditSentimentTool` — Reddit scraper, sets `fallback_required=True` instead of raising |
| `utils/technical_analysis_tool.py` | `TechnicalAnalysisTool` — batch yfinance + ta; one call covers all tickers |
| `utils/fundamental_data_tool.py` | `FundamentalDataTool` — batch yfinance fetch (P/E, margins, FCF, growth, etc.) |
| `utils/fundamental_grader_tool.py` | `FundamentalGraderTool` — deterministic financial health grader; takes FundamentalDataTool output |
| `utils/composite_score_tool.py` | `CompositeScoreTool` — sentiment + momentum + fundamental → composite score 0-100 |
| `utils/portfolio_allocator_tool.py` | `PortfolioAllocatorTool` — allocation % and trade setups (entry zone, stop, take-profit) |
| `utils/recommendation_validator.py` | Post-pipeline validation: stop/TP invariants, R/R checks, allocation sanity |
| `utils/execution_tracker.py` | Per-phase wall-clock timing + LLM token tracking |
| `utils/yfinance_cache.py` | In-memory cache (scoped per `run_analysis()` call) to avoid duplicate yfinance calls |

### Task → Tool Mapping

| Phase | Agent | Tools | Runs after |
|---|---|---|---|
| 1 Market Analysis | MarketAnalyst | `RedditSentimentTool`, `SerperDevTool` (fallback) | — |
| 2 Technical Analysis | TechnicalAnalyst | `TechnicalAnalysisTool` | Phase 1 |
| 3 Fundamental Analysis | FundamentalAnalyst | `FundamentalDataTool` → `FundamentalGraderTool` | Phase 1 (parallel with 2) |
| 4 Draft Strategy | InvestorStrategic | `CompositeScoreTool` → `PortfolioAllocatorTool` | Phases 2 + 3 |
| 5 Critique Review | Critic | none (reasoning only) | Phase 4 |
| 6 Final Strategy | InvestorStrategic | `PortfolioAllocatorTool` (if actions change) | Phase 5 |

### Pydantic Output Schemas (`schemas/agent_outputs.py`)

Each phase validates its LLM output against a Pydantic model via `_extract_pydantic()` in `ProspectAIFlow`:

| Schema | Key fields |
|---|---|
| `MarketAnalysisOutput` | `candidate_stocks[]` — ticker, mention_count, average_sentiment [-1,1], relevance_score [0,1], rationale |
| `TechnicalAnalysisOutput` | `technical_analysis[]` — ticker, raw_indicators, momentum_analysis (momentum_score 0-10, risk_level, regime, entry_zone) |
| `FundamentalAnalysisOutput` | `fundamental_analysis[]` — ticker, valuation_metrics, fundamental_rating, key_strengths/risks |
| `InvestorStrategicOutput` | `positions[]` — ticker, action, composite_score, allocation_pct, trade_setup or scaled_entry_setups, rationale |
| `CriticOutput` | `per_ticker_critiques[]` — severity, issue_type, finding, instruction; `revision_directives[]` |

### Final `run_analysis()` Return Value

```python
{
    "status": "success",
    "workflow_completed": True,
    "result": {                     # InvestorStrategicOutput (final phase)
        "sector": str,
        "positions": [
            {
                "ticker": str,
                "action": "LONG-BUY" | "SCALED-ENTRY" | "WAIT-FOR-ENTRY" | "MONITOR" | "AVOID",
                "composite_score": float,   # 0-100; formula: 30 sentiment + 40 momentum + 30 fundamentals
                "allocation_pct": float,
                "current_price": float | None,
                "trade_setup": {"entry_zone_low", "entry_zone_high", "stop_loss", "take_profit"} | None,
                "scaled_entry_setups": [{...}, {...}] | None,   # 2 tranches for SCALED-ENTRY
                "rationale": str,
                "monitoring_triggers": [str, ...],
                "review_frequency": "DAILY" | "WEEKLY" | "MONTHLY"
            }
        ],
        "deployed_pct": float,
        "reserved_pct": float,
        "cash_reserve_pct": float,
        "overall_strategy": str,
        "risk_level": "Low" | "Medium" | "High" | "Very High"
    },
    "summary": str,
    "execution_metrics": {          # from ExecutionTracker
        "run_at": str,              # ISO 8601
        "pipeline_elapsed_sec": float,
        "phases": [{"name", "elapsed_sec", "input_tokens", "output_tokens", "cached_tokens"}],
        "totals": {"input_tokens", "output_tokens", "cached_tokens", "total_tokens"},
        "by_model": {model_id: {"input_tokens", "output_tokens", "cached_tokens", "total_tokens"}}
    },
    "validation_warnings": [{"severity", "ticker", "field", "message"}]
}
```

### LLM Configuration

- **Global**: `MODEL_PROVIDER` env var (`anthropic` or `ollama`) — set by `--ollama` CLI flag.
- **Per-agent env overrides**: `AGENT_MARKET_ANALYST_MODEL`, `AGENT_TECHNICAL_ANALYST_MODEL`, `AGENT_FUNDAMENTAL_ANALYST_MODEL`, `AGENT_INVESTOR_STRATEGIC_MODEL`, `AGENT_CRITIC_MODEL`.
- **Per-agent YAML defaults** (`config/agents.yaml` `llm:` block): Haiku for data-gathering agents (1–3), Sonnet for reasoning agents (4–6).
- All LLM calls go through `crewai.LLM` backed by LiteLLM — no direct langchain dependencies.

### Adding a New Agent

1. Add an entry to `config/agents.yaml` with `name`, `role`, `goal`, `backstory`, and an `llm:` block.
2. Add a task entry to `config/tasks.yaml` with `description` and `expected_output`.
3. Create `agents/new_agent.py` subclassing `BaseAgent`; implement `create_agent()` returning a `crewai.Agent`.
4. Add the corresponding Pydantic schema to `schemas/agent_outputs.py`.
5. Add a new `@listen` phase in `prospect_ai_flow.py`, store output in `ProspectAIFlowState`, and wire context via the `_slim_*()` helpers.
