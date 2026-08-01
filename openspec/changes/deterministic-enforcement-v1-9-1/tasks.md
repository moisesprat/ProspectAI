## 1. Regression fixtures (write first, red by construction)

- [x] 1.1 Build fixture from failing run #1: Final Strategist output that changed an
      action without calling `allocate_portfolio` and contains hand-written
      `allocation_pct`/`trade_setup`/fabricated entry zone.
- [x] 1.2 Build fixture from failing run #2 (published Energy-sector output): 25%
      position under conservative's 15% cap, stops at 5.0–5.4% vs the 3% cap,
      round-number setups, plus its `reserved_pct` inconsistency.
- [x] 1.3 Build fixture for the v1.9.0 zero-width entry zone (TRENDING regime edge case).
- [x] 1.4 Build fixture for a Critic `revision_directives` entry ordering WAIT-FOR-ENTRY
      at `entry_zone_status=CURRENT_ENTRY`.

## 2. `PortfolioBoundsValidator`

- [x] 2.1 Create `utils/portfolio_bounds_validator.py` with `validate(final_output,
      risk_profile) -> list[Violation]`: per-position allocation cap, stop-distance cap,
      minimum R/R, LONG-BUY/WAIT-FOR-ENTRY invariant `stop_loss < entry_zone_low ≤
      entry_zone_high < take_profit`, minimum entry-zone width, and portfolio-level
      bucket sum `deployed_pct + reserved_pct + cash_reserve_pct == 100 ± 0.5`.
- [x] 2.2 Reuse `PROFILE_BOUNDS` from `utils/portfolio_allocator_tool.py` as the single
      source of truth for cap/stop/R-R constants — do not duplicate the table.
- [x] 2.3 Define `BoundsViolationError(violations: list[dict])` (structured: ticker,
      rule, expected, actual).
- [x] 2.4 Unit test `PortfolioBoundsValidator` against hand-constructed compliant and
      non-compliant fixtures, independent of the Flow.
- [x] 2.5 Unit test: replay the fixture from 1.2 directly through the validator and
      assert it raises `BoundsViolationError` listing the allocation-cap and
      stop-distance violations.
- [x] 2.6 Property test: generate random valid `allocate_portfolio` inputs (actions,
      composite scores, entry zones) across both risk profiles and assert the tool's
      output always passes `PortfolioBoundsValidator`.

## 3. Flow-authoritative allocator re-invocation

- [x] 3.1 In `prospect_ai_flow.py`, after `final_strategy`, build the
      `allocate_portfolio` payload from the Final Strategist's decided actions
      (ticker, action, composite_score, entry_zone_low/high, current_price) and invoke
      the tool unconditionally (not only when actions changed vs. the draft).
- [x] 3.2 Overwrite `allocation_pct`, `trade_setup`, `scaled_entry_setups`,
      `deployed_pct`, `reserved_pct`, `cash_reserve_pct`, `total_allocated_pct` on the
      final output with the tool's result. (`scaled_entry_setups` does not exist in
      the current schema/tool output — nothing to overwrite; only the fields that
      actually exist are overwritten.)
- [x] 3.3 Run `PortfolioBoundsValidator` on the result; on failure, re-invoke
      `allocate_portfolio` once more and re-validate; on second failure, raise
      `BoundsViolationError` from `run_analysis()` instead of returning a result.
- [x] 3.4 Remove the Final Strategist's "CASE B" branch (LLM decides whether to
      re-invoke `allocate_portfolio`) from `config/tasks.yaml`'s `final_strategy` task
      description; narrow its scope to deciding actions/rationale only.
- [x] 3.5 Integration test: fixture from 1.1 (LLM skipped the tool call) now produces
      correct, tool-computed numbers in the Flow's output.
- [x] 3.6 Integration test: fixture from 1.3 (zero-width entry zone) is caught by
      `PortfolioBoundsValidator` before publication (paired with the
      `technical_interpretation_tool.py` TRENDING-regime fix already landed separately).

## 4. `ActionPolicyGate`

- [x] 4.1 Create `utils/action_policy_gate.py` encoding the `entry_zone_status ×
      risk_profile → allowed actions` table from `config/tasks.yaml`'s STEP 3 guidance
      as a data structure (function or dict keyed on `(entry_zone_status,
      risk_profile)` returning the allowed action set).
