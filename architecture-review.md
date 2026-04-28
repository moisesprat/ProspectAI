# Architectural Review Report — ProspectAI

> Reviewed: 2026-04-29 | Reviewer: architecture-reviewer agent | Branch: main

---

## Executive Summary

ProspectAI is a well-conceived, production-grade multi-agent investment pipeline built on CrewAI. The architecture has matured significantly: it features a clean YAML-driven config layer, strong Pydantic v2 data contracts between agents, a hybrid parallel/sequential Flow orchestrator, deterministic computation tools that remove LLM guesswork from math, and meaningful test coverage for all tool-layer logic.

The primary architectural concerns are a not-yet-completed Crew-to-Flow migration leaving a circular dependency and an over-wide `ProspectAICrew` class, a **critical vocabulary mismatch** between the grader tool and the output schema, scattered DRY violations in scoring constants and sector lists, and three agent classes that silently ignore their YAML configuration.

---

## Scope

Files reviewed:

- `main.py`, `prospect_ai_crew.py`, `prospect_ai_flow.py`
- `agents/` — all agent files including `base_agent.py`, `critic_agent.py`
- `config/` — `config.py`, `agents.yaml`, `tasks.yaml`, both loaders
- `schemas/agent_outputs.py`
- `utils/` — all tool and utility files
- `tests/` — all test files
- `pyproject.toml`

---

## Strengths

- **Clean YAML-driven configuration.** Agent identity and task instructions are fully externalised into `config/agents.yaml` and `config/tasks.yaml`. Adding a new agent requires no changes to any Python file except `prospect_ai_crew.py`. `TaskConfigLoader.render()` using Python's `string.Template` is a correct, lightweight substitution approach.

- **Strong Pydantic v2 data contracts.** `schemas/agent_outputs.py` enforces the inter-agent data contract with field validators, model validators, and invariant enforcement (stop < entry zone low < take profit, bucket sum = 100%). Auto-correction of numeric rounding artifacts is a pragmatic engineering decision that avoids false failures from LLM floating-point drift.

- **Deterministic math separated from LLM reasoning.** `TechnicalInterpretationTool`, `FundamentalGraderTool`, `CompositeScoreTool`, and `PortfolioAllocatorTool` contain zero LLM calls — they are pure Python functions wrapped in the `BaseTool` contract. LLMs reason, tools compute. The separation is explicit and well-documented.

- **Parallel execution via CrewAI Flow.** `ProspectAIFlow` correctly uses `@listen(and_(technical_analysis, fundamental_analysis))` for `draft_strategy`, reducing wall-clock time by ~50% for the two independent analysis phases.

- **Slim context helpers.** The six `_slim_*` methods in `ProspectAIFlow` project typed Pydantic state into minimal JSON for downstream context, preventing token bloat and reducing hallucination risk.

- **Module-level yfinance cache.** `utils/yfinance_cache.py` prevents redundant network calls when multiple tools process the same tickers. The `clear()` call at the start of each `run_analysis()` correctly scopes the cache to a single pipeline execution.

- **Post-generation validator.** `utils/recommendation_validator.py` runs deterministic sanity checks after LLM output, catching structural errors the schema cannot.

- **Useful test suite.** Tool-layer tests provide genuine coverage of computation logic with all HTTP and yfinance calls mocked. Schema tests exercise edge cases rather than just happy paths.

- **Execution metrics.** `ExecutionTracker` captures per-phase wall-clock time and LLM token usage by model — a production-quality observability feature.

---

## Findings

### CRITICAL

---

**F-01 | `utils/fundamental_grader_tool.py`:82–100 and `schemas/agent_outputs.py`:120–124 | Valuation vocabulary mismatch between grader tool and Pydantic schema**

The `FundamentalGraderTool` emits `valuation_grade` values from the set `{"CHEAP", "FAIR", "EXPENSIVE", "VERY_EXPENSIVE"}`. The `FundamentalRating` Pydantic schema declares `valuation: Literal["Undervalued", "Fairly Valued", "Overvalued"]`. These vocabularies do not overlap. The LLM must silently translate between the two, with no enforcement that "CHEAP" becomes "Undervalued" rather than "Fairly Valued". A high-PE stock could receive a favorable fundamental rating.

