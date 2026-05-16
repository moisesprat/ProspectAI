## 1. Backend — ROI formula and filter

- [x] 1.1 In `prospectai-backend/serve.py` `GET /api/long-buy-wins`, filter out records with null/missing `trigger_price` before fetching prices
- [x] 1.2 Replace the midpoint ROI calculation with `(current - trigger_price) / trigger_price * 100`
- [x] 1.3 Deploy the updated `serve.py` to Modal (`modal deploy serve.py`)

## 2. Verify

- [x] 2.1 `curl /api/long-buy-wins` and confirm only records with `trigger_price` are returned and `roi_pct` matches `(current - trigger) / trigger * 100`
