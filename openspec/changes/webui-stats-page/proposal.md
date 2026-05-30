## Why

Users have no consolidated view of ProspectAI's prediction track record or usage patterns — stats are buried in raw API responses. A dedicated Stats page surfaces this intelligence, demonstrates the tool's value over time, and adds accountability by showing real ROI on past LONG-BUY calls.

## What Changes

- Add a standalone **Stats page** (`stats.html` or a JS-driven view) in the web frontend, reachable from a prominent "ProspectAI Stats" link in the main page header.
- The Stats page aggregates data from two existing API endpoints: `GET /api/analytics` and `GET /api/long-buy-wins` (extended to return all long-buys, not only recent winners).
- Display **usage counters**: total analyses run, breakdown by sector, breakdown by risk profile (Aggressive vs. Conservative).
- Display a **LONG-BUY track record table**: ticker, sector, date predicted, entry (trigger) price, current price, ROI — sorted by ROI descending.
- Fire a **Simple Analytics custom event** (`stats_page_open`) when the user navigates to the Stats page, so usage is tracked via Simple Analytics (not the backend store).
- Show a visible **"ProspectAI Stats"** button/link in the main page header, next to the existing runs count and leading-sector badge.

## Capabilities

### New Capabilities
- `stats-page`: Full Stats page with usage metrics and LONG-BUY track record table, including the entry point button in the main page and click tracking.

### Modified Capabilities
- `analytics-action-breakdown`: Ensure `by_risk_profile` is returned in a way the frontend can render as Aggressive vs. Conservative labels (no backend counter changes needed for Stats page views).
- `long-buy-wins-api`: Extend `GET /api/long-buy-wins` (or add a new endpoint `GET /api/long-buy-history`) to return **all** historical LONG-BUY entries (not just recent positive-ROI wins), with current price and ROI computed live, so the Stats page can display the complete track record sorted by ROI.

## Impact

- **Frontend** (`../prospectai-web`): New `stats.html` (or SPA view), new CSS styles, updated `index.html` to add the Stats button.
- **Backend** (`../prospectai-backend`): Extend analytics store to track `stats_page_views`; extend or add an endpoint returning all LONG-BUY history with live ROI.
- No changes to the core `ProspectAIFlow` pipeline or Pydantic schemas.
- No breaking changes to existing API consumers — existing fields remain unchanged.
