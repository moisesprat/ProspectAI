## Context

The Recent Wins enrichment shipped with three new card rows (recommendation label sentence, separate trigger price row, separate current price row). On a viewport with five horizontally-stacked cards, the doubled height pushed sector selection below the fold. We compacted the live UI to a 4-row layout that preserves all information; this change reconciles the spec text to match.

## Goals / Non-Goals

**Goals:**
- Bring `long-buy-wins-ui` spec in line with deployed UI (commit `fcdbc77`).
- Preserve every piece of information from the prior spec (action label, recommended date, current price, optional trigger price, ROI).

**Non-Goals:**
- Any code changes — already deployed.
- Any API contract changes — backend response is unchanged.

## Decisions

### D1 — Encode LONG-BUY as a tag next to the ticker, not a full sentence

**Decision:** Replace "Recommended as LONG-BUY by ProspectAI · [date]" with a compact `LONG-BUY` tag pill placed inline with the ticker on row 1.

**Rationale:** The full sentence consumed a row and repeated information the section heading already implies (these cards are ProspectAI's own picks). A tag conveys the action label in a fraction of the space.

### D2 — Merge trigger and current price into one row with an arrow

**Decision:** Render the price row as `$trigger → $current`. When `trigger_price` is null, render only `$current` (no arrow, no placeholder).

**Rationale:** Two prices on one line read as "what we suggested → what it is now," which is the comparison users care about. Reads in one glance instead of scanning two labelled rows.

### D3 — Use relative-time only for the recommended date

**Decision:** The date when ProspectAI recommended the pick is shown via the existing relative-time string ("5d ago"), now placed inline with the sector on row 2.

**Rationale:** Relative time was already present in the prior layout. The absolute short date ("May 10") that the verbose layout added was redundant once the relative time is kept.

## Risks / Trade-offs

- Users who scanned the prior verbose label may find the `LONG-BUY` tag less explicit. Mitigation: the section heading "Recent picks performing well" already frames the cards as ProspectAI picks, so the tag is sufficient context.
- Absolute date is dropped in favour of relative time. Acceptable — relative time was the prior contract and the cards target last-30-day picks where "Nd ago" is precise enough.