**Impact:** Silent data quality corruption in the fundamental layer. The `CriticAgent` `VALUATION_IGNORED` check compares against task context (grader vocabulary), not the schema field — so even the critic cannot catch this consistently.

**Fix:** Update `FundamentalRating.valuation` in `schemas/agent_outputs.py` to `Literal["CHEAP", "FAIR", "EXPENSIVE", "VERY_EXPENSIVE"]`. Update the `_quality_map` translation in `prospect_ai_flow.py::_slim_fundamental()` to pass grader vocabulary directly. Verify `tasks.yaml` descriptions reference grader vocabulary consistently.

---

**F-02 | `main.py`:138 and `utils/reddit_sentiment_tool.py`:52–102 | Three supported sectors are unreachable via CLI**

`main.py`'s `--sector` argument accepts only five values: `["Technology", "Healthcare", "Finance", "Energy", "Consumer"]`. `RedditSentimentTool.SECTOR_TICKERS` supports eight sectors, adding `"Industrials"`, `"Real Estate"`, and `"Utilities"`. These three sectors have production-ready ticker lists and subreddit configs that go unused.

**Fix:** Replace the hardcoded `choices` list in `main.py` with `list(RedditSentimentTool.SECTOR_TICKERS.keys())`. Update `CLAUDE.md` supported sectors list.

---

### MAJOR

---

