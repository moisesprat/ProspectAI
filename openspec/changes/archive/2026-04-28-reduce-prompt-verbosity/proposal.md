## Why

Both `config/agents.yaml` and `config/tasks.yaml` are injected into every LLM prompt. Right now they carry the same information twice: backstories enumerate procedural workflows that are also described step-by-step in task descriptions, and task descriptions open with persona statements already covered by agent role/backstory. On every single run, the LLM receives 1 500–2 500 redundant tokens across the two files. The redundancy also creates a maintenance risk: if a rule changes in one file it must be hunted down and changed in the other.

The fix is a clear division of responsibility: backstories define WHO the agent is and its core operating principles; task descriptions define WHAT to do in this run and how to format the output. No content belongs in both.

This change supersedes the staged `slim-task-descriptions` change (tasks.yaml scope only). All tasks.yaml reductions from that change are included here together with the agents.yaml backstory slimming.

## What Changes

**agents.yaml — backstory scope reduction:**
- `market_analyst`: keep temporal-awareness identity and "never invent tickers" principle; remove steps 1–6 (procedural workflow → lives in tasks.yaml)
- `technical_analyst`: keep "works exclusively with tool-derived data" identity; remove workflow steps 1–4; fix stale `interpret_technical_indicators` reference (tool was replaced by batch `calculate_technical_indicators`)
- `fundamental_analyst`: keep "never guess financial data" principle; remove workflow steps 1–5
- `investor_strategic`: keep identity + action-type definitions + allocation-cap table; remove full 6-step workflow, PORTFOLIO CONSTRUCTION RULES section, CRITICAL RULES section (all already in tasks.yaml)
- `critic`: keep adversarial identity ("every claim must be traceable to a specific number"); remove the full 20-item failure-mode checklist and portfolio-level checks (already in tasks.yaml critique_review description)

**tasks.yaml — description scope reduction:**
- Remove agent persona openers from all 6 tasks ("You are the X Agent in the ProspectAI pipeline.")
- Replace full JSON payload examples with compact field-type annotations (field_name: type|null)
- Reduce `market_analysis` rationale word count from 200–400 to 80–120 words per stock
- Condense `draft_strategy` action-selection rules (STEP 3) into a compact decision table ≤ 20 lines
- Condense `critique_review` issue-type catalog to one line per issue type
- Remove "NOTE: Your output will be reviewed by a Critic Agent" from `draft_strategy`

## Capabilities

### New Capabilities
- `task-prompt-economy`: Task descriptions are lean instruction sets — no persona openers, no JSON payload examples, concise rationale guidance, condensed decision tables
- `agent-backstory-focus`: Backstories define agent identity and core principles only; procedural workflow steps and rule catalogs are not duplicated from tasks.yaml

### Modified Capabilities

## Impact

- `config/agents.yaml` — all 5 agent backstories modified; no structural YAML changes
- `config/tasks.yaml` — all 6 task descriptions modified; no structural YAML changes
- No Python, schema, or test changes
- Behavioral parity: all tool calls, output structures, validation rules, and edge-case handling preserved; only redundant prose is removed
