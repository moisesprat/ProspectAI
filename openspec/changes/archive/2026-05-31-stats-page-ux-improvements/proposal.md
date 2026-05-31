## Why

The Stats page has several usability gaps: blank screens while APIs load, chart types that don't suit the data shape, a Decisions tab with too many undifferentiated donuts and missing sectors, and a Performance table that surfaces noisy/duplicate data without enough context. These improvements make the page significantly more informative and professional.

## What Changes

1. **Loading skeletons** — Animated "loading" placeholders replace blank areas while the two API calls (`/api/analytics`, `/api/long-buy-history`) are in-flight. Each card/chart/table area shows a pulsing skeleton until its data arrives.

2. **Activity tab — charts redesign** — Replace the sector coverage list with a horizontal bar chart (CSS-only, no library). Replace the risk-profile list with an SVG donut pie chart, consistent with the Decisions tab style.

3. **Decisions tab — single filtered donut** — Replace the "one donut per sector" grid with a single donut chart that defaults to "Overall" and has a sector dropdown to filter to any individual sector. All sectors stored in `action_breakdown` are shown (including Semiconductors, Finance, Energy — the missing ones were a rendering bug because the loop only showed sectors with at least one slice, but the sector dropdown must include all sectors present in the data).

4. **Performance table — data quality and transparency**:
   - **Exclude last 5 days**: entries whose `recommended_at` is within 5 calendar days of today are hidden (too recent to be meaningful).
   - **Deduplicate**: rows with the same ticker + same calendar date + same trigger price are collapsed to a single row (keep the one with the most recent `recommended_at` timestamp).
   - **Stop-loss disclaimer**: a small note above the table stating that stop-loss levels were not factored into ROI — if the stop-loss price was hit, the actual outcome would have been different.
   - **Version column**: add a `Version` column showing `prospectai_version` for each row (backend endpoint extended to return this field).

## Capabilities

### New Capabilities
- `stats-loading-skeletons`: Animated skeleton placeholders shown during API fetches on the Stats page.

### Modified Capabilities
- `stats-page`: Activity tab charts redesigned; Decisions tab simplified to one filtered donut; Performance table data quality rules (5-day exclusion, deduplication, disclaimer, version column).
- `long-buy-wins-api`: Extend `GET /api/long-buy-history` response to include `prospectai_version` field per row.

## Impact

- **Frontend** (`prospectai-web`): `stats.html`, `stats.css`, `stats.js` — no new files needed.
- **Backend** (`prospectai-backend`): `app.py` — add `prospectai_version` to the `/api/long-buy-history` response; redeploy with `modal deploy serve.py`.
- No changes to the pipeline, Pydantic schemas, or other pages.
