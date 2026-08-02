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
pytest tests/test_flow_phases.py -v      # per-phase unit tests (mocked LLM)

# Supported sectors (driven by RedditSentimentTool.SECTOR_TICKERS)
# Technology, Semiconductors, Healthcare, Finance, Energy, Consumer, Industrials, Real Estate, Utilities
```

## Slash Commands (`.claude/commands/`)

Custom Claude Code commands available in this project:

| Command | Purpose |
|---|---|
| `/deploy <version>` | Full release pipeline — bumps version in `pyproject.toml` and `serve.py`, builds wheel, uploads to PyPI, deploys Modal backend |
| `/test [file] [-k pattern]` | Runs pytest suite; accepts an optional target file or `-k` filter |
| `/prospectai-analytics` | Fetches live usage stats from Modal (`/api/analytics`): runs by sector, risk profile, and action-type breakdown |
| `/prospectai-longbuy-analysis` | Fetches all LONG-BUY entries from the Modal Dict, computes ROI vs live yfinance prices, and saves a colour-coded Excel workbook to the repo root |

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
        │  (deterministic: CandidateUniverseFilter drops ETF/benchmark tickers)
  ┌─────┴──────┐  (parallel)
  ▼            ▼
TechnicalAnalystAgent   FundamentalAnalystAgent
  └─────┬──────┘
        ▼
InvestorStrategicAgent (draft)
        │
        ▼
CriticAgent (adversarial review)
        │  (deterministic: ActionPolicyGate drops out-of-policy directives)
        ▼
InvestorStrategicAgent (final revision — actions/rationale only)
        │  (deterministic: PortfolioAllocatorTool re-invocation + PortfolioBoundsValidator)
        ▼
   validated result
```

As of `reasoning-depth-action-selection`, **the only LLM-owned decision in the whole pipeline is which of the 4 valid actions (`LONG-BUY`/`WAIT-FOR-ENTRY`/`MONITOR`/`AVOID`) to assign to each ticker, and the rationale for it.** Every number that reaches the final output — composite score inputs, allocation %, entry zone, stop-loss, take-profit, bounds compliance — is computed by deterministic code and is never trusted from LLM output, even when the LLM echoes a number back. See "LLM vs. deterministic responsibility per phase" below for the full breakdown.

