## Context

`stats.js` runs two parallel fetches on load (`/api/analytics`, `/api/long-buy-history`). Currently the page renders placeholder dashes (`—`) immediately and replaces them when data arrives. The Activity tab renders sector coverage as a `<ul>` list and risk profile as a `<ul>` list. The Decisions tab calls `renderCharts()` which builds one donut per sector by iterating `action_breakdown`. The Performance tab renders all rows from the history response without any date or deduplication filtering.

The `prospectai_version` field is present on records in the Modal Dict but is not currently included in the `/api/long-buy-history` response.

## Goals / Non-Goals

**Goals:**
- Animated CSS skeleton loaders for cards, charts, and table while data is in-flight.
- Horizontal bar chart for sector coverage (CSS `width` driven by %-of-max), SVG donut for risk profile, both in the Activity tab.
- Single donut + sector `<select>` in the Decisions tab; dropdown includes "Overall" + every sector key from `action_breakdown`.
- Performance table: exclude entries ≤ 5 days old; deduplicate on (ticker, date, trigger_price); add stop-loss disclaimer banner; add `Version` column.
- Backend: add `prospectai_version` to `/api/long-buy-history` row shape.

**Non-Goals:**
- No server-side deduplication or date-filtering (done client-side to avoid API changes beyond the version field).
- No new charting library.
- No changes to `/api/long-buy-wins` (the "Recent Wins" widget on the main page).

## Decisions

### Decision 1: Skeleton loaders via CSS animation, not a library
Skeleton elements are `<div class="skeleton">` placeholders injected into each section's container before the fetch resolves. A CSS `@keyframes` pulse (opacity 0.4 → 0.8 → 0.4) runs on them. When data arrives, `renderX()` replaces the skeleton's parent innerHTML. This matches the project's no-library approach.

### Decision 2: Horizontal bar chart — CSS `width` percentage
Each sector bar's width = `(count / maxCount) * 100%`, set as an inline style. The bar is a `<div class="stat-bar-fill">` inside a `<div class="stat-bar-track">`. No canvas, no SVG. Sector name and count are text nodes in the same row.

### Decision 3: Risk profile — SVG donut (same as Decisions donuts)
Reuse the existing `renderDonut()` helper. Risk profile donut uses the same two-colour palette: Conservative → `#4a7c59` (green), Aggressive → `#e0a040` (amber). Rendered into a small SVG in the Activity card alongside a mini legend.

### Decision 4: Single donut + sector filter in Decisions tab
Replace the per-sector grid with one large donut (same size as the current "Overall" donut). Above it, a `<select>` with options: "Overall", then one entry per sector key from `action_breakdown` (sorted alphabetically). On change, re-call `renderDonut()` with the selected sector's counts or the aggregated overall counts. This fixes the missing-sectors issue: the dropdown is built from `Object.keys(action_breakdown)`, so every sector the backend returns is included regardless of having all four action types.

### Decision 5: Performance deduplication — client-side on (ticker, date, trigger_price)
"Date" is the UTC calendar date (YYYY-MM-DD) extracted from `recommended_at`. Deduplication keeps the entry with the latest `recommended_at` among duplicates. Applied before the 5-day filter so duplicates don't re-appear.

### Decision 6: 5-day exclusion window
`today` is computed as UTC midnight. Any entry with `recommended_at` ≥ `today - 5 days` is excluded from the table and from KPI card calculations (win rate, avg return, best/worst).

### Decision 7: `prospectai_version` — backend field addition
In `get_long_buy_history()`, add `"prospectai_version": r.get("prospectai_version")` to each history item dict. Redeploy needed. Frontend renders the value as-is; `null` displays as "—".

### Decision 8: Stop-loss disclaimer
A single `<p class="stats-disclaimer">` element rendered above the track record table, always visible (not conditional). Text: *"ROI figures assume the position was held to the current price. Stop-loss levels were not factored in — if the stop-loss price was hit, the actual outcome would differ."*

## Risks / Trade-offs

- **Skeleton flash**: if the API responds in < 200 ms (e.g., cached), users may see a brief skeleton flash. Acceptable — the skeleton improves the slow-path experience significantly.
- **5-day window is a hard cut**: an entry from exactly 5 days ago at 23:59 UTC is excluded; one from 5 days ago at 00:01 is also excluded. Using UTC calendar days keeps it deterministic.
- **Deduplication hides true prediction count**: users may notice fewer rows. The disclaimer banner and row count in the section subtitle will make this transparent.
