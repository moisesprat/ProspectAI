## Context

The Performance tab in `stats.html` already fetches `/api/long-buy-history` on page load and stores the full entry array in memory. Each entry carries a `sector` field. KPI cards and the table are rendered client-side from this array. The change is a pure frontend filter — no API or backend work is involved.

The existing flow:
1. `fetchLongBuyHistory()` → stores raw entries in `allHistory`.
2. `renderPerformanceTab()` calls `applyDataRules(allHistory)` (dedup + 5-day exclusion) → produces `filteredHistory`.
3. KPI cards and table render from `filteredHistory`.

## Goals / Non-Goals

**Goals:**
- Add a sector `<select>` dropdown above the KPI cards on the Performance tab.
- Default to "All Sectors" (current behaviour unchanged).
- On sector change, re-run `applyDataRules` on the sector-filtered subset and re-render KPI cards and table.
- Keep row-count subtitle in sync with the filtered count.

**Non-Goals:**
- Multi-select or combined-sector filtering.
- Persisting the selected sector across page reloads.
- Backend changes.
- Changes to the Decisions tab or Activity tab.

## Decisions

### Decision: Client-side filtering only, no new fetch
Sector data is already present in each history entry. Re-fetching per sector would add latency and complexity for zero benefit.

*Alternative considered*: query parameter on `/api/long-buy-history?sector=X`. Rejected — over-engineering; the full dataset is small (<1 000 rows expected).

### Decision: Dropdown options derived dynamically from the data
Populate the sector `<select>` by extracting unique `sector` values from `allHistory` (raw, before data-rule filtering), sorted alphabetically, with "All Sectors" prepended. This avoids hard-coding sector names and keeps the dropdown accurate even if new sectors are added to the backend.

*Alternative considered*: hard-coded list matching `RedditSentimentTool.SECTOR_TICKERS`. Rejected — creates a maintenance coupling between frontend and backend.

### Decision: Reuse existing `applyDataRules` + render pipeline
Rather than a second code path, filter `allHistory` to the chosen sector first, then pass the subset into the existing rules → render chain. KPI card logic is untouched; it just receives a smaller array.

### Decision: Place dropdown above KPI cards
Positioning the control above the cards makes it clear the selection governs everything below it (cards + table), matching the pattern used on the Decisions tab (sector dropdown above the donut).

## Risks / Trade-offs

- **Empty sector result** → KPI cards all show "—" and table shows "No signals yet." Already handled by existing null-guard logic in card computation and table render.
- **Sector field absent on old entries** → entries with `sector: null` would be excluded from all named-sector views but visible under "All Sectors". Acceptable — old entries predate sector tagging.

## Migration Plan

Frontend-only change; no deploy coordination required beyond the normal `prospectai-web` deployment.
