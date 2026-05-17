## Context

The Recent Wins strip on the web UI is fed by `GET /api/long-buy-wins` (backend `serve.py:248`). The endpoint currently filters records on `roi <= 0`, so any pick whose current price is even fractionally above its trigger is eligible — including picks that round to `+0.0%` in the UI. The frontend (`recentWins.js`) then displays each pick with a relative-time stamp (`today`, `1d ago`, …) inside the sector row.

Two small problems compound:
1. The strip is a marketing showcase, but `+0.0%` cards weaken that signal.
2. Relative time hides *when* the call was actually made — useful context for evaluating a pick.

The change is intentionally narrow: tweak the backend threshold and replace the date formatter / move it into row 1 on the frontend.

## Goals / Non-Goals

**Goals:**
- Only LONG-BUY picks with `roi_pct > 2.5` appear in the `/api/long-buy-wins` response.
- Each card shows the recommendation date as an absolute `dd-MMM-yy` string (e.g., `15-May-26`) next to the `LONG-BUY` action tag in row 1.
- Row 2 becomes the sector alone, with no relative-time suffix.
- The empty-state UX (no section when there are no wins) is preserved.

**Non-Goals:**
- Tuning the ROI threshold beyond 2.5% (no per-sector or per-risk-profile threshold).
- Localizing the date string for non-English locales.
- Changing the cap of 5 returned wins.
- Reworking row 3 (ROI) or row 4 (price line).
- Adding a tooltip with the full timestamp.

## Decisions

### Decision 1: Filter ROI in the backend, not the frontend
Apply the `> 2.5%` threshold inside `get_long_buy_wins` rather than client-side.

**Rationale:** Keeps the API response self-describing (every item shown by *any* client is a real win), avoids shipping data only to hide it, and keeps the 5-item cap meaningful (5 *strong* winners, not 5 returned then 2 displayed).

**Alternative considered:** filtering client-side. Rejected — splits the contract definition across two repos and makes future clients re-implement the rule.

### Decision 2: Strict `> 2.5`, not `>= 2.5`
A pick exactly at `2.50%` is filtered out.

**Rationale:** The user originally requested "profitabilities of > 3%". After live data review (with `+2.89%` picks excluded under the 3% rule looking too restrictive against the current dataset), the threshold was lowered to `2.5%` at deploy time. Strict comparison matches the original phrasing convention and avoids edge cases at the cutoff. The values are already rounded to 2 decimal places, so the practical impact at the exact boundary is negligible.

### Decision 3: `dd-MMM-yy` format with English month abbreviation
Format: two-digit day, hyphen, three-letter English month (`Jan`…`Dec`), hyphen, two-digit year. Example: `15-May-26`.

**Rationale:** Compact (9 chars) so it fits in row 1 next to the tag, unambiguous across locales (unlike `05/15/26` vs. `15/05/26`), and matches common finance-UI conventions.

**Alternative considered:** ISO `2026-05-15`. Rejected — visually busier and reads as a database value rather than a human label. Could be revisited if users complain.

**Implementation:** build the string by hand from `Date.getUTCDate()`, a 12-element month-abbreviation array, and `Date.getUTCFullYear() % 100` (zero-padded). UTC is used so all viewers see the same date as the backend's stored `recommended_at`.

### Decision 4: Move the date into row 1, leave sector alone in row 2
Row 1: `<ticker>   <LONG-BUY tag>  ·  <date>`
Row 2: `<sector>` only.

**Rationale:** The user explicitly asked for the date "well shown next to long-buy label". Keeping row 2 as the sector preserves a clear two-line hierarchy (identity → category).

**Alternative considered:** keep the date in row 2 in place of relative time. Rejected — the user's request is specifically to surface the date next to the action label.

## Risks / Trade-offs

- **[Sparser strip]** With `> 2.5%`, the section will render empty more often during sideways markets. → Mitigation: existing "no wins → no section" behavior already handles this gracefully; no change needed.
- **[Date drift across timezones]** A pick made at `2026-05-15T23:30:00Z` could look like `16-May-26` to a UTC+1 viewer if we format in local time. → Mitigation: format using `getUTC*` methods so the date matches the backend's stored timestamp for every viewer.
- **[Layout overflow on narrow screens]** Adding a date chip to row 1 may cause wrapping on very narrow viewports. → Mitigation: keep the date string short (9 chars) and verify on a 320px test viewport; tweak `styles/recentWins.css` (or equivalent) only if needed.
- **[Test fixtures hardcode old threshold]** Any backend test that asserts a `+0.5%` pick appears in the response will break. → Mitigation: update fixtures in the same PR; covered in tasks. (New boundary tests target `2.4 / 2.5 / 2.51`.)

## Migration Plan

1. Land backend and frontend changes together (one PR per repo, or a coordinated pair).
2. No data migration: stored records are unchanged; only the *filter* changes.
3. Rollback: revert the two files (`serve.py` filter line, `recentWins.js` formatter + markup). No state to clean up.
