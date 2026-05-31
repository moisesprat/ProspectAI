## Why

The Stats page currently presents three sections stacked vertically with no clear information hierarchy, mixes vocabulary inconsistently, and lacks key performance metrics (win rate, average return, best/worst pick). Reorganising into tabs with proper investment vocabulary and headline performance KPIs makes the page substantially more useful and professional.

## What Changes

- Replace the vertical section layout with a **3-tab navigation**: Activity, Decisions, Performance.
- **Activity tab** — usage coverage: total pipeline runs, breakdown by sector, breakdown by risk profile. Uses proper labels ("Aggressive", "Conservative") and sorts sectors by run count.
- **Decisions tab** — signal distribution: the existing donut charts (overall + per-sector) showing how signals (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID) are distributed. Renamed from "Recommendation Distribution" to "Signal Distribution" for cleaner investment vocabulary.
- **Performance tab** — track record: the existing LONG-BUY table plus three new headline KPI cards above it: **Win Rate** (% of picks with ROI > 0), **Avg Return** (mean ROI across picks with valid trigger price), **Best Pick** and **Worst Pick** callout cards.
- Update all section titles to use consistent investment vocabulary: "Analyses" → "Runs", "Recommendation" → "Signal", "LONG-BUY Track Record" → "Signal Performance".

## Capabilities

### New Capabilities
- `stats-page-tabs`: Tab navigation shell replacing the linear section layout; tab state stored in URL hash so direct links work.
- `stats-performance-kpis`: Win rate, avg return, best pick, and worst pick KPI cards computed client-side from the `/api/long-buy-history` response.

### Modified Capabilities
- `stats-page`: Layout restructured into tabs; section titles updated; no new API calls or backend changes required.

## Impact

- **Frontend only** (`prospectai-web`): `stats.html` restructured, `stats.css` updated, `stats.js` updated to wire tab switching and render KPI cards.
- No backend changes — all new metrics are computed client-side from the existing `/api/long-buy-history` and `/api/analytics` responses.
- No breaking changes to any other page.
