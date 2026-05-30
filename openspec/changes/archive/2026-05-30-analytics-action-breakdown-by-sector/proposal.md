## Why

The analytics API currently only counts how many times each sector has been analyzed — it has no visibility into what actions ProspectAI is recommending (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID). Without this, there's no way to tell whether the pipeline is systematically over-recommending caution or aggressively deploying capital across sectors.

## What Changes

- `_persist_run_results` in `app.py` now records per-position action counts into `analytics_store` using the key pattern `action:{sector}:{action_type}`.
- `GET /api/analytics` response gains a new `action_breakdown` field: a dict keyed by sector, each containing counts and percentage share for every action type seen in that sector.
- The `/prospectai-analytics` slash command output is updated to display the new breakdown.

## Capabilities

### New Capabilities
- `analytics-action-breakdown`: Track recommendation action type counts (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID) per sector and expose percentage breakdowns via the analytics API.

### Modified Capabilities
- (none — existing sector run counts and risk profile counts are unchanged)

## Impact

- **`../prospectai-backend/app.py`**: `_persist_run_results` writes additional keys; `get_analytics` reads and aggregates them.
- **`/prospectai-analytics` skill**: display layer picks up the new `action_breakdown` field.
- No schema changes to the ProspectAI pipeline itself; data is captured from the existing `result["positions"]` array.
- No breaking changes to the existing `/api/analytics` response shape — new field is additive.