**F-03 | `prospect_ai_flow.py`:81–82 and `:464 | Circular dependency between `ProspectAIFlow` and `ProspectAICrew`**

`ProspectAIFlow.__init__()` imports `ProspectAICrew` via a deferred import to construct `self._factory`, and `run_analysis()` imports it again to call `ProspectAICrew._parse_result()`. `ProspectAICrew` currently plays three roles: deprecated orchestrator, task/agent factory, and static parse utility. Importing a `DeprecationWarning`-emitting class just to call a JSON parsing utility is a fragile anti-pattern.

**Fix:** Extract `_parse_result` as a module-level function (in `prospect_ai_flow.py` or `utils/pipeline_result_parser.py`). Extract task/agent factory logic into a `TaskFactory` class with no deprecation baggage. `ProspectAIFlow` should depend only on `TaskFactory`.

---

**F-04 | `agents/fundamental_analyst_agent.py`:20, `agents/investor_strategic_agent.py`:18, `agents/critic_agent.py`:16 | Three agents hardcode verbose/allow_delegation, bypassing YAML config**

`MarketAnalystAgent` and `TechnicalAnalystAgent` correctly use `self.verbose` and `self.allow_delegation` (loaded from YAML). The three other concrete agents hardcode `verbose=True, allow_delegation=False`. If `verbose: false` is set in `agents.yaml`, the change has no effect — failing silently.

**Fix:** Replace `verbose=True, allow_delegation=False` with `verbose=self.verbose, allow_delegation=self.allow_delegation` in all three agents.

---

**F-05 | `utils/composite_score_tool.py`:21–22 and `utils/fundamental_grader_tool.py`:19–20 | Scoring constants duplicated across two tools**

`_FINANCIAL_HEALTH_SCORE` and `_GROWTH_OUTLOOK_SCORE` are defined identically in both files. If the formula is updated in one but not the other, `FundamentalGraderTool` and `CompositeScoreTool` will silently disagree.

**Fix:** Extract both dicts to `utils/scoring_constants.py` and import from both tools. Add a consistency test.

---

**F-06 | `utils/technical_analysis_tool.py`:449–455 | `_get_atr_status()` is a stub that always returns `"Normal Volatility"`**

The method has a single `return "Normal Volatility"` for all stocks. `TechnicalInterpretationTool` correctly classifies volatility using ATR ratio thresholds (`>0.03` = HIGH), but the raw indicator payload always contradicts it with `"Normal Volatility"`. This creates an internal contradiction the LLM must reconcile.

**Fix:** Implement real ATR status using the same `atr_ratio` thresholds as `TechnicalInterpretationTool`. The function already receives the `atr` value; it needs `current_price` as a second parameter (available at the call site).

---

**F-07 | `prospect_ai_crew.py`:94–138 | `_PHASE_CONFIG` dict rebuilt on every `build_task()` call, creating new tool instances each time**

`build_task()` is called six times per pipeline run. Each call reconstructs the full `_PHASE_CONFIG` dict, instantiating new tool objects. Tool initialization runs Pydantic model construction on every call.

**Fix:** Move `_PHASE_CONFIG` to a class attribute or `@cached_property` initialized once in `__init__`.

---

**F-08 | `tests/test_crew.py`:298–365 | `ProspectAIFlow` async phases have no individual test coverage**

`TestProspectAIFlowRunAnalysis` tests `run_analysis()` but none of the six `@start`/`@listen` async methods are tested individually. Key untested paths include: `_check_error()` raising on `state.error`, `_extract_pydantic()` fallback branch, `_emit_progress()` callback, and the `and_()` gating behavior.

**Fix:** Add `pytest-asyncio` to dev dependencies. Write unit tests for each phase method, mocking `_factory.build_task()` and `_make_crew().akickoff()` with synthetic `CrewOutput`.

---

### MINOR

---

**F-09 | `utils/reddit_sentiment_tool.py`:58 | Duplicate ticker "NET" in Technology sector list**

`"NET"` appears twice. The dict comprehension silently overwrites the first, but the list-based counters will double-count mentions.

**Fix:** Remove the second `"NET"` from the list.

---

**F-10 | `agents/technical_analyst_agent.py`:11–20 | Stale scaffolding: `sys.path` manipulation and 8 unused imports**

`sys.path` manipulation was needed when the file was run directly as a script; the project now uses `pyproject.toml`. Eight imports at lines 7–9 are unused. A duplicate `from crewai import Agent` appears inside `create_agent()` on line 34. Same `sys.path` pattern appears in `utils/enhanced_pdf_generator.py`:14–17.

**Fix:** Remove lines 7–20 from `technical_analyst_agent.py`. Remove the duplicate inner import. Apply the same cleanup to `enhanced_pdf_generator.py`.

---

**F-11 | `agents/investor_strategic_agent.py`:26–50 | Dead `execute_task()` method with TODO stub**

Returns a hardcoded dict and is never called anywhere. Predates the CrewAI task-based architecture.

**Fix:** Delete lines 26–50 and the unused `from typing import Dict, Any, List` import.

---

**F-12 | `prospect_ai_flow.py`:226 and `:317 | `_quality_map` dict defined twice**

`_slim_fundamental()` and `_critic_reference_table()` each define the identical local `_quality_map = {"High": "STRONG", "Medium": "ADEQUATE", "Low": "WEAK"}`.

**Fix:** Extract as a module-level constant at the top of `prospect_ai_flow.py`.

---

**F-13 | `config/config.py`:83–116 | Six unused class-level constants**

`MARKET_DATA_SOURCES`, `TECHNICAL_INDICATORS`, `FUNDAMENTAL_METRICS`, `RISK_LEVELS`, `REWARD_LEVELS`, `OUTPUT_FORMAT`, `REPORT_TEMPLATE` are never referenced in any production code path.

**Fix:** Remove from `config.py`.

---

**F-14 | `agents/__init__.py` | `CriticAgent` not exported from agents package**

`agents/__init__.py` exports all other agents but not `CriticAgent`. `from agents import CriticAgent` raises `ImportError`.

**Fix:** Add `from .critic_agent import CriticAgent` to `agents/__init__.py`.

---

**F-15 | `prospect_ai_crew.py`:267–280 and `prospect_ai_flow.py`:27–33 | `_AGENT_NAMES` list duplicated**

