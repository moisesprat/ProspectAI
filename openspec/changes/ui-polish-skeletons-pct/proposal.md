## Why

The main page shows raw dashes (`v—`, `—`) while the backend is cold-starting (up to several seconds), which looks broken. The recent wins banner appears out of nowhere without a loading hint. In the Stats page, the risk profile donut and decisions donut show raw counts alongside percentages, but the run count and action counts come from different tracking windows — showing both creates confusion ("226 runs" vs "466 total"). Percentages alone convey the distribution accurately without the misleading absolute numbers.

## What Changes

1. **Main page — loading skeletons** (`index.html`, `analytics.js`, `recentWins.js`):
   - The version tag (`#version-tag`) shows a pulsing skeleton while the `/api/version` call is in-flight; replaced by `v1.9.0` (or whatever) once resolved.
   - The runs count (`.analytics-count`) shows a skeleton while `/api/analytics` is in-flight; replaced by the number once resolved.
   - The recent wins section renders a skeleton strip (a single row of placeholder cards) while `/api/long-buy-wins` is fetching; the skeleton is removed and replaced by the real marquee (or nothing, if no wins).

2. **Stats page — risk profile donut legend** (`stats.js`): Remove raw count from the risk profile donut legend. Show only label + percentage (e.g., "Aggressive · 75.9%").

3. **Stats page — decisions donut legend** (`stats.js`): Same — `buildLegend()` shall render label + percentage only, no raw count. Applies to both the Overall donut and any sector-filtered donut.

## Capabilities

### Modified Capabilities
- `stats-loading-skeletons`: Extend skeleton loading to the main page — version tag, runs count, and recent wins placeholder.
- `stats-page`: Donut legends (risk profile and decisions) show percentage only, no raw count.

## Impact

- **Frontend only** (`prospectai-web`): `analytics.js`, `recentWins.js`, `stats.js`, `style.css` (skeleton animation already in `stats.css`; needs equivalent in `style.css` or extracted to shared file).
- No backend changes.
