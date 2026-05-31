## Context

The Performance table is rendered by `renderHistory(history)` in `stats.js`. The `history` array arrives pre-sorted by ROI descending from `excludeRecentHistory(deduplicateHistory(raw))`. `renderHistory` iterates the array in order and writes rows. The table headers are plain `<th>` elements with no interactivity.

## Goals / Non-Goals

**Goals:**
- Clickable `<th>` on Return and Signal Date columns.
- Sort state tracked as `{ col: 'roi' | 'date', dir: 'desc' | 'asc' }`.
- Default: `{ col: 'roi', dir: 'desc' }`.
- Clicking the active column toggles direction; clicking the other column sets it as active with `desc` as the initial direction.
- Visual indicator: a `↓` / `↑` character appended to the active header, dim on inactive headers.

**Non-Goals:**
- No sort on other columns (#, Ticker, Sector, Entry Price, Current, Version).
- No URL persistence of sort state.
- No server-side sorting.

## Decisions

### Decision 1: Sort applied by re-calling `renderHistory` with a sorted copy
After each header click, sort `_perfHistory` (a module-level cache of the filtered history) and call `renderHistory(sorted)`. This keeps rendering logic in one place — no DOM manipulation of existing rows.

### Decision 2: Null ROI sorts last regardless of direction
When sorting by ROI, entries with `roi_pct === null` always go to the bottom (after both positive and negative values), matching the existing default sort behavior.

### Decision 3: CSS — sortable headers styled with cursor:pointer and dim arrow
```css
.col-sortable { cursor: pointer; user-select: none; }
.col-sortable:hover { color: var(--text); }
.sort-arrow { color: var(--muted); margin-left: 4px; font-size: 10px; }
.sort-arrow.active { color: var(--amber); }
```
The `<th>` keeps its existing padding and alignment; only the cursor and arrow change.
