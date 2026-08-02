## REMOVED Requirements

### Requirement: draft_strategy action-selection expressed as a decision table
**Reason**: The fixed decision-table premise this requirement enforced (≤20 lines, one rule per line) no longer applies — `reasoning-action-selection` replaces the table with a reasoning framework that must weigh conflicting signals, which cannot be expressed as single-line condition→action rules.
**Migration**: See "draft_strategy reasoning framework has a word budget" below — the replacement economy constraint for the same prompt section.

## ADDED Requirements

### Requirement: draft_strategy reasoning framework has a word budget
The `draft_strategy` STEP 3 reasoning-framework block (replacing the removed decision table) SHALL occupy approximately 250–350 words, keeping prompt cost roughly comparable to the table it replaces while allowing room to state the reasoning approach, the two surviving hard invariants, and the requirement that the rationale name conflicting signals explicitly.

#### Scenario: Reasoning framework fits within the word budget
- **WHEN** the `draft_strategy` STEP 3 reasoning-framework text is word-counted
- **THEN** the count falls within approximately 250–350 words
