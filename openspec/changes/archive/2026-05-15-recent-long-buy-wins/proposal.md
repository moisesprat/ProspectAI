## Why

Users landing on the ProspectAI web app have no evidence the tool produces profitable recommendations. Displaying recent LONG-BUY picks that are currently in positive ROI builds credibility and encourages users to run their own analysis.

## What Changes

- Add a new backend endpoint (`GET /api/long-buy-wins`) that reads the `long-buy-history` Modal Dict, fetches current prices for each ticker, computes ROI from the entry zone midpoint, filters to positive-ROI recommendations from the last 30 days, and returns the top results sorted by ROI descending.
- Add a "Recent Wins" section to the web UI (above the execution panel) that renders the returned recommendations as compact cards showing ticker, sector, recommended date, entry zone, current price, and ROI percentage.
- Extend the backend pipeline completion hook in `serve.py` to persist every LONG-BUY position into the `long-buy-history` Modal Dict automatically on each successful run.

## Capabilities

### New Capabilities
- `long-buy-wins-api`: Backend endpoint that computes and serves positive-ROI recommendations from the last 30 days
- `long-buy-wins-ui`: Frontend section displaying recent winning recommendations with ROI badges
- `long-buy-persistence`: Automatic storage of LONG-BUY positions into `long-buy-history` on pipeline completion

### Modified Capabilities

_(none — no existing spec-level requirements change)_

## Impact

- **Backend** (`prospectai-backend/serve.py`): New `/api/long-buy-wins` endpoint; new persistence logic in the `pipeline_done` path; new `yfinance` dependency in the Modal image for live price lookup.
- **Frontend** (`prospectai-web/ui/`): New UI module for the wins section; fetched on page load.
- **Modal Dict** (`long-buy-history`): Schema gains an optional `trigger_price` field; existing records remain valid (field defaults to `null`).
- **No changes** to the `prospectai` Python package itself or the pipeline output schema.
