## Why

The current "Recent Wins" cards show ticker, sector, ROI, and time ago — but give no context about what ProspectAI actually recommended or at what price. Users can't tell whether they should have acted, or what the suggested entry price was versus what the stock trades at today.

## What Changes

- Each win card is relabelled to make clear the recommendation came from ProspectAI as a LONG-BUY action on a specific date.
- The suggested entry price (`trigger_price`) is shown on the card when available; the field is omitted entirely when the record has no `trigger_price`.
- The live current stock price is shown alongside the suggested entry price so users can compare "what ProspectAI said to buy at" vs "what it trades at now."

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `long-buy-wins-ui`: card content requirements change — must display recommendation label ("Recommended as LONG-BUY by ProspectAI · [date]"), conditional `trigger_price`, and current price.
- `long-buy-wins-api`: response schema change — must expose `recommended_action` field (always `"LONG-BUY"`) so the UI can render the label without hard-coding it.

## Impact

- `prospectai-backend/serve.py` — `GET /api/long-buy-wins` response schema: add `recommended_action: "LONG-BUY"` to each item.
- `prospectai-web` — win card component: updated copy, conditional trigger price row, current price row.
- No database / Modal Dict schema changes needed.
