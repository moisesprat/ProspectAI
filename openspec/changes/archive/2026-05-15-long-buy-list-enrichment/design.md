## Context

The `/api/long-buy-wins` endpoint already returns `trigger_price` (optional) and `current_price` per item. The frontend win card currently renders only ticker, sector, ROI %, and relative time. Users have no signal that these picks came from ProspectAI as LONG-BUY actions, nor do they see the suggested entry price vs today's price side by side.

## Goals / Non-Goals

**Goals:**
- Surface `recommended_action` in the API response so the UI can render it without hard-coding the string "LONG-BUY."
- Update the win card to show: recommendation label, suggested entry price (conditional), and current price.

**Non-Goals:**
- Changing ROI calculation logic or filtering rules.
- Modifying the Modal Dict schema or backfill scripts.
- Adding new API endpoints.

## Decisions

### D1 — Add `recommended_action` to API response rather than hard-coding in UI

**Decision:** The backend adds `"recommended_action": "LONG-BUY"` to each item in the `/api/long-buy-wins` response.

**Rationale:** The dict stores only LONG-BUY entries today, but future changes could add other action types to the same store. Returning the field from the API makes the UI data-driven rather than dependent on an implicit assumption.

**Alternative considered:** Hard-code "LONG-BUY" in the frontend. Rejected — the API already owns the record and returning the field costs one line.

### D2 — Omit trigger price element entirely when null (not just hide with CSS)

**Decision:** The card renders no trigger price row when `trigger_price` is null. No placeholder text, no dash.

**Rationale:** Empty or "n/a" price rows create noise and confusion ("what does this mean?"). Omitting cleanly degrades for older records that predate the trigger price contract.

### D3 — Show `current_price` from API response (not re-fetched client-side)

**Decision:** The card reads `current_price` from the API response already computed by the backend via yfinance.

**Rationale:** Price is already fetched once per request; no client-side yfinance or additional API call needed. The value is always fresh (computed at request time).

## Risks / Trade-offs

- `current_price` is fetched at request time, not at card render time — on a slow connection the price shown may be a few seconds old. Acceptable for this use case.
- Records without `trigger_price` silently show less information. This is intentional (D2) but means older entries look slightly different from newer ones.

## Migration Plan

1. Deploy backend change (adds `recommended_action` field — purely additive, no breaking change).
2. Deploy frontend change (reads `recommended_action` and renders new card fields).
3. No rollback complexity — both changes are additive; old frontend ignores new field, old backend response still satisfies new frontend (trigger_price absent → row omitted).
