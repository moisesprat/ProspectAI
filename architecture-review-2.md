# Architectural Review Report — ProspectAI (Round 2)

## Executive Summary

ProspectAI's recent fixes (F-01 through F-08, plus bucket auto-correction) have meaningfully improved the codebase: the circular import is broken, scoring constants are centralized, agent settings now flow from YAML, and flow phases have unit-test coverage. However, the largest architectural risk in the current state is **schema-vs-tasks.yaml contract drift** — particularly in `fundamental_analysis` where the YAML output spec uses field names (`raw_fundamentals`, `assessment`, `risk_factors`, `catalysts`) that do not exist in the Pydantic schema (`valuation_metrics`, `fundamental_rating`, `key_risks`, `key_strengths`). All previously open MINOR issues (F-09 through F-18) are still present. New issues are documented below.

---

## Findings

### CRITICAL

**F-19 — `tasks.yaml` `fundamental_analysis` output spec is incompatible with `FundamentalAnalysisOutput` schema**
- Location: `config/tasks.yaml` (STEP 4 of fundamental_analysis task) vs `schemas/agent_outputs.py:127-140`
- Description: tasks.yaml instructs the LLM to emit `stock_analyses[]` with sub-fields `raw_fundamentals`, `assessment.financial_health` (STRONG/ADEQUATE/WEAK), `assessment.growth_outlook`, `risk_factors`, `catalysts`. The Pydantic schema requires `fundamental_analysis[]` with `valuation_metrics`, `fundamental_rating.quality` (Low/Medium/High), `key_risks`, `key_strengths`, `investment_thesis`. The LLM receives contradictory instructions.
- Impact: Every run risks `RuntimeError("Pydantic validation failed for fundamental_analysis")`.
- Fix: Rewrite tasks.yaml STEP 4 to use the exact schema field names. Simultaneously align Literal values (see F-21).

**F-20 — `tasks.yaml` `technical_analysis` output spec omits required schema fields**
- Location: `config/tasks.yaml` (STEP 4 of technical_analysis task) vs `schemas/agent_outputs.py:87-100`
- Description: Schema requires `technical_score: TechnicalScore` and `investment_recommendation: str (min_length=50)` on every entry. tasks.yaml never asks for them. Array is named `stock_analyses[]` in YAML but `technical_analysis[]` in schema.
- Impact: LLM guided by YAML produces output that conflicts with the schema.
- Fix: Either add the missing fields to tasks.yaml, or delete them from the schema if they are not consumed downstream (they are not consumed by any slim helper or context builder).

### MAJOR

**F-09 — Duplicate "NET" ticker in Technology sector** (still present)
- Location: `utils/reddit_sentiment_tool.py` (SECTOR_TICKERS["Technology"])
- "NET" appears twice. `mention_counts` de-dupes via dict, but the ranking loop may yield two NET entries in the top-5.
- Fix: `list(dict.fromkeys(tickers))` to deduplicate on use, or remove the duplicate from the constant.

**F-21 — Schema literals misaligned with deterministic tool outputs**
- Location: `schemas/agent_outputs.py:122-123` vs `utils/fundamental_grader_tool.py`
- `FundamentalRating.quality: Literal["Low","Medium","High"]` but grader emits `STRONG/ADEQUATE/WEAK`. `growth: Literal["Declining","Stable","Moderate Growth","High Growth"]` but grader emits `HIGH/MODERATE/LOW/DECLINING`. Two maps (`_quality_map`, `_growth_map`) must translate at runtime.
- Fix: Change schema literals to `Literal["STRONG","ADEQUATE","WEAK"]` and `Literal["HIGH","MODERATE","LOW","DECLINING"]`. Eliminates F-12 and the translation maps.

