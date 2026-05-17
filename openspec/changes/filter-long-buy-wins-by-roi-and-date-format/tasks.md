## 1. Backend — `prospectai-backend`

- [x] 1.1 In `serve.py:get_long_buy_wins`, change the ROI inclusion guard from `if roi <= 0: continue` to `if roi <= 2.5: continue` so only picks with `roi_pct > 2.5` are appended to `wins`.
- [x] 1.2 Confirm the rounded `roi_pct` field on each item still rounds to 2 decimal places (`round(roi, 2)`) and that the 5-item cap on `wins[:5]` is unchanged.
- [x] 1.3 Update or add a unit / integration test that seeds the `long-buy-history` dict with `roi_pct` values around the boundary (e.g., `2.4`, `2.5`, `2.51`, `5.0`, `12.0`) and asserts only `> 2.5%` items are returned, sorted descending, capped at 5.
- [x] 1.4 Update any existing test fixtures or asserts that previously expected sub-3% picks in the response. (No pre-existing tests existed for this endpoint.)

## 2. Frontend — `prospectai-web/ui/recentWins.js`

- [x] 2.1 Replace the `relativeTime(isoString)` helper with `formatRecommendedDate(isoString)` that returns `dd-MMM-yy` using `Date#getUTCDate`, a 12-element month-abbreviation array (`Jan`…`Dec`), and `Date#getUTCFullYear() % 100` zero-padded to 2 digits. Day SHALL be zero-padded.
- [x] 2.2 Update the `rw-top` row markup so it renders the ticker, the action tag, and the formatted date (e.g., separated by a middle-dot) — the date sits visually adjacent to the `LONG-BUY` tag.
- [x] 2.3 Update the `rw-sector` row markup to render only `${w.sector}` — remove the ` · ${relativeTime(w.recommended_at)}` suffix.
- [x] 2.4 Verify no other reference to `relativeTime` remains in `recentWins.js` (delete the old function) and that no other UI file imports it.

## 3. Styles — `prospectai-web/styles`

- [x] 3.1 Adjust the row-1 (`.rw-top`) styles only if needed so the date chip wraps gracefully or fits beside the action tag on a 320px viewport. (Removed `justify-content: space-between`, added `flex-wrap: wrap` and `.rw-date` rule.)

## 4. Verification

- [x] 4.1 Backend: run the backend test suite locally and confirm the new threshold test passes and no regressions are introduced. (4/4 pass: `python3 -m pytest tests/ -v`.)
- [ ] 4.2 Frontend: start the web UI locally pointing at a backend instance that has at least one record with `roi_pct > 2.5`; visually confirm the card shows `<TICKER>  LONG-BUY · <dd-MMM-yy>` in row 1 and the sector alone in row 2.
- [ ] 4.3 Frontend: confirm picks with `roi_pct <= 2.5` no longer appear in the strip.
- [ ] 4.4 Frontend: spot-check date rendering for a record whose `recommended_at` is late-UTC (e.g., `23:30:00Z`) and confirm the displayed day matches the UTC date for viewers in both `UTC-5` and `UTC+2` timezones (devtools timezone override).
- [ ] 4.5 Frontend: confirm the empty-state behavior — when no records satisfy `roi_pct > 2.5`, the "Recent Wins" section is not rendered at all.

## 5. Release

- [ ] 5.1 Land backend and frontend changes together; coordinate deploy so the UI never queries an unfiltered backend with the new layout (or vice versa). Note: the change is forward/backward compatible in payload shape, so order is preference, not requirement. (Backend deployed to Modal on 2026-05-16 via `modal deploy serve.py`; web UI deploy still pending.)
- [ ] 5.2 Update release notes / `VERSION.md` if the project conventions require it for UI-visible changes. (Note: `VERSION.md` lives in the pipeline repo and tracks `prospectai` package releases; backend/web-only changes have not historically required a bump. Reconfirm with project owner before merging.)
