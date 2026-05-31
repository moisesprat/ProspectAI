## 1. HTML — Restructure into tabs

- [x] 1.1 Replace the three `<section>` blocks in `stats.html` with a tab bar (`<nav role="tablist">`) containing three `<button role="tab">` buttons: "Activity", "Decisions", "Performance"
- [x] 1.2 Wrap each section in a `<div role="tabpanel">` with matching IDs (`panel-activity`, `panel-decisions`, `panel-performance`); add `hidden` to the two inactive panels by default
- [x] 1.3 Add four KPI card slots (`<div id="kpi-win-rate">`, `kpi-avg-return`, `kpi-best-pick`, `kpi-worst-pick`) at the top of the Performance panel, before the track record table
- [x] 1.4 Update all section titles and subtitles to use investment vocabulary: "Total Runs", "Sector Coverage", "Signal Distribution", "Signal Performance", etc. (per the vocabulary table in design.md)

## 2. CSS — Tab bar and KPI cards

- [x] 2.1 Add `.stats-tabs` tab bar styles: horizontal flex row, bottom border `var(--border)`, gap between buttons
- [x] 2.2 Add `.stats-tab` button styles: monospace 11px, muted text, no background, `cursor:pointer`; active state (`[aria-selected="true"]`): amber text + 2px amber bottom border
- [x] 2.3 Add `.stats-kpi-grid` grid (2×2, responsive to 1-col on mobile) and `.stats-kpi-card` card styles for the four KPI cards
- [x] 2.4 Add `.kpi-value--pos` (green) and `.kpi-value--neg` (red) modifier classes for Avg Return, Best Pick, Worst Pick colour coding

## 3. JS — Tab switching logic

- [x] 3.1 Add `initTabs()` in `stats.js` that reads `window.location.hash` on load, activates the matching tab (default `#activity`), and calls `history.replaceState` if hash was absent
- [x] 3.2 Wire click handlers on each tab button: update `aria-selected`, toggle `hidden` on panels, call `history.pushState` to update the hash
- [x] 3.3 Add `window.addEventListener('popstate', ...)` to handle browser back/forward navigation between tabs

## 4. JS — Performance KPI cards

- [x] 4.1 Implement `renderPerformanceKpis(history)` in `stats.js`: derive win rate, avg return, best pick, worst pick from the `history` array (entries with non-null `roi_pct`)
- [x] 4.2 Render Win Rate card: `(positiveCount / validCount * 100).toFixed(1) + '%'`; show "—" if `validCount === 0`
- [x] 4.3 Render Avg Return card: mean of non-null `roi_pct` values, prefixed `+` or `−`; show "—" if no valid entries
- [x] 4.4 Render Best Pick card: ticker + ROI of the entry with highest `roi_pct`; green colour; show "—" if no valid entries
- [x] 4.5 Render Worst Pick card: ticker + ROI of the entry with lowest `roi_pct`; red colour; show "—" if no valid entries
- [x] 4.6 Call `renderPerformanceKpis(data.history)` in `init()` after the history fetch succeeds; pass `[]` on failure (shows "—")

## 5. JS — Vocabulary and empty-state updates

- [x] 5.1 Replace the hard-coded "Recommendation Distribution" subtitle text in `stats.js` chart rendering with "Signal Distribution"
- [x] 5.2 Add a "No signal data yet" placeholder in the Decisions panel when `action_breakdown` is empty (currently the section is just `hidden` — show a message instead)

## 6. QA

- [x] 6.1 Verify tab switching works: clicking each tab shows the correct panel and updates the hash
- [x] 6.2 Verify direct links: `stats.html#decisions` and `stats.html#performance` open on the correct tab
- [x] 6.3 Verify all four KPI cards render with correct values (Win Rate, Avg Return, Best Pick, Worst Pick)
- [x] 6.4 Verify KPI colour coding: positive avg return is green, negative is red; best pick green, worst pick red
- [x] 6.5 Verify vocabulary: all old labels are replaced (no "Total Analyses", no "Recommendation Distribution", no "LONG-BUY Track Record")
- [x] 6.6 Verify mobile layout: on a narrow viewport, cards and KPI grid stack to a single column
