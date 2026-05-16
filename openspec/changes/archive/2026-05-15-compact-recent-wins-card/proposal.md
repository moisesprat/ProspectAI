## Why

The just-shipped enrichment (label, trigger price, current price) inflated each Recent Wins card from 4 rows to 7, doubling its height and crowding the section. We compacted the live UI to 4 rows while preserving all information, but the synced main spec still describes the old verbose layout — implementation and spec have diverged.

## What Changes

- Recent Wins card layout is described as a 4-row compact arrangement: ticker + LONG-BUY tag (row 1), sector · relative-time (row 2), ROI (row 3), combined `$trigger → $current` price row (row 4, trigger omitted when null).
- Drop the verbose "Recommended as LONG-BUY by ProspectAI · [date]" label sentence from the spec — replaced by a compact `LONG-BUY` tag adjacent to the ticker.
- Drop the separate full-sentence trigger price row ("Entry suggested at $X.XX") and the standalone current price row — both are merged into a single price line with an arrow.
- No backend changes. No code changes — implementation already deployed (`prospectai-web` commit `fcdbc77`). This change is spec-only.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `long-buy-wins-ui`: "Each win card displays key data" requirement and its scenarios are rewritten to describe the compact layout instead of the verbose one.

## Impact

- `openspec/specs/long-buy-wins-ui/spec.md` — requirement text and scenarios updated to match live UI.
- No `prospectai-web` changes (already deployed).
- No `prospectai-backend` changes — API contract is unchanged.
