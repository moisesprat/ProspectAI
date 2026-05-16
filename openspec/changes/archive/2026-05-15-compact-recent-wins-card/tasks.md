## 1. Verify spec matches live UI

- [x] 1.1 Load the production frontend (https://prospectai.pages.dev or current Cloudflare Pages URL) and confirm a Recent Wins card renders four rows as described in the modified spec (ticker + LONG-BUY tag; sector · time; ROI; `$trigger → $current` or `$current`)
- [x] 1.2 Confirm at least one card without a `trigger_price` renders row 4 as only `$current` (no arrow, no placeholder)
- [x] 1.3 Confirm the `LONG-BUY` tag text reflects the API `recommended_action` field (inspect a live `/api/long-buy-wins` response)

## 2. Sync spec

- [x] 2.1 Sync the delta spec into `openspec/specs/long-buy-wins-ui/spec.md` (handled by `/opsx:archive` sync step)