- [x] 4.2 In `prospect_ai_flow.py`, between `critique_review` and `final_strategy`,
      resolve each `revision_directives` entry to its target ticker/position (reuse the
      ticker-matching approach from `_critic_reference_table()`), read that position's
      `entry_zone_status`/`risk_profile`, and evaluate against the gate.
- [x] 4.3 Drop directives whose requested action is outside the allowed set from the
      context passed to `final_strategy`; log ticker, rejected action, and reason.
- [x] 4.4 Pass through unfiltered any directive that does not request a specific action
      change (rationale-only or non-action concerns).
- [x] 4.5 Unit test `ActionPolicyGate`'s table resolution for all
      `entry_zone_status`/`risk_profile` combinations.
- [x] 4.6 Integration test: fixture from 1.4 (Critic orders WAIT-FOR-ENTRY at
      CURRENT_ENTRY) is dropped before reaching `final_strategy`, and the Final
      Strategist's context does not contain it.
- [x] 4.7 Integration test: a directive requesting a policy-permitted action (e.g.
      aggressive LONG-BUY on PULLBACK_ENTRY with sufficient momentum) passes through
      unchanged.

## 5. Sentiment availability sentinel

- [x] 5.1 Add `sentiment_available: bool = True` to `MarketAnalysisOutput` in
      `schemas/agent_outputs.py`; change `average_sentiment` to accept `None`.
- [x] 5.2 Update the Market Analyst task/agent path so that when
      `RedditSentimentTool.fallback_required=True` and the Serper fallback also fails,
      it sets `sentiment_available=False` and `average_sentiment=null` for affected
      candidates instead of `0.0`.
- [x] 5.3 Update `CompositeScoreTool` to check sentiment availability per stock and, when
      unavailable, compute `composite_score` from technical + fundamental components
      only, with weights renormalized so max attainable score is still 100.
- [x] 5.4 Add one instruction to the Critic's task description: sentiment-based findings
      are out of scope when `sentiment_available=false` (Critic prompt otherwise
      unchanged).
- [x] 5.5 Update report rendering to show "sentiment: no data" for tickers with
      `sentiment_available=false`. (No standalone report-renderer module exists in this
      repo — the LLM-generated prose in `market_analysis`/`draft_strategy` now uses the
      literal phrase, and `sentiment_available` is surfaced into every downstream
      phase's context via `_slim_market_for_analysis()`/`_slim_market_for_strategy()`.)
- [x] 5.6 Unit tests: `CompositeScoreTool` renormalization for unavailable sentiment;
      `MarketAnalysisOutput` accepts `average_sentiment=null` only when
      `sentiment_available=false`.
- [x] 5.7 Unit test (Critic validation spec): Critic does not cite `average_sentiment`
      or a sentiment trend as grounds for a finding when `sentiment_available=false`.
      (The Critic itself is LLM-driven and not directly unit-testable; verified at the
      two testable seams instead — the prompt instruction exists in `tasks.yaml`, and
      the context builders correctly surface `average_sentiment=null`/
      `sentiment_available=false` to the Critic.)

## 6. Serper retry classification

- [x] 6.1 Diagnose the current Serper 400 root cause (log the response body against the
      known request shape; check for a malformed/deprecated query parameter). Static
      review of the request construction (`{"q": ..., "num": 10}`, no `gl`/`location`/
      `hl` set since TaskFactory never configures them) found no malformed parameter —
      the payload shape matches Serper's documented contract. Root-causing the specific
      historical 400 requires the actual response body from a live failing run, which
      isn't available in this session; `PatientSerperDevTool` (6.2) now logs that body
      on every non-retryable failure so the next occurrence is diagnosable.
- [x] 6.2 Update the Serper tool's error handling: 4xx fails fast (no retry, log response
      body, mark source unavailable); only 429/5xx retry, max 2 attempts with backoff.
      Implemented as `utils/patient_serper_tool.py::PatientSerperDevTool`, a thin
      subclass of `crewai_tools.SerperDevTool` overriding `_make_api_request` — the
      upstream tool has no retry logic of its own (one request, raises immediately), so
      wrapping was the only way to add retry classification without forking the
      third-party package. Wired into `TaskFactory.search_tool` in `prospect_ai_crew.py`.
- [x] 6.3 Fix the root-caused 400 issue found in 6.1. No fixable defect was found in the
      request construction itself (see 6.1) — nothing to change beyond the fail-fast/
      retry behavior in 6.2. Revisit once a live 400 response body is captured.
- [x] 6.4 Unit test: a 400 response results in exactly zero retries and marks the source
      unavailable. A 429/503 response retries up to 2 times before failing.

