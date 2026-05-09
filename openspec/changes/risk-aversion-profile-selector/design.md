## Context

ProspectAI is a three-repo system: the `prospectai` PyPI module (pipeline logic), `prospectai-backend` (Modal/FastAPI SSE server), and `prospectai-web` (Cloudflare Pages SPA). Today every pipeline run uses the same hardcoded allocation caps (LONG-BUY 40%, SCALED-ENTRY 20%, WAIT-FOR-ENTRY 15%) and fixed stop-loss/take-profit formulas (3% stop, R/R 2.0). Users with different risk tolerances get the same output regardless.

The goal is to add a `risk_profile` parameter (`"conservative"` | `"aggressive"`) that flows from the UI trigger through the backend into the pipeline, where it parametrizes the deterministic math in `PortfolioAllocatorTool` and provides qualitative context to the LLM agents.

## Goals / Non-Goals

**Goals:**
- Introduce `risk_profile` as a first-class pipeline input available to all three strategic phases (Draft Strategist, Critic, Final Strategist)
- Harden `PortfolioAllocatorTool` with per-profile allocation caps and trade-setup formula constants — all math stays deterministic
- Let LLM agents use `risk_profile` for qualitative decisions only: action label preference, narrative tone, allocation concentration
- Expose `risk_profile` on the backend SSE endpoint and track its usage in analytics
- Surface a 2-button selector in the web UI before the pipeline trigger

**Non-Goals:**
- Dynamic or per-ticker risk profiles — one profile applies to the whole run
- The LLM computing or overriding the numeric bounds; it receives them as read-only context
- A third profile or custom numeric overrides in this change
- Changing the `MarketAnalystAgent` or `TechnicalAnalystAgent` behavior — profile affects only the strategic phases

## Decisions

### D1: `risk_profile` enters as a top-level key in `run_analysis()` input dict

`run_analysis({"sector": ..., "risk_profile": "conservative"})` — same pattern as `sector`. Stored in `ProspectAIFlowState` alongside the sector and propagated via task rendering (`$risk_profile` template variable) and explicit tool input.

**Alternative considered:** pipeline-level env var. Rejected — env vars are process-scoped, which makes parallel runs impossible and unit testing awkward.

### D2: Profile constants defined once in `PortfolioAllocatorTool` as a lookup table

```python
PROFILE_BOUNDS = {
    "conservative": {
        "max_alloc_pct":    15.0,
        "stop_multiplier":  0.97,   # 3% stop
        "rr_ratio":         2.5,
    },
    "aggressive": {
        "max_alloc_pct":    30.0,
        "stop_multiplier":  0.95,   # 5% stop
        "rr_ratio":         1.5,
    },
}
```

`max_alloc_pct` replaces the per-action caps as a single per-position ceiling (conservative: 15%, aggressive: 30%). The SCALED-ENTRY and WAIT-FOR-ENTRY caps from the current design were artifacts of the fixed-formula world; with profile-based bounds they become the profile ceiling.

`stop_multiplier` and `rr_ratio` replace the hardcoded `0.97` and `× 2` constants in `_trade_setup()` and `_trade_setup_immediate()`.

**Alternative considered:** separate constants per action type per profile. Rejected — doubles the table size with no meaningful difference; the profile already encodes the risk posture.

### D3: `risk_profile` is passed inside `stocks_json` as a top-level key

```json
{"risk_profile": "conservative", "stocks": [...]}
```

This keeps `PortfolioAllocatorTool._run()` as a single-argument method (required by CrewAI's `BaseTool` contract) while avoiding global state. The tool parses it from the JSON payload.

**Alternative considered:** second `_run` argument. Rejected — CrewAI's tool invocation model passes a single string; multi-arg signatures are brittle.

### D4: Critic validates stop and R/R bounds relative to the profile

The Critic task prompt receives `$risk_profile` and the corresponding bounds in plain text. It emits a `CRITICAL` critique when a `trade_setup` violates the profile: a stop > 6% on conservative, or R/R < 2.5 on conservative, or R/R < 1.5 on aggressive. Since `PortfolioAllocatorTool` is deterministic, these critiques should be rare — but they catch cases where the Final Strategist re-calls the tool with stale inputs.

### D5: Analytics tracks `risk_profile` as flat keys alongside sector counts

`analytics_store[f"risk_profile:{risk_profile}"]` — a flat key in the existing Modal Dict. This avoids nested-dict mutation races on the Modal Dict and keeps the existing sector keys unchanged. The `/api/analytics` response gains a `by_risk_profile` field.

## Risks / Trade-offs

- **Version coupling** → `InvestorStrategicOutput` gains a required `risk_profile` field. Any backend pinning the old PyPI version will break at schema validation. Mitigation: coordinate PyPI publish, Modal redeploy, and web deploy as a single release train; bump the minor version.
- **Default coercion** → if an unknown `risk_profile` value reaches `PortfolioAllocatorTool`, it must not silently use wrong bounds. Mitigation: validate on entry and raise `ValueError` early; backend defaults to `"conservative"` on missing param.
- **Critic scope creep** → adding profile-relative validation to the Critic task prompt risks making it more verbose and slower. Mitigation: add a compact bounds table as a single paragraph, not a multi-section block.

## Migration Plan

1. Publish new `prospectai` version (minor bump) with schema + tool changes.
2. Deploy updated `prospectai-backend` pinning the new version — `/api/analyze` accepts `risk_profile` query param with default `"conservative"`.
3. Deploy updated `prospectai-web` with the UI toggle.

Rollback: revert the Modal backend to the previous version tag; old web UI always sends `risk_profile=conservative` (the default), so no state is lost.

## Open Questions

- Should `risk_profile` be included in the SSE `pipeline_done` event payload so the frontend can label the rendered report? (Lean: yes, trivial to add.)
- Should the analytics `/api/analytics` response include `by_risk_profile` in the same endpoint or a separate route? (Lean: same endpoint, additive field.)
