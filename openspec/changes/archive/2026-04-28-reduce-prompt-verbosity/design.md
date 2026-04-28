## Context

Every CrewAI task prompt is assembled from three sources: the agent's `role` + `goal` + `backstory` (from agents.yaml) and the task's `description` + `expected_output` (from tasks.yaml). All five strings are concatenated and sent to the LLM. Currently the backstories contain full procedural workflows that are also spelled out step-by-step in the task descriptions. The `critic` and `investor_strategic` backstories alone are 70–80 lines each, duplicating the same rule sets that appear in `critique_review` and `draft_strategy`. The result is that each run sends the same behavioral instructions twice.

The guiding principle for this refactor: **backstories define identity and invariant principles; task descriptions define the run-time procedure.** An agent's identity (who it is, what it never does) should stay in the backstory. The workflow (what it does in this specific task) belongs in the task description.

## Goals / Non-Goals

**Goals:**
- Reduce per-agent prompt token count by ~40–60% compared to current files
- Establish clear ownership: backstory = identity/principles, task = procedure/output format
- Fix the stale `interpret_technical_indicators` reference in `technical_analyst` backstory
- Maintain full behavioral parity across all 6 pipeline stages

**Non-Goals:**
- Changing model selection, temperature, max_tokens, or any non-text agent settings
- Modifying Python code, Pydantic schemas, or tool implementations
- Changing `expected_output` fields (already concise)
- Touching anything outside agents.yaml and tasks.yaml

## Decisions

**Backstory content = identity + invariant principles only**
Backstories are sent on every task for that agent. They should contain:
- Who the agent is in one sentence (its mental model of itself)
- What it never does (data integrity rules, action constraints)
- Key output contract reminders (e.g., "output only the JSON dict")
Backstories should NOT contain: numbered workflow steps, tool call examples, issue-type catalogs, threshold values, or allocation cap tables — those belong in the task description that runs only once.

**Decision table over prose for action-selection rules**
The `draft_strategy` STEP 3 currently uses 45 lines of overlapping prose to describe 8 conditions. A compact decision table (condition → action, one line each) is equivalent and readable by the LLM. Threshold values (RSI > 70, gap ≥ 5%) are preserved; explanatory rationale is removed.

**One-line issue catalog in critique_review**
The critic's failure-mode catalog has 20 entries, each occupying 3–5 lines in tasks.yaml AND 3–5 lines in the backstory. The catalog is preserved in tasks.yaml only, at one line per entry: `TYPE_NAME — condition (SEVERITY)`. The backstory retains the adversarial principle but not the enumerated list.

**Field-type annotations over JSON examples**
Full JSON payload examples (e.g., the 25-field NVDA block in draft_strategy) are replaced with compact field-type annotations:
```
positions[]: ticker(str) action(str) composite_score(float) allocation_pct(float)
             current_price(float|null) trade_setup(obj|null) scaled_entry_setups(list|null)
             rationale(str) monitoring_triggers(str[]) review_frequency(str)
```
LLMs produce correctly structured output from field-list annotations; full examples with realistic numbers add no instruction value and inflate the prompt significantly.

**Fix stale tool reference in technical_analyst**
The backstory references `interpret_technical_indicators` per-ticker. That tool was removed and replaced with a batch-capable `calculate_technical_indicators` that returns interpretation data inline. The backstory must be corrected to reference only the batch tool.

## Risks / Trade-offs

[Risk] Removing workflow steps from backstories causes agents to miss multi-step tool orchestration sequences →
Mitigation: Workflow steps are still present in task descriptions. Backstories were never the primary instruction source — task descriptions are. The change does not remove any workflow step; it removes the second copy.

[Risk] Condensed critic checklist causes LLM to miss edge cases →
Mitigation: All 20 issue types are preserved in tasks.yaml. Only the English prose elaboration is stripped. The issue type name is already self-describing (OVERBOUGHT_IGNORED, WAIT_ENTRY_ZERO_ALLOC, etc.). The Pydantic schema provides a hard backstop.

[Risk] Field-type annotations cause wrong field name or missing field in output →
Mitigation: `expected_output` descriptions remain intact as a secondary signal. Pydantic schemas enforce structure at parse time and fail fast with clear errors.

[Risk] Reduced `market_analysis` rationale (80–120 words) loses audit detail →
Mitigation: 80–120 words (~500 characters) is sufficient to capture RSI, momentum_score, sentiment, and valuation_grade in one sentence each. The rationale is for human audit — it is not consumed by downstream agents.

## Migration Plan

1. Edit agents.yaml (all 5 backstories)
2. Edit tasks.yaml (all 6 task descriptions)
3. Run unit tests: `python -m pytest tests/test_schemas.py -q`
4. Run a live pipeline: `python main.py --sector Technology` — confirm all 6 tasks produce valid Pydantic output
5. Rollback: both files are in git; `git checkout config/agents.yaml config/tasks.yaml` reverts instantly