## 7. `reserved_allocations` and Critic checklist rewording

- [x] 7.1 Add `reserved_allocations: [{ticker, pct}]` to `PortfolioAllocatorTool`'s
      output, derived from the existing `final_allocs` filtered to WAIT-FOR-ENTRY
      positions.
- [x] 7.2 Add invariant checks reachable by `PortfolioBoundsValidator`:
      `reserved_pct == sum(reserved_allocations[].pct)`, and every WAIT-FOR-ENTRY
      position has a `reserved_allocations` entry with `pct > 0`. (Already implemented
      in Group 2 — `portfolio_bounds_validator.py` checks `reserved_allocations`
      whenever present in the final output.)
- [x] 7.3 Reword the `WAIT_ENTRY_ZERO_ALLOC` checklist item in
      `config/tasks.yaml`'s `critique_review` task to check against
      `reserved_allocations` per position, not the aggregate `reserved_pct`.
- [x] 7.4 Unit test: `reserved_allocations` sums to `reserved_pct` across multiple
      WAIT-FOR-ENTRY positions.
- [x] 7.5 Unit test (Critic validation spec): Critic flags `WAIT_ENTRY_ZERO_ALLOC` for an
      unattributed WAIT-FOR-ENTRY position even when the aggregate `reserved_pct` is
      positive. (Critic reasoning itself isn't unit-testable in this codebase's
      convention; verified instead that the reworded checklist instruction referencing
      `reserved_allocations` and "aggregate" exists in `tasks.yaml`, plus the
      deterministic `PortfolioBoundsValidator`/`PortfolioAllocatorTool` tests in 7.2/7.4
      that make the same distinction mechanically enforceable regardless of Critic
      output.)

## 8. ETF / sector-benchmark exclusion

- [x] 8.1 Identify the exclusion point(s): the primary Reddit-derived candidate list and
      the Serper/manual fallback candidate list currently used when Reddit/Serper both
      degrade. `RedditSentimentTool.SECTOR_TICKERS` is already ETF-free (curated single
      stocks); the fallback path is free-text LLM extraction from search snippets with
      no such curation — that is where a sector benchmark ETF (e.g. XLE) can leak in.
      Filtering once in the Flow after `MarketAnalysisOutput` is parsed — rather than in
      each source path — covers both uniformly and can't be bypassed by whichever
      source is active.
- [x] 8.2 Add a shared filter (sector benchmark ticker per the existing
      `RedditSentimentTool.SECTOR_TICKERS`-style mapping, plus a generic ETF check)
      applied identically to both the primary and fallback candidate paths.
      Implemented as `utils/candidate_universe_filter.py`, wired into
      `ProspectAIFlow.market_analysis()` right after parsing.
- [x] 8.3 Confirm XLE (or any sector benchmark ETF) cannot reach `MarketAnalysisOutput`
      via either path.
- [x] 8.4 Unit test: fallback candidate list is filtered the same way as the primary
      list — a benchmark ticker present in the fallback source is excluded.

## 9. Version bump and release prep

- [x] 9.1 Bump `pyproject.toml`/`VERSION.md` to `1.9.1`.
- [x] 9.2 Run the full test suite (`pytest tests/ -v`) including all new fixtures and
      unit/integration tests added above. 298 passed. (Also fixed the local `.venv`
      itself missing a `pytest` install, which had been silently causing `pytest` to
      resolve to the global, version-mismatched Python — unrelated pre-existing
      environment issue, now corrected.)
- [x] 9.3 Update `CLAUDE.md` if any new module, tool, or return-shape detail
      (`BoundsViolationError`, `sentiment_available`, `reserved_allocations`) needs to be
      reflected in the architecture reference tables. Updated: Agent Pipeline steps 5-6,
      Key Files table (4 new `utils/` modules), Task → Tool Mapping, Pydantic Output
      Schemas (`MarketAnalysisOutput`), and the `run_analysis()` return-value section.
- [x] 9.4 Confirm no changes to `prospectai-backend` or `prospectai-web` are required by
      this change (per design.md's Migration Plan); note the future need for the backend
      to catch `BoundsViolationError` as a separate, later change. Confirmed:
      `prospectai-backend/app.py` already wraps `ProspectAIFlow().run_analysis(...)` in a
      generic `except Exception`, so `BoundsViolationError` is caught safely today
      without any backend change — a more specific/user-friendly handling of it is a
      nice-to-have for a future backend release, not a blocker for this one.
