## ADDED Requirements

### Requirement: Task descriptions omit agent persona openers
Task `description` strings SHALL NOT begin with "You are the X Agent" or any equivalent persona statement. Agent identity is provided by the `role` and `backstory` fields.

#### Scenario: No persona opener in any task description
- **WHEN** any task description in tasks.yaml is read
- **THEN** it does not begin with "You are" and does not reference the agent's pipeline role in the opening sentence

### Requirement: Output schema communicated as field-type annotations
Task descriptions that currently embed full JSON payload examples with realistic numeric values SHALL replace those examples with compact field-type annotations listing each key and its type.

#### Scenario: No multi-line JSON example blocks in task descriptions
- **WHEN** any task description is read
- **THEN** it contains no JSON block with example numeric values (e.g., `"pe_ratio": 65.2`) — only field names and type annotations

### Requirement: market_analysis rationale length capped at 80–120 words
The `market_analysis` task description SHALL specify that each candidate stock rationale is 80–120 words.

#### Scenario: Rationale word-count guidance is within the reduced bound
- **WHEN** the market_analysis task description specifies a per-stock rationale length
- **THEN** the upper bound is ≤ 120 words

### Requirement: draft_strategy action-selection expressed as a decision table
Action-selection logic in draft_strategy STEP 3 SHALL be expressed as a compact condition → action table, one rule per line, occupying ≤ 20 lines total.

#### Scenario: Action rules fit within line budget
- **WHEN** the draft_strategy action-selection section is read
- **THEN** it occupies no more than 20 lines

### Requirement: critique_review issue-type entries are one line each
Each issue type in the critique_review adversarial checklist SHALL occupy a single line in the format: `TYPE_NAME — condition (SEVERITY)`.

#### Scenario: Issue catalog entries are single-line
- **WHEN** any issue-type entry in the critique_review checklist is read
- **THEN** it fits on a single line with no line continuation

### Requirement: Critic preface removed from draft_strategy
The `draft_strategy` task description SHALL NOT contain a sentence noting that output will be reviewed by a Critic Agent.

#### Scenario: Critic preface absent
- **WHEN** the draft_strategy task description is read
- **THEN** it contains no reference to the Critic reviewing the output