**F-22 — Module-level yfinance cache is unsafe for concurrent runs**
- Location: `utils/yfinance_cache.py:17-23`
- Module-level `_history_cache`, `_info_cache` etc. are shared across all concurrent `run_analysis()` calls. `clear()` at the start of one run wipes another run's cached data.
- Impact: Dormant for single-run CLI usage; critical when Modal serves concurrent requests.
- Fix: Use `contextvars.ContextVar` for the cache, or inject a per-run cache instance into tools.

**F-23 — `recommendation_validator` ignores `scaled_entry_setups`**
- Location: `utils/recommendation_validator.py:22-117`
- Stop/TP and R/R validation only runs on `trade_setup`. SCALED-ENTRY positions (which have `trade_setup=None`) are unchecked.
- Fix: Extract `_validate_setup(ticker, setup, label)` and call it for both `trade_setup` and each entry in `scaled_entry_setups`.

**S-27 — `final_strategy` phase has no tools in TaskFactory (PortfolioAllocatorTool missing)**
- Location: `prospect_ai_crew.py:79-83` (`TaskFactory._phase_config["final_strategy"]["tools"]: []`)
- tasks.yaml STEP 2 CASE B ("Call allocate_portfolio ONCE with revised actions") cannot execute because the tool is not wired. The legacy ProspectAICrew correctly had `[CompositeScoreTool(), PortfolioAllocatorTool()]` for final_strategy.
- Fix: Add `PortfolioAllocatorTool()` to `_phase_config["final_strategy"]["tools"]`.

### MINOR

**F-10 — Stale scaffolding in `technical_analyst_agent.py`** (still present)
- `sys.path.insert` block, unused imports (`os`, `sys`, `datetime`, `Dict`, `Any`, `List`, `Optional`), redundant `from crewai import Agent` inside `create_agent()`.
- Fix: Delete path manipulation and prune imports.

**F-11 — Dead `execute_task()` in `InvestorStrategicAgent`** (still present)
- Returns hardcoded empty dict, never called.
- Fix: Delete the method.

**F-12 — `_quality_map` defined twice in `prospect_ai_flow.py`** (still present)
- Identical local dict in `_slim_fundamental` and `_critic_reference_table`.
- Fix: Lift to module-level constant. Disappears entirely when F-21 is implemented.

**F-13 — Unused constants in `config.py`** (still present)
- `MARKET_DATA_SOURCES`, `TECHNICAL_INDICATORS`, `FUNDAMENTAL_METRICS`, `RISK_LEVELS`, `REWARD_LEVELS`, `OUTPUT_FORMAT`, `REPORT_TEMPLATE` — none referenced anywhere.
- Fix: Delete all of them.

**F-14 — `CriticAgent` not exported from `agents/__init__.py`** (still present)
- `agents.__all__` lists only the original four agents.
- Fix: Add `from .critic_agent import CriticAgent` and append to `__all__`.

**F-15 — `_AGENT_NAMES` duplicated** (still present)
- `prospect_ai_flow.py:27-34` (module-level) and `prospect_ai_crew.py:272` (scoped in `run_analysis`).
- Fix: Import from flow into crew, or delete after F-25 is resolved.

**F-16 — `validation_warnings` dict comprehension duplicated** (still present)
- Identical four-key projection from `ValidationIssue` built twice in `run_analysis`.
- Fix: Add `to_dict()` method to `ValidationIssue` and call once.

**F-17 — Synchronous `time.sleep` in Reddit tool** (still present)
- `time.sleep(2)` per request and `time.sleep(60)` on rate-limit inside an async flow phase.
- Fix: Use `asyncio.sleep` or `run_in_executor`.

**F-18 — `import ta` deferred inside method** (still present)
- `ta` is a hard dependency; deferring adds no value. The try/except hiding an `ImportError` is misleading.
- Fix: Move `import ta` to the top of `technical_analysis_tool.py`.

**F-24 — Stale comment in `tasks.yaml` references removed orchestration**
- Line 4 says "Context wiring defined in `prospect_ai_crew.py`". It is now in `prospect_ai_flow.py`.
- Fix: Update comment or remove it.

