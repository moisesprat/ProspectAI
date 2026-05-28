## Why

Users have different risk tolerances, but the pipeline today always constructs portfolios using the same allocation bounds and stop-loss distances. Adding a `risk_profile` parameter lets users choose between a conservative posture (tighter stops, smaller positions, preferring entries with confirmation) and an aggressive posture (wider targets, concentrated bets, preferring immediate execution) — surfaced as a simple 2-button selector in the UI before triggering a run.

## What Changes

- `PortfolioAllocatorTool` gains a `risk_profile` input (`"conservative"` | `"aggressive"`) and applies hardcoded per-profile bounds for max allocation, stop-loss distance, R/R ratio, and take-profit distance
- `InvestorStrategicOutput` and `CriticOutput` schemas gain a `risk_profile` field so the profile is propagated through and validated at each phase
- Draft Strategist, Critic, and Final Strategist task prompts receive `$risk_profile` as a template variable to guide qualitative decisions (action labels, narrative tone, concentration preference)
- The Critic validates findings relative to the profile — a stop loss valid for aggressive is flagged as too wide for conservative
- The Final Strategist resolves Critic directives while staying within profile bounds; it cannot drift outside the profile
- `prospectai-backend` `/api/analyze` endpoint accepts `risk_profile` as a query parameter (default: `conservative`) and logs it to `analytics_store`
- `prospectai-web` shows a Conservative / Aggressive toggle before the pipeline trigger and passes the value to the backend

## Capabilities

### New Capabilities
- `risk-profile-selector`: User-selectable risk profile (`conservative` / `aggressive`) that parametrizes portfolio construction bounds and guides LLM qualitative reasoning throughout the pipeline

### Modified Capabilities
- `portfolio-allocator-allocation`: Allocation bounds are now profile-dependent (max per-position 15% conservative / 30% aggressive)
- `portfolio-allocator-trade-setups`: Stop-loss and take-profit distances are now profile-dependent (stop 6%/15%, take-profit 12%/25%, R/R 2.5/1.5)

## Impact

- **prospectai (PyPI module)**: `schemas/agent_outputs.py`, `utils/portfolio_allocator_tool.py`, `config/tasks.yaml`, `prospect_ai_flow.py` (pass `risk_profile` into tool calls and task rendering)
- **prospectai-backend**: `serve.py` — new `risk_profile` query param on `/api/analyze`, analytics logging
- **prospectai-web**: `index.html` / `app.js` — UI toggle, pass value on pipeline trigger
- **Version coupling**: breaking change to `run_analysis()` input shape and `InvestorStrategicOutput` schema; backend must redeploy after PyPI publish
