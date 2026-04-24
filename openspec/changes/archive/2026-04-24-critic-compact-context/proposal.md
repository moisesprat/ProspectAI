## Why

The Critic agent currently receives the same full multi-phase context as the Draft Strategist (market + technical + fundamental + draft), which causes it to re-derive upstream data rather than focus on reviewing the draft's reasoning quality. The Critic's job is adversarial review — not recalculation — and should receive the minimum data needed to verify claims: the draft output plus a compact per-ticker reference table of the raw values it checks against.

## What Changes

- Replace the Critic's current four-section context (market slim + technical slim + fundamental slim + draft slim) with two inputs:
  - **Draft output** — the full `_slim_draft()` JSON (positions, allocations, setups, rationale, triggers)
  - **Reference table** — a new compact per-ticker lookup built from typed state models containing only the fields the Critic's checklist actually references: `rsi`, `stochastic_status`, `entry_zone_status`, `average_sentiment`, `valuation_grade`, `financial_health`, `momentum_score`, `composite_score`
- Add a new `_critic_reference_table()` helper in `ProspectAIFlow` that builds the compact reference from the three typed state models (`market_output`, `technical_output`, `fundamental_output`)
- Remove the three existing slim helpers (`_slim_market_for_strategy`, `_slim_technical`, `_slim_fundamental`) from the Critic's context-building call in `critique_review()`

## Capabilities

### New Capabilities

- `critic-compact-context`: The Critic receives a structured per-ticker reference table instead of full upstream phase outputs, keeping its context focused on verification data only.

### Modified Capabilities

- `parallel-analysis-flow`: The `critique_review()` flow method's context-building changes — it no longer passes market/technical/fundamental slim outputs to the Critic.

## Impact

- `prospect_ai_flow.py` — new `_critic_reference_table()` helper; updated `critique_review()` context assembly
- `config/tasks.yaml` — the `critique_review` task description references upstream field names; may need updating to reflect the compact reference table format
- No changes to schemas, agents, or other tools
- No change to the public `run_analysis()` API
