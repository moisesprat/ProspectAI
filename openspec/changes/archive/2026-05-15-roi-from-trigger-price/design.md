## Context

The `long-buy-history` Modal Dict contains 15 entries today; 6 lack `trigger_price` (older runs predating the trigger contract). The endpoint currently computes ROI as `(current - entry_zone_mid) / entry_zone_mid * 100` and includes any record with positive midpoint-ROI. This produces "wins" for records the system never explicitly told a user to buy at a specific price.

## Goals / Non-Goals

**Goals:**
- ROI reflects what a user following ProspectAI's trigger signal would actually have earned.
- Only records with an actionable buy basis (`trigger_price`) appear in the wins feed.

**Non-Goals:**
- Backfilling `trigger_price` onto older records.
- Removing older records from the Modal Dict (they remain stored but are filtered out at read time).
- Changing the UI — the existing compact card layout handles both cases correctly.

## Decisions

### D1 — Use `trigger_price` as the ROI basis, not the entry zone midpoint

**Decision:** ROI is `(current_price - trigger_price) / trigger_price * 100`.

**Rationale:** `trigger_price` is the single price emitted by `PortfolioAllocatorTool` as the suggested entry. The midpoint is a derived value; the trigger is the contract. Anchoring ROI to the trigger means the displayed % equals the % a user following the signal would actually have realized.

**Alternative considered:** Continue using the midpoint and add a separate "trigger ROI" field. Rejected — duplicates information and forces the UI to decide which to show; the trigger ROI is the only one that maps to a real action.

### D2 — Exclude records without `trigger_price`

**Decision:** Records where `trigger_price` is null or missing are filtered out before ROI computation and not returned.

**Rationale:** Without a trigger, there is no defined buy basis. Falling back to the midpoint for these records would mix two ROI semantics in one list and silently re-introduce the very problem this change fixes.

**Alternative considered:** Fall back to `entry_zone_high` for records without `trigger_price`. Rejected — pessimistic but still synthetic; users would not know which records were "real" and which were inferred.

## Risks / Trade-offs

- Wins list will shrink in the short term (older records drop out). Mitigation: the 30-day window naturally rolls older entries out; new runs always emit `trigger_price`, so the feed refills on its own.
- A record where `trigger_price > entry_zone_high` (the trigger sat above the zone, as observed for AMD) now computes ROI against that higher basis, potentially flipping a "win" to a "loss" or vice versa. This is intended — the displayed ROI now matches the actual signal.

## Migration Plan

1. Deploy backend (`modal deploy serve.py`). Purely a read-time filter + formula change; no data migration.
2. No frontend deploy required.
3. Rollback: revert the backend commit and redeploy. Storage is untouched, so rollback is single-step.
