## 1. Backend — Persistence Hook

- [ ] 1.1 In `serve.py`, after `pipeline_done` is put on the queue, iterate result positions and write each LONG-BUY to `long-buy-history` Modal Dict with key `{run_id}:{ticker}` and fields: ticker, sector, recommended_at, entry_zone_low, entry_zone_high, entry_zone_mid, trigger_price, run_id
- [ ] 1.2 Wrap persistence in try/except so failures never break the SSE stream

## 2. Backend — Wins Endpoint

- [ ] 2.1 Add `yfinance` to the Modal image `pip_install` list
- [ ] 2.2 Implement `GET /api/long-buy-wins` endpoint: read all records from `long-buy-history`, filter to last 30 days, fetch current prices via yfinance batch download, compute ROI, filter positive, sort descending, cap at 5
- [ ] 2.3 Return `{ "wins": [...] }` with fields: ticker, sector, recommended_at, entry_zone_low, entry_zone_high, current_price, roi_pct (rounded 2dp), trigger_price
- [ ] 2.4 Handle edge cases: empty dict, yfinance failure per ticker (exclude that ticker), full yfinance failure (return empty array)

## 3. Frontend — Wins Section

- [ ] 3.1 Create `ui/recentWins.js` module: export `render(container)` that fetches `/api/long-buy-wins`, returns early (no DOM) if empty
- [ ] 3.2 Render section with heading ("Recent picks performing well"), disclaimer line, and a horizontal card row
- [ ] 3.3 Each card shows: ticker, sector, ROI badge ("+X.X%"), relative time ("3d ago")
- [ ] 3.4 Add CSS for the wins section — horizontal scroll on mobile (< 640px), flex-wrap on desktop
- [ ] 3.5 Wire `render()` call in `main.js` (or equivalent entry point) targeting a container between header and sample-preview

## 4. Integration & Deploy

- [ ] 4.1 Add `/api/long-buy-wins` to CORS allow list (already covered by existing `allow_methods=["GET"]`)
- [ ] 4.2 Test endpoint locally with existing 3 records (MSFT, META, JNJ)
- [ ] 4.3 Deploy updated backend to Modal
- [ ] 4.4 Deploy updated frontend to Cloudflare Pages
- [ ] 4.5 Verify wins section renders on production with live data
