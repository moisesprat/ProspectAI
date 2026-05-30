## 1. Backend — Record action counts

- [ ] 1.1 In `_persist_run_results` (app.py), add a loop over all positions that increments `analytics_store[f"action:{sector}:{pos['action']}"]` for each position, wrapped in `try/except` matching the existing pattern
- [ ] 1.2 Verify the write uses the uppercase action string exactly as stored in the position dict (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID)

## 2. Backend — Expose breakdown in GET /api/analytics

- [ ] 2.1 In `get_analytics` (app.py), extract all keys matching `action:{sector}:{action_type}` from the raw store dict
- [ ] 2.2 Build `action_breakdown` dict: for each sector, compute `counts`, `total`, and `percentages` (rounded to 1 decimal)
- [ ] 2.3 Add `action_breakdown` to the response dict returned by `get_analytics`

## 3. Analytics Skill — Display breakdown

- [ ] 3.1 In the `/prospectai-analytics` skill, read the new `action_breakdown` field from the API response
- [ ] 3.2 For each sector that has action data, display a table or formatted list showing action type counts and percentages

## 4. Verification

- [ ] 4.1 Run a pipeline analysis locally and confirm new `action:*` keys appear in `analytics.json`
- [ ] 4.2 Call `GET /api/analytics` and confirm `action_breakdown` is present and percentages sum to 100% per sector
- [ ] 4.3 Deploy to Modal backend and confirm live endpoint returns the new field
