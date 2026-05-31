## Context

`stats.html` currently renders three `<section>` blocks stacked vertically: summary cards, charts, and track record table. All data is fetched in parallel on load from `/api/analytics` and `/api/long-buy-history`. The page uses no framework — pure vanilla JS ES modules, no router, no state library. `stats.js` contains `renderSummary`, `renderCharts`, and `renderHistory` functions, plus a `renderDonut` SVG helper.

The performance KPI values (win rate, avg return, best/worst pick) can be derived entirely from the `/api/long-buy-history` response already in memory — no new API call needed.

## Goals / Non-Goals

**Goals:**
- Tab nav with three tabs: Activity | Decisions | Performance.
- URL hash (`#activity`, `#decisions`, `#performance`) drives active tab so deep links work and browser back/forward work.
- Performance tab gains four KPI cards above the table: Win Rate, Avg Return, Best Pick, Worst Pick.
- All section titles use investment vocabulary: "Runs", "Signal Distribution", "Signal Performance".

**Non-Goals:**
- No animated tab transitions (keep it minimal).
- No server-side tab state — hash only.
- No new API endpoints.
- No filtering or sorting controls (deferred).

## Decisions

### Decision 1: URL hash for tab state
**Chosen:** Read `window.location.hash` on load; listen to `hashchange` to switch tabs. Default to `#activity` if hash is absent or unknown.
**Rationale:** Zero dependencies, survives page reload, enables direct linking, works with browser history. Simpler than a JS router or `sessionStorage`.

### Decision 2: Tab panels as `<section>` with `hidden` attribute
**Chosen:** Keep the three `<section>` elements in the DOM; toggle `hidden` to show/hide. Tabs are `<button>` elements with `role="tab"` / `aria-selected`.
**Rationale:** No layout shift, no JS rendering delay for panel content, accessible by default.

### Decision 3: KPI cards computed client-side after history fetch
**Chosen:** After `renderHistory(data.history)`, call `renderPerformanceKpis(data.history)` which computes win rate, avg ROI, best, and worst from the same array.
- **Win Rate** = `(picks with roi_pct > 0) / (picks with roi_pct !== null) * 100`, displayed as `X.X%`.
- **Avg Return** = mean of all non-null `roi_pct` values, displayed as `+X.X%` or `−X.X%`.
- **Best Pick** = entry with highest `roi_pct` (ticker + ROI).
- **Worst Pick** = entry with lowest `roi_pct` (ticker + ROI).
**Rationale:** All data is already in memory; no extra fetch, no backend change.

### Decision 4: Tab bar style
**Chosen:** A horizontal row of `<button>` tabs below the page header, flush-left, using the existing `var(--mono)` font. Active tab: amber bottom border + amber text. Inactive: muted text, no border.
**Rationale:** Matches the existing monospace aesthetic without introducing new visual patterns.

### Decision 5: Vocabulary mapping
| Old label | New label |
|---|---|
| Total Analyses | Total Runs |
| pipeline runs completed | pipeline executions |
| By Sector | Sector Coverage |
| By Risk Profile | Risk Profile |
| Recommendation Distribution | Signal Distribution |
| How action types are distributed… | Signal mix across all runs and by sector. |
| LONG-BUY Track Record | Signal Performance |
| All LONG-BUY predictions… | All LONG-BUY signals with live prices and return, ranked by ROI. |

## Risks / Trade-offs

- **Hash-based routing and `<a href="stats.html">` from the main page**: will land on `#activity` by default, which is the correct first tab. No issue.
- **KPI cards show "—" if history has zero valid ROI entries**: graceful because all four KPIs check for null before computing.
- **`hidden` attribute on `<section>` vs `display:none` CSS**: `hidden` is a valid HTML attribute that also sets `display:none` in all modern browsers. Using it keeps the JS simple (toggle `.hidden` property).
