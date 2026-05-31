## 1. Backend — Add prospectai_version to history endpoint

- [x] 1.1 In `prospectai-backend/app.py` `get_long_buy_history()`, add `"prospectai_version": r.get("prospectai_version")` to each item dict
- [x] 1.2 Deploy with `modal deploy serve.py` and verify the field appears in the response

## 2. CSS — Skeleton loaders

- [x] 2.1 Add `.skeleton` and `@keyframes skeleton-pulse` to `stats.css`: a `<div>` with rounded corners, muted background, and opacity pulsing 0.4 → 0.8 → 0.4 over 1.4s
- [x] 2.2 Add `.skeleton--line` (single text-line height, full width) and `.skeleton--block` (fixed height rectangle) size variants for use in cards and table cells

## 3. CSS — Activity tab charts

- [x] 3.1 Add `.stat-bar-row`, `.stat-bar-label`, `.stat-bar-track`, `.stat-bar-fill`, `.stat-bar-count` styles for the horizontal sector bar chart
- [x] 3.2 Add `.stats-risk-donut-wrap` flex container to position the small risk-profile donut + legend side by side within the risk-profile card

## 4. CSS — Decisions tab single donut + filter

- [x] 4.1 Add `.stats-chart-filter` styles for the sector `<select>` dropdown above the donut (monospace font, dark theme, border matching `--border2`)
- [x] 4.2 Remove or repurpose `.stats-sector-donuts` and `.stats-chart-card--sector` styles (they are no longer used)

## 5. CSS — Performance table additions

- [x] 5.1 Add `.stats-disclaimer` paragraph style: small monospace text, muted amber or dim colour, `border-left: 2px solid var(--amber-dim)`, padding-left
- [x] 5.2 Add `.col-version` column style (narrow, muted text)

## 6. HTML — Skeleton placeholders and structural updates

- [x] 6.1 In the Activity panel, replace the `<ul id="sector-list">` with a `<div id="sector-chart">` container; replace the `<ul id="risk-list">` with a `<div id="risk-donut-wrap">` + `<svg id="donut-risk">` + `<ul id="legend-risk">`
- [x] 6.2 In the Decisions panel, remove the overall donut row and per-sector donut container; add a `<select id="chart-sector-filter">` above a single `<div class="stats-chart-card--overall">` containing `<svg id="donut-decisions">` and `<ul id="legend-decisions">`
- [x] 6.3 In the Performance panel, add `<p class="stats-disclaimer" id="perf-disclaimer" hidden>` before the table; add a `<th class="col-version">Version</th>` column header
- [x] 6.4 Update the Performance section subtitle to include a `<span id="perf-row-count"></span>` for the dynamic row count message

## 7. JS — Skeleton loader integration

- [x] 7.1 Add `showSkeletons()` function called at the top of `init()` (before fetches) that injects `.skeleton` divs into: the total-runs value, sector chart container, risk donut container, the decisions chart area, the four KPI card values, and the table body
- [x] 7.2 Ensure each `renderX()` call clears its container before rendering (removing any skeleton elements)

## 8. JS — Activity tab: horizontal bar chart

- [x] 8.1 Rewrite `renderSummary()` sector section: compute `maxCount = Math.max(...counts)`, then for each sector build a `.stat-bar-row` with a `.stat-bar-fill` whose `width` style = `${(count/maxCount)*100}%`
- [x] 8.2 Rewrite `renderSummary()` risk profile section: call `renderDonut()` into `#donut-risk` with Conservative=`#4a7c59`, Aggressive=`#e0a040`; build legend in `#legend-risk`

## 9. JS — Decisions tab: single donut with sector filter

- [x] 9.1 Rewrite `renderCharts()` to: populate `#chart-sector-filter` with "Overall" + sorted sector keys; render the initial "Overall" donut into `#donut-decisions`
- [x] 9.2 Wire an `addEventListener('change')` on `#chart-sector-filter` that re-calls `renderDonut()` and `buildLegend()` with the selected sector's data (or aggregated overall)

## 10. JS — Performance table: data quality rules

- [x] 10.1 Add `deduplicateHistory(history)`: group by `(ticker, utcDateStr, trigger_price)`, keep the entry with the latest `recommended_at` per group
- [x] 10.2 Add `excludeRecentHistory(history)`: filter out entries where `recommended_at` is within 5 UTC calendar days of today
- [x] 10.3 Apply both transforms in order (deduplicate first, then exclude recent) before passing history to `renderHistory()` and `renderPerformanceKpis()`
- [x] 10.4 Add `<td class="col-version">` cell to each table row rendering `row.prospectai_version ?? '—'`
- [x] 10.5 After filtering, show the disclaimer: `document.getElementById('perf-disclaimer').hidden = false` and set `#perf-row-count` text to `"${filteredCount} signals · entries within 5 days and duplicates excluded"`

## 11. QA

- [x] 11.1 Verify skeletons appear briefly on load and are replaced by real data (throttle network to Slow 3G in DevTools)
- [x] 11.2 Verify the sector horizontal bar chart renders with correct relative widths
- [x] 11.3 Verify the risk profile donut renders with correct slice proportions
- [x] 11.4 Verify the Decisions dropdown includes all sectors (Technology, Semiconductors, Finance, Energy, Healthcare, etc.) and switching sectors updates the donut
- [x] 11.5 Verify duplicate rows are removed from the Performance table (MU entries on same date/trigger should collapse to 1)
- [x] 11.6 Verify entries from the last 5 days are excluded from the table and KPI cards
- [x] 11.7 Verify the Version column shows version strings or "—"
- [x] 11.8 Verify the stop-loss disclaimer is visible above the table
- [x] 11.9 Verify KPI cards (Win Rate, Avg Return, Best/Worst Pick) reflect the post-filter dataset
