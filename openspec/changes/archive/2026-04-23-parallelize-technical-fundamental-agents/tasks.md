## 1. Refactor ProspectAICrew into a task/agent factory

- [x] 1.1 Add per-phase task builder methods to `ProspectAICrew`: `build_market_task()`, `build_technical_task(market_task)`, `build_fundamental_task(market_task)`, `build_draft_task(...)`, `build_critique_task(...)`, `build_final_task(...)`
- [x] 1.2 Add `DeprecationWarning` to `ProspectAICrew.__init__()` with message: "ProspectAICrew is deprecated; use ProspectAIFlow instead."
- [x] 1.3 Add `# DEPRECATED` docstring to `ProspectAICrew` class noting planned removal

## 2. Implement ProspectAIFlow

- [x] 2.1 Create `prospect_ai_flow.py` with `ProspectAIFlowState(BaseModel)` holding typed outputs for each phase (`market_output`, `technical_output`, `fundamental_output`, `draft_output`, `critique_output`, `final_output`)
- [x] 2.2 Implement `ProspectAIFlow(Flow[ProspectAIFlowState])` with `__init__` accepting `task_callback`, `step_callback`, and `progress_callback`
- [x] 2.3 Add `@start() market_analysis()` method: builds and kicks off Market Analysis mini-Crew, stores result in `self.state.market_output`, emits `progress_callback` with `task_index=0`
- [x] 2.4 Add `@listen(market_analysis) technical_analysis()` method: builds and kicks off Technical Analysis mini-Crew, stores result in `self.state.technical_output`, emits `progress_callback` with `task_index=1`
- [x] 2.5 Add `@listen(market_analysis) fundamental_analysis()` method: builds and kicks off Fundamental Analysis mini-Crew, stores result in `self.state.fundamental_output`, emits `progress_callback` with `task_index=2`
- [x] 2.6 Add `@listen(and_(technical_analysis, fundamental_analysis)) draft_strategy()` method: builds and kicks off Draft Strategy mini-Crew, stores result, emits `progress_callback` with `task_index=3`
- [x] 2.7 Add `@listen(draft_strategy) critique_review()` method: builds and kicks off Critic mini-Crew, stores result, emits `progress_callback` with `task_index=4`
- [x] 2.8 Add `@listen(critique_review) final_strategy()` method: builds and kicks off Final Strategy mini-Crew, stores result, emits `progress_callback` with `task_index=5`
- [x] 2.9 Add error guard in each `@listen` method: check `self.state` for an error field set by any prior phase and short-circuit with a raised exception before starting the next Crew
- [x] 2.10 Implement `run_analysis(market_criteria, progress_callback=None) -> dict` on `ProspectAIFlow`: clears yfinance cache, calls `self.kickoff()`, runs `_parse_result` and `validate_portfolio`, returns same dict shape as `ProspectAICrew.run_analysis()`

## 3. Update entry points

- [x] 3.1 Update `main.py`: replace `from prospect_ai_crew import ProspectAICrew` with `from prospect_ai_flow import ProspectAIFlow` and instantiate `ProspectAIFlow()` instead
- [x] 3.2 Update `../prospectai-backend/serve.py`: replace `ProspectAICrew` import with `ProspectAIFlow`; replace `agent_counter` auto-increment logic with explicit `task_index` from `progress_callback` events

## 4. Tests

- [x] 4.1 Update `tests/test_crew.py`: replace `ProspectAICrew` instantiation with `ProspectAIFlow`; verify that `run_analysis()` returns a dict with `pipeline_version`, `stock_recommendations`, and `portfolio_summary`
- [x] 4.2 Add a unit test asserting that instantiating `ProspectAICrew()` raises `DeprecationWarning`
- [x] 4.3 Add a smoke test that imports `ProspectAIFlow`, `Flow`, `listen`, `and_` from crewai to confirm the dependency is satisfied

## 5. Validation

- [x] 5.1 Run the full pipeline end-to-end (`python main.py --sector Technology`) and confirm Technical and Fundamental phases start concurrently (visible in verbose CrewAI logs)
- [x] 5.2 Confirm output schema is unchanged: `pipeline_version`, `stock_recommendations` (5 items), `portfolio_summary` all present
- [x] 5.3 Run `python -m pytest tests/` and confirm all tests pass
