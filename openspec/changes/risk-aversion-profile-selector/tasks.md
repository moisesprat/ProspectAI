## 1. prospectai — PortfolioAllocatorTool

- [x] 1.1 Add `PROFILE_BOUNDS` lookup table in `portfolio_allocator_tool.py` with `conservative` and `aggressive` entries (`max_alloc_pct`, `stop_multiplier`, `rr_ratio`)
- [x] 1.2 Update `_trade_setup()` to accept `stop_multiplier` and `rr_ratio` parameters and apply them in the stop/TP formulas
- [x] 1.3 Update `_trade_setup_immediate()` to accept `stop_multiplier` and `rr_ratio` parameters and apply them
- [x] 1.4 Update `PortfolioAllocatorTool._run()` to parse `risk_profile` from the top-level JSON key (default `"conservative"`, raise `ValueError` on unrecognised value)
- [x] 1.5 Replace the per-action hardcoded caps (`MAX_LONG_BUY_ALLOC`, etc.) with a single `max_alloc_pct` from the profile bounds applied uniformly to all deployed positions
- [x] 1.6 Pass `stop_multiplier` and `rr_ratio` from the resolved profile into all `_trade_setup()` and `_trade_setup_immediate()` calls
- [x] 1.7 Update the `description` docstring on `PortfolioAllocatorTool` to document the `risk_profile` key and per-profile bounds table

## 2. prospectai — Schemas

- [x] 2.1 Add `risk_profile: Literal["conservative", "aggressive"]` field to `InvestorStrategicOutput` in `schemas/agent_outputs.py`
- [x] 2.2 Add `risk_profile: Literal["conservative", "aggressive"]` field to `CriticOutput` in `schemas/agent_outputs.py`

## 3. prospectai — Flow state and task rendering

- [x] 3.1 Add `risk_profile: str = "conservative"` to `ProspectAIFlowState` in `prospect_ai_flow.py`
- [x] 3.2 Read `risk_profile` from the `run_analysis()` input dict and validate it (`"conservative"` | `"aggressive"`) before starting the pipeline; raise `ValueError` on invalid value
- [x] 3.3 Store validated `risk_profile` in `ProspectAIFlowState`
- [x] 3.4 Pass `risk_profile=self.state.risk_profile` to `TaskConfigLoader.render()` calls for Draft Strategist, Critic, and Final Strategist tasks
- [x] 3.5 Pass `risk_profile` into the `stocks_json` payload when calling `PortfolioAllocatorTool` in phases 4 and 6

## 4. prospectai — Task prompts

- [x] 4.1 Add `$risk_profile` template variable to the Draft Strategist task in `config/tasks.yaml`; include a one-paragraph block explaining profile-specific action label preference and allocation concentration guidance
- [x] 4.2 Add `$risk_profile` template variable to the Critic task in `config/tasks.yaml`; include a compact bounds table (stop %, R/R, max alloc) and instruct the Critic to flag violations as `CRITICAL`
- [x] 4.3 Add `$risk_profile` template variable to the Final Strategist task in `config/tasks.yaml`; instruct it to stay within profile bounds and not drift toward the other profile when resolving Critic directives

## 5. prospectai — Tests

- [x] 5.1 Add unit tests for `PortfolioAllocatorTool` covering conservative profile bounds (max_alloc 15%, stop 3%, R/R 2.5)
- [x] 5.2 Add unit tests covering aggressive profile bounds (max_alloc 30%, stop 5%, R/R 1.5)
- [x] 5.3 Add a test asserting `ValueError` is raised for an unknown `risk_profile` value
- [x] 5.4 Add a test asserting `InvestorStrategicOutput` and `CriticOutput` schema validation passes with the new `risk_profile` field present

## 6. prospectai-backend — Endpoint and analytics

- [x] 6.1 Add `risk_profile: str = "conservative"` query parameter to the `/api/analyze` FastAPI endpoint in `serve.py`
- [x] 6.2 Forward `risk_profile` to `run_analysis()` as `{"sector": sector, "risk_profile": risk_profile}`
- [x] 6.3 After a successful pipeline run, increment `analytics_store[f"risk_profile:{risk_profile}"]`
- [x] 6.4 Update `get_analytics()` to read and return a `by_risk_profile` dict from `analytics_store` (keys matching `"risk_profile:*"`)

## 7. prospectai-web — UI toggle

- [x] 7.1 Add a 2-button Conservative / Aggressive selector to `index.html` (or the relevant template) with Conservative pre-selected
- [x] 7.2 Wire the selector state so the selected value is appended as `&risk_profile=<value>` to the SSE request URL when the pipeline is triggered
- [x] 7.3 Visually distinguish the active/inactive button state with CSS (active = filled/highlighted, inactive = outlined)

## 8. Release

- [x] 8.1 Bump `prospectai` version (minor) in `VERSION.md` and `pyproject.toml`
- [ ] 8.2 Publish updated `prospectai` package to PyPI
- [ ] 8.3 Update `prospectai-backend` `serve.py` to pin the new version, then redeploy on Modal
- [ ] 8.4 Deploy updated `prospectai-web` to Cloudflare Pages
