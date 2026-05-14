## Context

ProspectAI's web frontend currently shows a static "Example output" preview and a sector selector. There is no social proof that the pipeline produces profitable picks. A `long-buy-history` Modal Dict already stores LONG-BUY recommendations (ticker, sector, entry zone, recommended_at, run_id). Three records exist today (JNJ, MSFT, META). The backend populates this dict via a backfill script; automatic persistence on pipeline completion is not yet implemented.

The frontend is vanilla JS (no framework), served as static files on Cloudflare Pages. The backend is a Modal/FastAPI app.

## Goals / Non-Goals

**Goals:**
- Serve a lightweight endpoint that computes ROI for recent LONG-BUY picks and returns only winners.
- Render a compact "Recent Wins" strip in the UI that loads on page init (no user action required).
- Automatically persist LONG-BUY positions at pipeline completion so the dict grows organically.
- Keep latency acceptable (< 3 s for the wins endpoint under cold-start conditions).

**Non-Goals:**
- Historical performance charts or time-series visualization.
- Displaying negative-ROI or MONITOR/AVOID recommendations.
- Real-time price streaming or WebSocket updates.
- Authentication or per-user tracking.
- Backfill automation — existing manual script is sufficient for seeding.

## Decisions

### D1: Price lookup via yfinance in the backend

**Choice:** The `/api/long-buy-wins` endpoint fetches current prices using `yfinance` (already a transitive dependency of `prospectai`) at request time.

**Alternatives considered:**
- Client-side price fetch (free API like finnhub): adds CORS complexity, API key exposure, and inconsistent price sources.
- Scheduled price snapshot stored in a second Modal Dict: adds operational complexity and staleness.

**Rationale:** yfinance is free, already in the image, and a single batch `download()` call for ≤ 10 tickers returns in < 2 s. Acceptable for a non-critical widget.

### D2: Show up to 5 winning picks, last 30 days, sorted by ROI

**Choice:** Filter to `recommended_at` within 30 days, compute ROI = (current − entry_zone_mid) / entry_zone_mid, keep only ROI > 0, sort descending, cap at 5.

**Rationale:** 5 cards fit a single row on desktop and scroll naturally on mobile. 30-day window keeps results fresh without requiring a large history.

### D3: UI placement — below header, above sector selector

**Choice:** Render the "Recent Wins" strip as a horizontal scrollable row between the header's byline and the `.sample-preview` section. It collapses gracefully if no wins are available (empty state hidden entirely).

**Alternatives considered:**
- Sidebar widget: Not viable — current layout is single-column.
- Below the report: Users won't see it until after running analysis.
- Modal/toast on load: Too intrusive.

### D4: Persistence hook — write LONG-BUY positions after pipeline_done

**Choice:** In `serve.py`, after the pipeline returns, iterate `result.positions`, and for each position with `action == "LONG-BUY"`, write a record to the `long-buy-history` Modal Dict keyed as `{run_id}:{ticker}`.

**Rationale:** This keeps persistence close to the SSE stream (where the result is already parsed) and avoids coupling the core `prospectai` package to Modal infrastructure.

### D5: Record schema extension — add `trigger_price` field

**Choice:** Add optional `trigger_price` (the stock's price at recommendation time, i.e., `current_price` from the pipeline output) to each record. Existing records without this field default to `null`; ROI computation falls back to entry_zone_mid.

## Risks / Trade-offs

- **yfinance rate limits / downtime** → Endpoint returns an empty array on failure; UI hides the section. Non-critical path — never blocks the main pipeline.
- **Cold start latency** → First call after Modal scale-to-zero may take 3–5 s. Acceptable because the widget renders async after page load and shows a skeleton/loader.
- **Small dataset initially** → Only 3 records exist. Feature appears empty until more pipeline runs accumulate LONG-BUY picks. Mitigated by hiding the section entirely when no positive-ROI results exist.
- **Price staleness** → yfinance returns last-close during market hours or delayed quotes. Acceptable for a "proof of past performance" widget — precision isn't critical.