The agent name list is defined as a module-level constant in `prospect_ai_flow.py` and rebuilt inline in `prospect_ai_crew.py`. Adding a phase requires updating both.

**Fix:** Import `_AGENT_NAMES` from `prospect_ai_flow.py` into `prospect_ai_crew.py`.

---

**F-16 | `prospect_ai_crew.py`:328–338 and `prospect_ai_flow.py`:467–476 | `validation_warnings` duplicated in result dict**

`validation_issues` appears at both `result["validation_warnings"]` (top-level) and `result["result"]["validation_warnings"]` (inside the structured payload).

**Fix:** Remove the mutation that inserts it into `structured`. Read only from the top-level key.

---

**F-17 | `utils/reddit_sentiment_tool.py`:292 and `:356 | Synchronous `time.sleep(2)` in network layer**

Every subreddit fetch starts with `time.sleep(2)`. A 5-subreddit Technology scan sleeps for 10+ seconds of wall-clock time before any response is processed. The `time.sleep(60)` retry path on 429 is even more costly.

**Fix:** Use `asyncio.sleep()` in async context, or reduce to 1-second gaps (sufficient for Reddit's unauthenticated rate limit). Better: concurrent fetch with a semaphore.

---

**F-18 | `utils/technical_analysis_tool.py`:147–149 | `import ta` deferred inside method on every call**

`import ta` is deferred inside `_calculate_all_indicators()`. Python caches it in `sys.modules`, so performance is not the issue — but it hides a required dependency and surfaces `ImportError` at runtime rather than startup.

**Fix:** Move `import ta` to the module top level.

---

### SUGGESTIONS

---

**S-01 | `config/agent_config_loader.py`:115–139 | `validate_config()` uses `print()` and is never called at runtime**

Replace `print()` calls with `logger.error()`/`logger.info()`. Call `validate_config()` once during startup in `main.py` to surface YAML errors before the pipeline begins.

---

**S-02 | `agents/base_agent.py`:77–90 | `reload_config()` partially reimplements `__init__`**

`reload_config()` re-assigns agent identity fields but not `max_tokens`, `max_iter`, `llm_config`, etc. A partial reload is worse than no reload. Either implement a full reload or remove the method (it is not called in production).

---

**S-03 | `prospect_ai_flow.py`:87–95 | Phase progress index passed as a magic integer literal**

Each `@listen` method manually passes the correct integer to `_emit_progress()`. If phases are reordered, progress agent names will silently mismatch.

**Fix:** Replace the integer index with the phase name string; look up the index via `PHASES.index(phase_name)`.

---

**S-04 | `utils/enhanced_pdf_generator.py` | Entire file is untested and disconnected from the live pipeline**

886 lines not imported by any production code path. `reportlab` is not in `pyproject.toml`.

**Fix:** Either connect to the pipeline (add `--pdf` CLI flag, add to optional dependencies, write a smoke test) or move to `scripts/` to signal it is not part of the core pipeline.

---

## Architecture: Current vs. Ideal State

### Current
```
main.py
  └─ ProspectAIFlow (crewai.Flow)
       ├─ __init__: suppresses DeprecationWarning, deferred import of ProspectAICrew as _factory
       ├─ run_analysis(): deferred import of ProspectAICrew again for _parse_result
       └─ each @listen phase calls _factory.build_task()

ProspectAICrew (deprecated)
  ├─ Role 1: deprecated orchestrator (run_analysis / create_tasks)
  ├─ Role 2: task/agent factory (build_task)
  └─ Role 3: static JSON parsing utility (_parse_result)
```

### Target
```
main.py
  └─ ProspectAIFlow (crewai.Flow)
       ├─ __init__: imports TaskFactory (no deprecation warning)
       ├─ run_analysis(): calls parse_pipeline_result() utility function
       └─ each @listen phase calls _factory.build_task()

TaskFactory
  ├─ Constructs agents and tools (moved from ProspectAICrew.__init__)
  └─ build_task(phase, sector, today, prior_context) → Task

