## 1. agents.yaml — market_analyst backstory

- [x] 1.1 Remove workflow steps 1–6 from market_analyst backstory
- [x] 1.2 Remove the downstream pipeline warning ("The Technical Analyst downstream reads your candidate_stocks list...")
- [x] 1.3 Verify backstory retains: temporal-awareness identity, "never invent tickers" principle, output format reminder (≤ 8 non-blank lines)

## 2. agents.yaml — technical_analyst backstory

- [x] 2.1 Remove workflow steps 1–4 from technical_analyst backstory
- [x] 2.2 Remove the downstream pipeline warning ("The Fundamental Analyst and Strategic Agent read your stock_analyses list")
- [x] 2.3 Fix stale reference: remove all mentions of `interpret_technical_indicators`
- [x] 2.4 Verify backstory retains: "works exclusively with tool-derived data" identity, "never compute signals manually" principle (≤ 8 non-blank lines)

## 3. agents.yaml — fundamental_analyst backstory

- [x] 3.1 Remove workflow steps 1–5 from fundamental_analyst backstory
- [x] 3.2 Verify backstory retains: "never guess financial data" principle, "never apply grading formulas manually", "exactly TWO tool calls" constraint (≤ 8 non-blank lines)

## 4. agents.yaml — investor_strategic backstory

- [x] 4.1 Remove workflow steps 1–6 from investor_strategic backstory
- [x] 4.2 Remove the "PORTFOLIO CONSTRUCTION RULES:" block and all sub-rules under it
- [x] 4.3 Remove the "CRITICAL RULES:" block and all sub-rules under it
- [x] 4.4 Verify backstory retains: identity ("final stage of automated pipeline, strict schema"), action-type definitions (LONG-BUY/SCALED-ENTRY/WAIT-FOR-ENTRY/MONITOR/AVOID and their key distinction), output contract ("output ONLY the JSON dict") (≤ 12 non-blank lines)

## 5. agents.yaml — critic backstory

- [x] 5.1 Remove the full failure-mode checklist (OVERBOUGHT_IGNORED through COMPOSITE_SCORE_MISMATCH) from critic backstory
- [x] 5.2 Remove the "Portfolio-level checks:" block from critic backstory
- [x] 5.3 Remove the "Write revision_directives as exact, actionable instructions" block from critic backstory
- [x] 5.4 Verify backstory retains: adversarial identity ("most skeptical analyst"), "every claim must be traceable to a specific number" principle, "do not praise" constraint (≤ 12 non-blank lines)

## 6. tasks.yaml — market_analysis

- [x] 6.1 Remove agent persona opener ("You are the first agent in the ProspectAI pipeline.")
- [x] 6.2 Reduce rationale word-count guidance from 200–400 to 80–120 words per stock
- [x] 6.3 Trim STEP 3 rationale coverage from 5 points (a–e) to 3 key points
- [x] 6.4 Replace full JSON output example (STEP 4) with compact field-type annotation list

## 7. tasks.yaml — technical_analysis

- [x] 7.1 Remove agent persona opener ("You are the Technical Analyst in the ProspectAI pipeline.")
- [x] 7.2 Replace full JSON output example (STEP 4) with compact field-type annotation list
- [x] 7.3 Trim STEP 3 key_signals examples to a short list without prose explanation

## 8. tasks.yaml — fundamental_analysis

- [x] 8.1 Remove agent persona opener ("You are the Fundamental Analyst in the ProspectAI pipeline.")
- [x] 8.2 Replace full JSON output example (STEP 4, including the PLUG unknown-ticker block) with compact field-type annotations

## 9. tasks.yaml — draft_strategy

- [x] 9.1 Remove agent persona opener ("You are the Draft Strategist in the ProspectAI pipeline.")
- [x] 9.2 Remove the "NOTE: Your output will be reviewed by a Critic Agent" sentence
- [x] 9.3 Condense STEP 3 action-selection rules into a compact decision table (≤ 20 lines)
- [x] 9.4 Replace full JSON output example (STEP 7) with compact field-type annotation list

## 10. tasks.yaml — critique_review

- [x] 10.1 Remove agent persona opener ("You are the Critic Agent in the ProspectAI pipeline.")
- [x] 10.2 Condense each issue-type entry in STEP 2 to a single line: `TYPE_NAME — condition (SEVERITY)`
- [x] 10.3 Replace full JSON output example (STEP 5) with compact field-type annotation list

## 11. tasks.yaml — final_strategy

- [x] 11.1 Remove agent persona opener ("You are the Final Strategist in the ProspectAI pipeline.")
- [x] 11.2 Replace full JSON output example (STEP 4) with compact field-type annotation list
- [x] 11.3 Trim CASE A/CASE B field listings — keep the "copy verbatim" rule but remove duplicate field enumeration

## 12. Validation

- [x] 12.1 Run `python -m pytest tests/test_schemas.py -q` — all tests pass
- [ ] 12.2 Run a live pipeline (`python main.py --sector Technology`) — all 6 tasks produce valid Pydantic output
