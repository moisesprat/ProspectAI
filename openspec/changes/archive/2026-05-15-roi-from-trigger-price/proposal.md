## Why

ROI is currently computed against the entry-zone midpoint, which is a synthetic price not corresponding to any action ProspectAI actually took. The `trigger_price` field — the price at which the system suggested entering — is the only price that represents a real buy signal. Measuring ROI from the midpoint overstates wins when the trigger was at the top of the zone and understates them when it was at the bottom, and produces "wins" for records where the system never actually told a user to buy.

## What Changes

- ROI is computed as `(current_price - trigger_price) / trigger_price * 100`, using the stored `trigger_price` as the basis.
- **BREAKING** Records without a `trigger_price` are excluded from the response (they have no real buy basis). Older entries that predate the `trigger_price` contract will no longer surface as "wins."
- The `entry_zone_low` and `entry_zone_high` fields remain in the response payload (used by the UI for context if needed), but no longer participate in ROI computation.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `long-buy-wins-api`: "ROI computation uses entry zone midpoint" requirement is replaced with a trigger-price-based formula; the response no longer includes records lacking `trigger_price`.

## Impact

- `prospectai-backend/serve.py` — `GET /api/long-buy-wins` filter and ROI formula updated. Modal redeploy required.
- `prospectai-web` — no code change needed (UI already renders `trigger_price`-aware price row).
- No Modal Dict schema change; older records remain in storage but are filtered out.
