## ADDED Requirements

### Requirement: Final-output allocation is Flow-authoritative, not LLM-authoritative
The Flow, not the LLM, SHALL determine when `PortfolioAllocatorTool` is invoked to price
the final published output, and SHALL treat the tool's result as authoritative — any
allocation, trade-setup, or bucket values written by the LLM in its raw text output SHALL
be discarded and replaced by the tool's result before publication.

#### Scenario: LLM-written allocation values are discarded
- **WHEN** the Final Strategist's raw output contains an `allocation_pct` value that was
  not produced by a tool call
- **THEN** the value the Flow publishes is the one computed by the Flow's own
  `allocate_portfolio` invocation, not the LLM-written value
