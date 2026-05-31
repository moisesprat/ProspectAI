## 1. Backend — New History Endpoint

- [x] 1.1 Add `GET /api/long-buy-history` route to `prospectai-backend/app.py` that reads all records from `long_buy_store`, fetches current prices in batch via yfinance, computes `roi_pct` where `trigger_price` is valid, and returns `{ "history": [...] }` sorted by `roi_pct` desc (nulls last)
- [x] 1.2 Ensure the response schema matches the spec: fields `ticker`, `sector`, `recommended_at`, `trigger_price`, `current_price`, `roi_pct`, `risk_profile` on each item
- [x] 1.3 Add CORS header coverage for the new endpoint (verify it matches the existing pattern in `app.py`)
- [x] 1.4 Deploy updated backend with `modal deploy serve.py` and smoke-test `GET /api/long-buy-history` in the browser

## 2. Frontend — Stats Entry Point in Main Page

- [x] 2.1 Add `trackStatsPageOpen` function to `prospectai-web/ui/saEvents.js` that calls `saEvent('stats_page_open')`
- [x] 2.2 Update `prospectai-web/ui/analytics.js` `render()` to append a "ProspectAI Stats" anchor link (`<a href="stats.html">`) visually attached to the analytics bar, styled as a prominent pill/button

## 3. Frontend — Stats Page Shell

- [x] 3.1 Create `prospectai-web/stats.html` with the same `<head>` setup as `index.html` (fonts, SA script, `stats.css` link, `stats.js` module)
- [x] 3.2 Create `prospectai-web/styles/stats.css` with the full page layout: summary card grid, chart section, track record table — using the same IBM Plex font stack and olive-green/white colour palette as the main page
- [x] 3.3 Add a back-link to `index.html` (or `/`) in the `stats.html` header

## 4. Frontend — Usage Summary Cards

- [x] 4.1 Create `prospectai-web/ui/stats.js` with a `loadSummary()` function that fetches `GET /api/analytics`, maps `by_risk_profile` keys to humanised labels (conservative → Conservative, aggressive → Aggressive), and renders total-analyses, by-sector, and by-risk-profile cards into `stats.html`
- [x] 4.2 Handle analytics fetch failure gracefully: show "—" placeholders, no thrown errors

## 5. Frontend — Action-Type Pie Charts

- [x] 5.1 Implement `renderDonut(svgEl, slices)` helper in `stats.js` that draws SVG donut slices using `stroke-dasharray` / `stroke-dashoffset` on `<circle>` elements (no external library)
- [x] 5.2 Implement `loadCharts()` in `stats.js` that reads `action_breakdown` from the analytics response and calls `renderDonut` once for the aggregated "Overall" chart
- [x] 5.3 Render one smaller per-sector donut chart for each sector present in `action_breakdown`, each with its own legend showing action type, count, and percentage
- [x] 5.4 Apply consistent colour coding: LONG-BUY `#4a7c59`, WAIT-FOR-ENTRY `#e0a040`, MONITOR `#8c8c8c`, AVOID `#c0392b`
- [x] 5.5 Hide the entire chart section when `action_breakdown` is empty

## 6. Frontend — LONG-BUY Track Record Table

- [x] 6.1 Implement `loadHistory()` in `stats.js` that fetches `GET /api/long-buy-history` and renders rows into the track record table
- [x] 6.2 Format `recommended_at` as `dd-MMM-yy` using UTC date components (same pattern as `recentWins.js`)
- [x] 6.3 Render ROI badge: green `+X.X%` with a proportional mini progress bar (width = `min(roi / 50, 1) * 100%`) for positive ROI; muted/red `−X.X%` with no bar for negative; "—" for null ROI
- [x] 6.4 Render Entry Price as "—" when `trigger_price` is null
- [x] 6.5 Handle history endpoint failure gracefully: show a "Could not load track record" message in the table area

## 7. Frontend — Simple Analytics Event

- [x] 7.1 Call `trackStatsPageOpen()` at the top of `stats.js` `init()` (fires on page load before data fetches)

## 8. QA

- [x] 8.1 Verify the "ProspectAI Stats" button appears on `index.html` and navigates to `stats.html`
- [x] 8.2 Verify the SA `stats_page_open` event fires in the browser console (`[SA] fired OK: stats_page_open`)
- [x] 8.3 Verify summary cards, risk profile labels, and sector counts render correctly against the live backend
- [x] 8.4 Verify the Overall donut and per-sector donuts render with correct slice proportions and legend values
- [x] 8.5 Verify the track record table is sorted by ROI descending, null-ROI rows appear last, dates are formatted correctly, and progress bars scale proportionally
- [x] 8.6 Verify graceful degradation: disconnect network and confirm summary and table show placeholders without JS errors
