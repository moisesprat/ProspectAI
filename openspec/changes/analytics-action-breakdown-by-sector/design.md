## Context

`analytics_store` is a Modal Dict (key-value, string → int) used for flat counters. Currently it holds two namespaces:
- `{sector}` → run count (e.g., `"Technology" → 42`)
- `"risk_profile:{profile}"` → run count per profile

`_persist_run_results` in `app.py` populates these counters after each successful pipeline run. `GET /api/analytics` reads and formats them.

Position-level data (action types per run) already exists in `result["positions"]` immediately after the pipeline completes, but is discarded for analytics purposes — only LONG-BUY positions are persisted to `long_buy_store`.

## Goals / Non-Goals

**Goals:**
- Count how many times each action type (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID) has been recommended per sector, across all historical runs.
- Expose per-sector action counts and percentage share via `GET /api/analytics`.
- Require no schema or pipeline changes — capture data purely from the existing `result["positions"]` structure.

**Non-Goals:**
- Per-run breakdown (we aggregate across runs, not per run).
- Tracking action types by risk profile (out of scope for this change).
- Backfilling historical runs (counters start from zero; past runs are not reconstructed).

## Decisions

### Key pattern: `action:{sector}:{action_type}` in `analytics_store`

Adding a third namespace to the flat store keeps everything in one Modal Dict with no schema migration. Alternatives considered:
- **Nested JSON blob per sector**: Would require read-modify-write with a lock, which is not atomic in Modal Dict. Flat counters are atomic increment-only.
- **Separate Modal Dict**: No benefit over the third namespace and adds a new persistent resource.

### Percentage computed at read time, not write time

`GET /api/analytics` derives percentages from stored counts on every request. This means the display is always consistent with the underlying counts. Alternative of storing pre-computed percentages would go stale on partial writes and add write-time complexity.

### `_persist_run_results` iterates all positions (not just LONG-BUY)

The existing filter `if pos.get("action") != "LONG-BUY": continue` is only in the `long_buy_store` path. The new action-count loop is independent and covers all four action types.

## Risks / Trade-offs

- **Modal Dict eventual consistency**: Concurrent runs writing to the same `action:{sector}:{action_type}` key could race. Risk is low (runs are infrequent) and Modal Dict increment is best-effort; slight undercounting is acceptable for analytics.  → Mitigation: wrap in `try/except` like existing counters.
- **Unbounded action type values**: If a future pipeline version introduces a new action string, it will appear in the breakdown automatically. This is desirable but worth noting.  → Mitigation: none needed; open enum is correct behaviour.
- **No backfill**: Historical runs before this deploy show zero action counts. The sector run total will be higher than the sum of action counts for those sectors.  → Mitigation: document in API response (`action_breakdown` counts only post-deploy recommendations).

## Migration Plan

1. Deploy updated `app.py` to Modal — new keys start accumulating from first run post-deploy.
2. No rollback needed: removing the new keys has no effect on existing counters; old analytics consumers only read `by_sector` and `by_risk_profile`.
