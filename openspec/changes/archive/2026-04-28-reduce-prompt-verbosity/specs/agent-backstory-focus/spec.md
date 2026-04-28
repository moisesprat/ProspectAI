## ADDED Requirements

### Requirement: Backstories contain identity and principles only
Agent backstories in agents.yaml SHALL contain only: the agent's identity (who it is, its operating mindset), invariant data-integrity principles (what it never does), and its output contract (format constraint reminders). Backstories SHALL NOT contain: numbered workflow steps, tool call syntax, issue-type catalogs, threshold values, or allocation cap tables.

#### Scenario: No numbered workflow steps in any backstory
- **WHEN** any agent backstory in agents.yaml is read
- **THEN** it contains no numbered list of the form "1. Read context ... 2. Call tool ..." describing the task execution sequence

#### Scenario: No failure-mode catalog in critic backstory
- **WHEN** the critic backstory is read
- **THEN** it does not enumerate the failure-mode issue types (OVERBOUGHT_IGNORED, ENTRY_ZONE_VIOLATED, etc.)

### Requirement: technical_analyst backstory references only the batch tool
The `technical_analyst` backstory SHALL reference `calculate_technical_indicators` as the sole technical tool. Any reference to `interpret_technical_indicators` (removed tool) SHALL be absent.

#### Scenario: Stale tool reference removed
- **WHEN** the technical_analyst backstory is read
- **THEN** the string "interpret_technical_indicators" does not appear

### Requirement: investor_strategic backstory omits PORTFOLIO CONSTRUCTION RULES and CRITICAL RULES sections
The `investor_strategic` backstory SHALL NOT contain the "PORTFOLIO CONSTRUCTION RULES:" or "CRITICAL RULES:" block headers or the detailed sub-rules under them, as these are fully covered by the draft_strategy and final_strategy task descriptions.

#### Scenario: Rule blocks absent from investor_strategic backstory
- **WHEN** the investor_strategic backstory is read
- **THEN** it contains neither "PORTFOLIO CONSTRUCTION RULES" nor "CRITICAL RULES" as section headers

### Requirement: Backstory length is proportional to role complexity
After trimming, no agent backstory SHALL exceed 12 lines. Complex reasoning agents (investor_strategic, critic) MAY use up to 12 lines; data-gathering agents (market_analyst, technical_analyst, fundamental_analyst) SHALL use no more than 8 lines.

#### Scenario: Backstory line count within budget
- **WHEN** any backstory in agents.yaml is read and blank lines are excluded
- **THEN** it contains ≤ 12 non-blank lines