1. **MarketAnalystAgent** — calls `RedditSentimentTool` (or `PatientSerperDevTool` fallback); LLM extracts up to 5 tickers and writes sentiment rationale. Deterministic: `CandidateUniverseFilter` (`utils/candidate_universe_filter.py`) strips sector-benchmark/broad-market ETFs from the LLM's candidate list after this phase, uniformly for both the Reddit and Serper paths.
2. **TechnicalAnalystAgent** — calls `TechnicalAnalysisTool` (batch, all tickers at once); 13+ indicators (RSI, MACD, BB, ATR, etc.) via `yfinance` + `ta`. `TechnicalInterpretationTool` deterministically computes `momentum_score`, `entry_zone_low/high`, `entry_zone_status`, and `risk_level` from the raw indicators — the LLM only writes `overall_signal`/`key_signals` as its reading of those numbers, and copies the rest verbatim.
3. **FundamentalAnalystAgent** — calls `FundamentalDataTool` then `FundamentalGraderTool` (both batch, deterministic grading). Phases 2 and 3 run in parallel after Phase 1. The LLM only writes `risk_factors`/`catalysts`/`fundamental_summary`; all grades (`valuation_grade`, `financial_health`, `growth_outlook`) are copied verbatim from the tool.
4. **InvestorStrategicAgent (draft)** — calls `CompositeScoreTool` (deterministic weighted blend) then reasons over the resulting signals to decide **one action per ticker**, weighing technical/fundamental/sentiment signals holistically with no fixed decision table — only two facts are hard invariants (`entry_zone_status=CURRENT_ENTRY` excludes `WAIT-FOR-ENTRY`; `price_data_error` caps at `MONITOR`/`AVOID`). It then calls `PortfolioAllocatorTool` with its decided actions to get allocation %/trade-setup numbers — the LLM never computes those itself, only copies them into the draft.
5. **CriticAgent** — adversarial review of the draft's *reasoning*, not its numbers (allocation caps, stop%, R/R, bucket sums are explicitly out of scope — `PortfolioBoundsValidator` and `ActionPolicyGate` cover those deterministically downstream, and the Critic has no authority to fix a numeric field anyway). Outputs `revision_directives` and `per_ticker_critiques` (both may legitimately be empty on a clean draft). `ActionPolicyGate` (`utils/action_policy_gate.py`) deterministically drops any directive/critique that orders an action outside the `entry_zone_status × risk_profile` policy table before it reaches Phase 6 — this table only excludes `WAIT-FOR-ENTRY` at `CURRENT_ENTRY`/`BELOW_ZONE`; `LONG-BUY` is permitted at every `entry_zone_status`, including `BELOW_ZONE`.
6. **InvestorStrategicAgent (final)** — weighs the Critic's directives as a second analyst's counter-argument (every CRITICAL/MAJOR item must be explicitly adopted or rebutted with cited evidence) and decides the final action/rationale per ticker. Calls no tools. `ProspectAIFlow` — not the LLM — always re-invokes `PortfolioAllocatorTool` afterward (reading entry zones from the deterministic Phase-2 technical output, never from the LLM's own trade_setup) and overwrites every numeric allocation/trade-setup field, then validates the result with `PortfolioBoundsValidator` (fail-closed: one repair re-invocation, then raises `BoundsViolationError` rather than publishing a non-compliant result).

### LLM vs. deterministic responsibility per phase

| Phase | LLM decides | Code decides (never trusted from LLM output) |
|---|---|---|
| 1 Market Analysis | Which tickers to surface; sentiment tone/rationale when no measured score exists | `CandidateUniverseFilter` — drops ETF/benchmark tickers regardless of what the LLM picked |
| 2 Technical Analysis | `overall_signal`/`key_signals` (reasoned reading of the raw indicators) | `TechnicalInterpretationTool` — `momentum_score`, `entry_zone_low/high`, `entry_zone_status`, `risk_level`, all raw indicator values (`ta`/`yfinance`) |
| 3 Fundamental Analysis | `risk_factors`/`catalysts`/summary prose | `FundamentalGraderTool` — `valuation_grade`, `financial_health`, `growth_outlook`; all raw fundamentals (`yfinance`) |
| 4 Draft Strategy | **The action** per ticker (open reasoning, no table, 2 hard invariants only) and its rationale | `CompositeScoreTool` — composite score; `PortfolioAllocatorTool` — allocation %, entry zone, stop-loss, take-profit for the LLM's chosen action |
| 5 Critique Review | Whether the draft's *reasoning* holds up (findings may legitimately be zero) | `ActionPolicyGate` — strips any directive/critique requesting an action outside the policy table before Phase 6 ever sees it |
| 6 Final Strategy | The final action per ticker (weighing Critic input) and its rationale | `PortfolioAllocatorTool` (Flow re-invocation, ignores whatever the LLM wrote for these fields) + `PortfolioBoundsValidator` (fail-closed gate on the published result) |

The guardrail against the LLM inventing a 5th action is enforced independently of all of the above reasoning freedom: `PositionRecommendation.action` is a closed `Literal["LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"]` in `schemas/agent_outputs.py`, and `ActionPolicyGate`'s directive parser only recognizes those same 4 tokens — an invented action fails schema validation outright rather than being silently accepted or misparsed.

### Key Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point; validates `.env`, sets `MODEL_PROVIDER`, calls `ProspectAIFlow.run_analysis()` |
| `prospect_ai_flow.py` | **Current orchestrator** — `ProspectAIFlow(Flow[ProspectAIFlowState])`: 6-phase CrewAI Flow, state model, context slimming helpers, `_extract_pydantic()` for schema validation |
| `prospect_ai_crew.py` | `TaskFactory` — agent/task factory used by `ProspectAIFlow` (per-phase agent + tools + schema config, `build_task()`) |
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
| `utils/portfolio_allocator_tool.py` | `PortfolioAllocatorTool` — allocation % and trade setups (entry zone, stop, take-profit); also emits `reserved_allocations[]` (explicit per-ticker attribution of `reserved_pct`) |
| `utils/portfolio_bounds_validator.py` | `PortfolioBoundsValidator` / `BoundsViolationError` — Flow-level, fail-closed check of the final output against per-profile allocation/stop/R-R/bucket-sum/entry-zone invariants before publication |
| `utils/action_policy_gate.py` | `ActionPolicyGate` — deterministic `entry_zone_status × risk_profile → allowed actions` table; filters Critic `revision_directives` before they reach the Final Strategist |
| `utils/candidate_universe_filter.py` | Excludes sector-benchmark ETFs (e.g. XLE) and broad-market ETFs (SPY, QQQ, ...) from `MarketAnalysisOutput.candidate_stocks`, applied uniformly to the Reddit and Serper-fallback paths |
| `utils/patient_serper_tool.py` | `PatientSerperDevTool` — wraps `crewai_tools.SerperDevTool` with retry classification: 4xx fails fast (response body logged), only 429/5xx retry (max 2, backoff) |
| `utils/recommendation_validator.py` | Post-pipeline validation: stop/TP invariants, R/R checks, allocation sanity |
| `utils/execution_tracker.py` | Per-phase wall-clock timing + LLM token tracking |
| `utils/yfinance_cache.py` | In-memory cache (scoped per `run_analysis()` call) to avoid duplicate yfinance calls |
| `utils/scoring_constants.py` | Shared scoring weight tables used by `FundamentalGraderTool` and `CompositeScoreTool`; single source of truth for grade-to-point mappings |
| `utils/technical_interpretation_tool.py` | Deterministic numeric layer for `TechnicalAnalysisTool`: computes `momentum_score` (0-10), `entry_zone`, and `risk_level` from raw indicator values; never produces BUY/SELL signals (that is the LLM's job) |

### Task → Tool Mapping

| Phase | Agent | Tools | Runs after |
|---|---|---|---|
| 1 Market Analysis | MarketAnalyst | `RedditSentimentTool`, `PatientSerperDevTool` (fallback) | — |
| 2 Technical Analysis | TechnicalAnalyst | `TechnicalAnalysisTool` | Phase 1 |
| 3 Fundamental Analysis | FundamentalAnalyst | `FundamentalDataTool` → `FundamentalGraderTool` | Phase 1 (parallel with 2) |
| 4 Draft Strategy | InvestorStrategic | `CompositeScoreTool` → `PortfolioAllocatorTool` | Phases 2 + 3 |
| 5 Critique Review | Critic | none (reasoning only); `ActionPolicyGate` filters output before Phase 6 | Phase 4 |
| 6 Final Strategy | InvestorStrategic | none — LLM decides actions/rationale only; the Flow deterministically re-invokes `PortfolioAllocatorTool` and validates with `PortfolioBoundsValidator` afterward | Phase 5 |

### Pydantic Output Schemas (`schemas/agent_outputs.py`)

Each phase validates its LLM output against a Pydantic model via `_extract_pydantic()` in `ProspectAIFlow`:

| Schema | Key fields |
|---|---|
| `MarketAnalysisOutput` | `sentiment_available` (bool), `candidate_stocks[]` — ticker, mention_count, average_sentiment [-1,1] or `null` when `sentiment_available=false` (never a fabricated `0.0`), relevance_score [0,1], rationale |
| `TechnicalAnalysisOutput` | `technical_analysis[]` — ticker, raw_indicators, momentum_analysis (momentum_score 0-10, risk_level, regime, entry_zone) |
| `FundamentalAnalysisOutput` | `fundamental_analysis[]` — ticker, valuation_metrics, fundamental_rating, key_strengths/risks |
| `InvestorStrategicOutput` | `positions[]` — ticker, action (`Literal["LONG-BUY","WAIT-FOR-ENTRY","MONITOR","AVOID"]`), composite_score, allocation_pct, trade_setup, rationale |
| `CriticOutput` | `per_ticker_critiques[]` — severity, issue_type, finding, instruction (`default_factory=list`, may be empty); `revision_directives[]` (same) |

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
                "action": "LONG-BUY" | "WAIT-FOR-ENTRY" | "MONITOR" | "AVOID",
                "composite_score": float,   # 0-100; formula: 30 sentiment + 40 momentum + 30 fundamentals
                "allocation_pct": float,
                "current_price": float | None,
                "trade_setup": {"entry_zone_low", "entry_zone_high", "stop_loss", "take_profit"} | None,
                "rationale": str,
                "monitoring_triggers": [str, ...],
                "review_frequency": "DAILY" | "WEEKLY" | "MONTHLY"
            }
        ],
        "deployed_pct": float,
        "reserved_pct": float,
        "reserved_allocations": [{"ticker": str, "pct": float}],  # explicit per-ticker attribution of reserved_pct
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

