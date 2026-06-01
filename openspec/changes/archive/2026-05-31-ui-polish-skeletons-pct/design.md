## Context

The main page (`index.html`) uses `analytics.js` to render the analytics bar (runs count + leading sector + Stats link) and `recentWins.js` to render the marquee strip. Both fetch from the Modal backend asynchronously. `analytics.js` also fetches the version from `/api/version`. Both `style.css` and `stats.css` are loaded — `style.css` has existing `@keyframes shimmer` / `pulse-dot` animations; `stats.css` has `@keyframes skeleton-pulse` with the `.skeleton` class pattern.

`buildLegend()` in `stats.js` currently injects `<span class="stats-legend-count">${sl.value}</span>` into each legend item.

## Goals / Non-Goals

**Goals:**
- Skeleton for `#version-tag`: show a short pulsing bar while version is fetching; on resolve, set text as normal.
- Skeleton for `.analytics-count`: show a pulsing bar while analytics is fetching; on resolve, set the number.
- Skeleton for recent wins: render a fixed-width placeholder strip (3 ghost cards) while the wins fetch is in-flight; remove it on resolve (whether wins loaded or not).
- Remove `stats-legend-count` span from `buildLegend()` — show label + percentage only.

**Non-Goals:**
- No skeleton for the leading sector text or the Stats link.
- No skeleton for the sector selector cards or run button.
- No changes to the `buildLegend` signature — callers don't change.

## Decisions

### Decision 1: Skeleton CSS on the main page — reuse stats.css pattern in style.css
`stats.css` is only loaded on `stats.html`. The `.skeleton` / `@keyframes skeleton-pulse` pattern needs to also be available on `index.html`. Options:
- **Chosen**: Add `.skeleton` and `@keyframes skeleton-pulse` directly to `style.css` (a few lines). No new shared file needed; the class is simple enough to duplicate.
- Alternative: move skeleton styles to a shared `shared.css` — over-engineering for 4 lines of CSS.

### Decision 2: Version tag skeleton — replace inner text, restore on resolve
In `analytics.js`, before the fetch, set `versionEl.innerHTML = '<span class="skeleton" style="width:36px;height:14px;display:inline-block"></span>'`. On fetch success, set `versionEl.textContent = 'v' + data.version`. On failure, set it back to `v—`.

### Decision 3: Runs count skeleton — same pattern in analytics bar innerHTML
In `analytics.js` `render()`, replace the hardcoded `—` in `analytics-count` with a skeleton span. On fetch success, `countEl.textContent = count`.

### Decision 4: Recent wins skeleton — temporary placeholder section
In `recentWins.js`, inject a `<div class="recent-wins-skeleton">` with 3 ghost card placeholders before calling the API. Remove it unconditionally when the fetch completes (whether wins rendered or not). This prevents the banner area from shifting in layout.

### Decision 5: `buildLegend` — remove count span
Remove the `<span class="stats-legend-count">…</span>` line. The `stats-legend-count` CSS rule can stay (no harm if unused). The legend item becomes: dot → label → percentage.
