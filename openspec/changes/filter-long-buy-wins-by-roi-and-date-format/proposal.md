## Why

The "Recent Wins" strip on the web UI is meant to showcase ProspectAI's effective LONG-BUY picks, but it currently includes cards with marginal ROI (e.g., `+0.0%`), which undermines the credibility of the showcase. It also displays the recommendation date as fuzzy relative time (`today`, `2d ago`), which makes the picks feel ephemeral and obscures *when* the call was made. Showing a concrete calendar date next to the LONG-BUY tag and gating the strip on a meaningful profitability threshold makes the section read as a track record, not a feed.

## What Changes

- Backend `GET /api/long-buy-wins` filters out any record with `roi_pct <= 2.5` (currently filters only `roi_pct <= 0`). Threshold is a strict-greater-than-2.5% rule. **BREAKING** for any client expecting marginal-ROI items in the response.
- Frontend `recentWins.js` replaces the relative-time formatter with an absolute `dd-MMM-yy` formatter (e.g., `15-May-26`).
- Frontend card layout moves the recommendation date out of the sector row and renders it next to the `LONG-BUY` tag in row 1 (e.g., `MSFT   LONG-BUY · 15-May-26`). Row 2 becomes the sector alone.

## Capabilities

### New Capabilities
<!-- None — both affected capabilities already exist. -->

### Modified Capabilities
- `long-buy-wins-api`: the ROI inclusion threshold changes from `> 0%` to `> 2.5%`.
- `long-buy-wins-ui`: the date is rendered as `dd-MMM-yy` and placed next to the action tag; the sector row no longer carries a relative-time suffix.

## Impact

- **Code**: `prospectai-backend/serve.py` (`get_long_buy_wins` filter), `prospectai-web/ui/recentWins.js` (date formatter, card markup), and `prospectai-web/styles/*` if the row-1 layout needs spacing adjustments for the new date chip.
- **API contract**: response shape unchanged; the only difference is fewer items (records with `0 < roi_pct <= 2.5` are now excluded).
- **Empty-state behavior**: with a stricter threshold, the strip may render empty more often. Existing "no wins → don't render section" behavior is preserved and absorbs this.
- **Tests**: backend tests covering the win-filter threshold and frontend visual checks of the card layout.
- **Dependencies**: none added.