**F-25 — Legacy `ProspectAICrew` carries ~290 lines of dead-code surface**
- `_get_llm()`, `create_tasks()`, `run_analysis()` in `ProspectAICrew` are never called. `_parse_result` is a near-duplicate of `_parse_crew_result`.
- Fix: Extract `TaskFactory` to `task_factory.py`, delete `ProspectAICrew` and its tests, or set a clear removal milestone.

### SUGGESTIONS

**S-26 — `main()` mutates `os.environ["MODEL"]` irreversibly**
- Location: `main.py:166-178`
- In a warm container, a second call reads `anthropic/anthropic/claude-...` because prefix-stripping runs only once.
- Fix: Pass the resolved model into `ProspectAIFlow` rather than writing to env.

**S-28 — `_slim_market_for_analysis` drops `mention_count`**
- Minor token-save that drops potentially useful tie-breaker data.
- Fix: Consider keeping `mention_count` in the slim output.

**S-29 — LONG-BUY/WAIT-FOR-ENTRY silently leaves `trade_setup=None` when price unavailable**
- Location: `schemas/agent_outputs.py:199-212`
- No error or warning when the auto-construction path is skipped.
- Fix: Log a warning or raise in the no-price case for action types that require a trade setup.

**S-30 — `AgentConfigLoader` parses YAML 5 times on TaskFactory construction**
- No memoization; `agents.yaml` parsed once per agent class instantiated.
- Fix: `@lru_cache` on the YAML load.

---

## Improvement Plan

### Phase 1 — Immediate (Critical correctness)

1. **S-27** — Add `PortfolioAllocatorTool()` to `TaskFactory._phase_config["final_strategy"]["tools"]`. ~5 min. This fixes a broken feature silently failing in production.
2. **F-21** — Align `FundamentalRating` literals with grader output (`STRONG/ADEQUATE/WEAK`, `HIGH/MODERATE/LOW/DECLINING`). Update schema + tests. ~30 min. Eliminates F-12 and the runtime translation maps.
3. **F-19 + F-20 + F-24** — Rewrite tasks.yaml STEP 4 specs to match schema field names exactly. ~2-3 h. Eliminates the LLM contradiction that causes random pipeline failures.
4. **F-09** — Remove duplicate "NET" from SECTOR_TICKERS. ~2 min.

### Phase 2 — Short-term

5. **F-23** — Extend `recommendation_validator` to cover `scaled_entry_setups`. ~30 min.
6. **F-22** — Per-run cache isolation (ContextVar or injection). ~2 h.
7. **F-10, F-11, F-13, F-14** — Dead-code deletions. ~30 min total.
8. **F-16** — `ValidationIssue.to_dict()`. ~10 min.
9. **F-18** — Move `import ta` to module top. ~2 min.

### Phase 3 — Long-term

10. **F-25** — Retire `ProspectAICrew`. Extract `TaskFactory` to its own module. Remove deprecated class + tests.
11. **F-17** — Async-safe Reddit tool.
12. **S-26** — Idempotent model env mutation in `main()`.
13. **S-30** — Memoize `AgentConfigLoader`.

---

## Metrics Summary

| Dimension | Score (1–5) | Notes |
|---|---|---|
| Separation of Concerns | 4 | Tools/agents/orchestrator boundaries are clean. Slim helpers are well-isolated. |
| Maintainability | 3 | tasks.yaml/schema drift (F-19, F-20) and duplicated constants (F-12, F-15, F-16) hurt this. |
| Efficiency | 4 | yfinance cache, batch tools, parallel phases. F-17 sleeps are the only blemish. |
| Extensibility | 4 | YAML-driven agents + Pydantic schemas make adding an agent or sector easy. F-22 limits horizontal scale. |
| Convention Adherence | 3 | F-09, F-10, F-11, F-13 show drift in older files. New code (CriticAgent, TaskFactory) is clean. |
| **Overall** | **3.5** | Phase-1 fixes are all small but high-impact. Closing them brings this to a solid 4. |