utils/pipeline_result_parser.py
  └─ parse_pipeline_result(crew_result) → Dict

ProspectAICrew (legacy only)
  ├─ Wraps TaskFactory for backward compat
  └─ Still emits DeprecationWarning for direct callers
```

---

## Improvement Plan

### Phase 1 — Immediate (3–5 hours)

| # | Finding | Effort |
|---|---|---|
| 1 | Fix valuation vocabulary mismatch (F-01) | LOW — update schema + `_slim_fundamental()` translation |
| 2 | Add missing CLI sectors (F-02) | LOW — derive `choices` from `SECTOR_TICKERS.keys()` |
| 3 | Fix three agents bypassing YAML config (F-04) | LOW — two-line change per agent |
| 4 | Extract scoring constants to shared module (F-05) | LOW — new `utils/scoring_constants.py` + imports |
| 5 | Fix `_get_atr_status()` stub (F-06) | LOW — add `current_price` param, implement thresholds |
| 6 | Remove duplicate "NET" ticker (F-09) | LOW — delete one line |
| 7 | Delete dead `execute_task()` stub (F-11) | LOW — delete 25 lines |

### Phase 2 — Short-term (6–10 hours)

| # | Finding | Effort |
|---|---|---|
| 1 | Break circular dependency: extract `TaskFactory` + `_parse_result` (F-03) | MEDIUM — 2–3 hours |
| 2 | Add Flow phase unit tests (F-08) | HIGH — 3–4 hours, add `pytest-asyncio` |
| 3 | Move `_PHASE_CONFIG` out of `build_task()` (F-07) | LOW — 30 min |
| 4 | Clean up stale scaffolding (F-10) | LOW — 15 min |
| 5 | Fix `validation_warnings` duplication (F-16) | LOW — 15 min |
| 6 | Fix `_quality_map` + `_AGENT_NAMES` duplication (F-12, F-15) | LOW — 20 min |
| 7 | Add `CriticAgent` to `agents/__init__.py` (F-14) | LOW — 1 line |

### Phase 3 — Long-term

| # | Finding | Effort |
|---|---|---|
| 1 | Replace sync Reddit sleep with async rate-limiting (F-17) | MEDIUM — 2 hours |
| 2 | Move `import ta` to module top level (F-18) | LOW — 5 min |
| 3 | Remove vestigial constants from `config.py` (F-13) | LOW — 10 min |
| 4 | Connect or remove `enhanced_pdf_generator.py` (S-04) | MEDIUM — 1–3 hours |
| 5 | Add `validate_config()` to startup path (S-01) | LOW — 30 min |
| 6 | Complete or remove `reload_config()` in `BaseAgent` (S-02) | LOW — 20 min |

---

## Metrics Summary

| Dimension | Score (1–5) | Notes |
|---|---|---|
| Separation of Concerns | 4/5 | Strong layering: config / agents / tools / schemas / orchestrator. Minor violations in `ProspectAICrew` roles and agents bypassing YAML config. |
| Maintainability | 3/5 | YAML config, Pydantic schemas, docstrings are good. DRY violations, dead code, and the circular Crew/Flow dependency reduce this. |
| Efficiency | 3/5 | Parallel tech/fundamental phases are excellent. Synchronous Reddit sleeps (~10s floor) and per-call tool instantiation are clear regressions. |
| Extensibility | 4/5 | Adding a new agent or sector is well-documented. The sector CLI gap (F-02) and vocabulary mismatch (F-01) are the main friction points. |
| Convention Adherence | 3/5 | Tool pattern and LLM switching are consistently applied. 3/5 agents ignore YAML `verbose`/`allow_delegation`. Schema vocabulary mismatch is the most serious convention break. |
| Test Coverage | 3/5 | Tool and schema tests are thorough. Flow phase tests are absent. |
| **Overall** | **3.5/5** | Solid, production-aware architecture with a clear improvement path. Critical vocabulary mismatch and the sector gap are immediate priorities. Crew→Flow migration cleanup is the main medium-term investment. |
