## 1. Backend — API response enrichment

- [x] 1.1 In `prospectai-backend/serve.py`, add `"recommended_action": "LONG-BUY"` to each item appended to the `wins` list in `GET /api/long-buy-wins` (around line 306)
- [x] 1.2 Deploy the updated `serve.py` to Modal (`modal deploy serve.py`)

## 2. Frontend — Win card update

- [x] 2.1 In `prospectai-web`, update the win card render function to display the recommendation label: "Recommended as LONG-BUY by ProspectAI · [formatted date]" using `item.recommended_action` and `item.recommended_at`
- [x] 2.2 Add a current price row to each card displaying `item.current_price` (formatted as "$X.XX")
- [x] 2.3 Add a conditional trigger price row: render only when `item.trigger_price` is present and non-null, displaying "Entry suggested at $X.XX" (omit entirely otherwise)
- [x] 2.4 Deploy the updated frontend to Cloudflare Pages
