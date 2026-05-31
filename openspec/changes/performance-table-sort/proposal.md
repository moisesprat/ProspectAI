## Why

The Performance table is fixed at ROI descending. Users may want to see the most recent signals first to understand recent activity, or sort by ROI to find the best/worst performers. Clickable column headers are a standard table UX pattern that adds this flexibility with minimal complexity.

## What Changes

- The **Return** and **Signal Date** column headers in the Performance table become clickable sort controls.
- Default sort on load remains **Return descending** (highest ROI first).
- Clicking **Return** toggles between descending and ascending ROI sort.
- Clicking **Signal Date** toggles between descending (newest first) and ascending (oldest first) date sort.
- The active sort column shows a directional arrow indicator (↓ or ↑).
- Sorting is client-side only — no new API calls.

## Capabilities

### Modified Capabilities
- `stats-page`: Performance table column headers for Return and Signal Date are interactive sort controls with visual direction indicators.

## Impact

- **Frontend only** (`prospectai-web`): `stats.js` and `stats.css` — no backend changes, no HTML structural changes beyond `<th>` attributes.