**BREAKING (v1.9.1)**: `run_analysis()` can raise `utils.portfolio_bounds_validator.BoundsViolationError`
instead of returning the dict above, when the Flow's own `PortfolioAllocatorTool` re-invocation
still fails `PortfolioBoundsValidator` after one repair attempt. Callers (`main.py`, and the
`prospectai-backend` service once it's updated to depend on this version) should catch this
alongside other run failures rather than assume `run_analysis()` always returns a result.

### LLM Configuration

- **Global**: `MODEL_PROVIDER` env var (`anthropic` or `ollama`) — set by `--ollama` CLI flag.
- **Per-agent env overrides**: `AGENT_MARKET_ANALYST_MODEL`, `AGENT_TECHNICAL_ANALYST_MODEL`, `AGENT_FUNDAMENTAL_ANALYST_MODEL`, `AGENT_INVESTOR_STRATEGIC_MODEL`, `AGENT_CRITIC_MODEL`.
- **Per-agent YAML defaults** (`config/agents.yaml` `llm:` block): Haiku for data-gathering agents (1–3), Sonnet for reasoning agents (4–6).
- All LLM calls go through `crewai.LLM` (see `agents/base_agent.py::_get_llm()` and `agents/caching_llm.py`) — no direct langchain dependencies. `crewai.LLM(...)` is a factory: for providers in crewai's `SUPPORTED_NATIVE_PROVIDERS` list (includes both `anthropic` and `ollama`), it dispatches to a native completion class (e.g. `AnthropicCompletion`) instead of LiteLLM. Since `litellm` is not a pinned dependency here (only `crewai`/`crewai-tools` are) and isn't installed in `.venv`, **both the default Anthropic path and the `--ollama` path run through crewai's native clients, not LiteLLM** — LiteLLM is only crewai's fallback for providers outside that native list.

### Related Repositories

The full product spans three repos. Changes to this package's public API or `run_analysis()` return shape may require coordinated updates in both sibling repos.

| Repo | Purpose | Key integration |
|---|---|---|
| `../prospectai-backend` | Modal/FastAPI service that runs the pipeline | Imports `ProspectAIFlow`, `Config`; streams SSE to the frontend; **pins a specific `prospectai` version** |
| `../prospectai-web` | Vanilla-JS SPA deployed on Cloudflare Pages | Consumes SSE events from the backend; renders agent progress + final report |

> **Version coupling:** the backend installs the package via `pip_install("prospectai==X.Y.Z")`.
> After merging breaking changes here, bump `VERSION.md` / `pyproject.toml`, publish to PyPI, then
> redeploy the Modal backend so it picks up the new version.

### Adding a New Agent

1. Add an entry to `config/agents.yaml` with `name`, `role`, `goal`, `backstory`, and an `llm:` block.
2. Add a task entry to `config/tasks.yaml` with `description` and `expected_output`.
3. Create `agents/new_agent.py` subclassing `BaseAgent`; implement `create_agent()` returning a `crewai.Agent`.
4. Add the corresponding Pydantic schema to `schemas/agent_outputs.py`.
5. Add a new `@listen` phase in `prospect_ai_flow.py`, store output in `ProspectAIFlowState`, and wire context via the `_slim_*()` helpers.
