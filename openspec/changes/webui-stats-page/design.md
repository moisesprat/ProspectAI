## Context

ProspectAI's web frontend (`prospectai-web`) is a vanilla-JS SPA served from a single `index.html`, with UI modules under `ui/` and styles in `styles/style.css`. The backend (`prospectai-backend`) is a FastAPI app on Modal with two relevant endpoints:

- `GET /api/analytics` — returns `total`, `by_sector`, `leading_sector`, `by_risk_profile`, `action_breakdown`.
- `GET /api/long-buy-wins` — returns only LONG-BUY entries with ROI > 4% (positive wins only, deduplicated to one entry per ticker by highest ROI).

The existing analytics widget (`ui/analytics.js`) renders a one-line bar showing total runs and leading sector. Simple Analytics custom events are fired via `ui/saEvents.js`.

The reference design (image provided by user) shows a filterable table with columns: `#`, Ticker, Sector, Entry, Current Price, Source badge, ROI badge, Date, and a mini ROI progress bar. The aesthetic is clean white/light-grey with olive-green accents for positive ROI.

## Goals / Non-Goals

**Goals:**
- New `stats.html` page with: usage summary (total analyses, by sector, by risk profile) + full LONG-BUY track record table sorted by ROI descending.
- New backend endpoint `GET /api/long-buy-history` returning **all** LONG-BUY entries (any ROI, no deduplication) with live current price and computed ROI.
- A prominent "ProspectAI Stats" link button added to `index.html` next to the existing analytics bar.
- Fire `stats_page_open` Simple Analytics event when `stats.html` loads.
- Track record table columns: `#`, Ticker, Sector, Predicted Date, Entry Price, Current Price, ROI — sorted ROI desc, with a mini progress bar for positive ROI.

**Non-Goals:**
- No backend counter for stats page views (Simple Analytics handles it).
- No modification of existing `GET /api/long-buy-wins` endpoint behavior — the new endpoint is additive.
- CSS-only mini-bars for ROI column in the track record table; SVG conic-gradient pie charts (no external library) for action-type distribution.
- No server-side rendering or build changes — `stats.html` ships as a static file like `index.html`.
- No filtering/search UI in the initial release (the reference image shows filters, but these are deferred to keep scope tight; the table is sorted by ROI on load).
- Action-type distribution visualised as **pie charts**: one overall chart and one per sector, using `action_breakdown` data already returned by `GET /api/analytics`. Action types: LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID.

## Decisions

### Decision 1: Separate `stats.html` over a JS-router SPA view
**Chosen:** Add `stats.html` as a standalone page.
**Rationale:** The project has no JS router; adding one just for this page would be over-engineering. A separate HTML file follows the same pattern as the existing single-page app, is independently cacheable, and makes the SA event fire naturally on page load. The "ProspectAI Stats" link in `index.html` simply points to `stats.html`.
**Alternative considered:** Inject a hidden `<div id="stats-view">` into `index.html` and toggle visibility — rejected because it bloats the main page bundle and complicates state management.

### Decision 2: New `GET /api/long-buy-history` endpoint (additive, not modifying wins)
**Chosen:** Add a new endpoint rather than changing `get_long_buy_wins`.
**Rationale:** `get_long_buy_wins` is consumed by the existing "Recent Wins" cards on `index.html` with specific semantics (ROI > 4%, deduplicated). The Stats page needs all entries and all ROIs. Changing the existing endpoint's contract would break the wins cards.
**Shape:** Returns `{ "history": [...] }` where each item has `ticker`, `sector`, `recommended_at`, `trigger_price`, `current_price`, `roi_pct`, `risk_profile`. Items with no `trigger_price` are included but `roi_pct` is `null`. Sorted by `roi_pct` descending (nulls last) server-side.

### Decision 3: No deduplication in `/api/long-buy-history`
**Chosen:** Return every entry (same ticker can appear multiple times on different dates).
**Rationale:** The Stats page is a track record — every prediction is its own row. The user's reference image shows the same ticker appearing multiple times (e.g., MU twice, AMD twice). Deduplication would hide true prediction history.

### Decision 4: Aggressive vs Conservative label mapping
**Chosen:** Map `by_risk_profile` keys directly — `conservative` → "Conservative", `aggressive` → "Aggressive", `moderate` → "Moderate" — using a lookup table in the frontend JS. No backend changes needed.
**Rationale:** The backend already stores `risk_profile:conservative`, `risk_profile:aggressive` etc. The frontend just prettifies the labels.

### Decision 5: Pie charts via SVG `stroke-dasharray` — no external library
**Chosen:** Render pie/donut charts using inline SVG with `stroke-dasharray` / `stroke-dashoffset` on `<circle>` elements — one arc per action type.
**Rationale:** The project has no charting dependency and adding Chart.js (~200 KB) for a stats page is disproportionate. SVG donut slices are ~30 lines of JS per chart, stay on-brand, and need no bundler changes.
**Action-type colour palette:**
- LONG-BUY → `#4a7c59` (olive green)
- WAIT-FOR-ENTRY → `#e0a040` (amber)
- MONITOR → `#8c8c8c` (neutral grey)
- AVOID → `#c0392b` (red)

Layout: one "Overall" donut (aggregates all sectors) + a row of smaller per-sector donuts below it, each with a legend listing action type, count, and percentage.

### Decision 6: Look & feel — olive-green on white, matching reference image
**Chosen:** `stats.html` uses the same IBM Plex font stack and CSS custom properties as `index.html`. New CSS classes scoped under a `stats-*` namespace in a new `styles/stats.css` file.
**ROI column:** Positive ROI shown as green badge + mini filled bar. Neutral/negative as grey badge. Progress bar width = `min(roi_pct / 50, 1) * 100%` so bars saturate at 50% ROI.

## Risks / Trade-offs

- **yfinance latency on `/api/long-buy-history`:** Fetching live prices for all tickers on each page load adds 1-3 s. Mitigation: the endpoint reuses the same yfinance batch-download pattern as `get_long_buy_wins`; result should be fast enough for a stats page. If the store has many tickers, consider a 60 s server-side cache (out of scope for now).
- **`trigger_price` null entries:** Some early LONG-BUY records may have no trigger price. These rows will appear in the table with "—" for entry and ROI. Mitigation: front-end renders gracefully; nulls sort last.
- **No filter/search in v1:** Power users expecting the full filter UI from the reference image may be surprised. Mitigation: the table is sorted by ROI by default which surfaces the most useful data immediately; filter can be added in a follow-up change.

## Migration Plan

1. Add `GET /api/long-buy-history` route to `prospectai-backend/app.py` — fully additive, no existing behavior changes.
2. Add `stats.html` + `styles/stats.css` + `ui/stats.js` to `prospectai-web`.
3. Update `index.html` to insert the "ProspectAI Stats" button next to the analytics bar.
4. Add `trackStatsPageOpen` to `ui/saEvents.js`; call it from `ui/stats.js` on load.
5. Redeploy the Modal backend (`modal deploy serve.py`).
6. Deploy the updated web frontend.
7. Rollback: remove the new `stats.html` link from `index.html` — the rest of the app is unaffected.

## Open Questions

- Should the Stats page show only LONG-BUY entries, or all action types (SCALED-ENTRY, WAIT-FOR-ENTRY, etc.)? Current proposal: LONG-BUY only, to keep the track record focused on committed picks.
- Should negative-ROI rows be hidden by default (opt-in "show all")? Current proposal: show all rows sorted by ROI desc — transparency is the point.
