## Context

ProspectAI currently supports eight sectors. Sector membership is defined entirely in `RedditSentimentTool.SECTOR_TICKERS` (Python package); the CLI, backend analytics store, and web UI all derive their sector lists from this or mirror it manually.

The Technology sector currently contains semiconductor tickers (`NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `SMCI`, `ARM`) alongside pure-software names (`CRM`, `ORCL`, `ADBE`, `SNOW`, `PANW`, `CRWD`, `NET`, `DDOG`, `PLTR`, `NOW`). This mixing degrades signal quality in both directions.

Three codebases are involved:
- **Python package** — the authoritative source of sector definitions
- **`prospectai-web`** — static `SECTORS` array in `ui/data.js`; renders one `sector-btn` per entry
- **`prospectai-backend`** — analytics store is a free-form `modal.Dict` keyed by sector name string; no sector enumeration exists in backend code

## Goals / Non-Goals

**Goals:**
- Add `Semiconductors` as a fully functional sector in the Python package.
- Enforce mutual exclusivity: no ticker appears in both `Technology` and `Semiconductors`.
- Expose the new sector in the web UI's sector selector grid.
- Keep analytics working automatically for the new sector (no backend code change required).

**Non-Goals:**
- No new agents, tools, or pipeline phases.
- No changes to `prospectai-backend/serve.py` — the analytics store already accepts any sector string dynamically.
- No changes to `config/agents.yaml` or `config/tasks.yaml`.

## Decisions

### 1 — Ticker split between Technology and Semiconductors

**Semiconductors:** `NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `ASML`, `TSM`, `KLAC`, `LRCX`, `AMAT`, `ARM`, `SMCI`.

**Technology** (software, internet, cloud, IT services): `AAPL`, `MSFT`, `GOOGL`, `GOOG`, `META`, `AMZN`, `TSLA`, `CRM`, `ORCL`, `ADBE`, `PLTR`, `NOW`, `SNOW`, `ANET`, `PANW`, `CRWD`, `NET`, `DDOG`, `APP`, `UBER`, `EPAM`, `INFY`, `CTSH`, `ACN`, `WIT`, `IBM`, `GLOB`, `DXC`.

IT services additions rationale: EPAM (engineering services), INFY/CTSH/WIT (Indian offshore IT), ACN (Accenture — consulting + tech services), IBM (hybrid IT/cloud), GLOB (LatAm nearshore), DXC (managed IT services). These are pure-services plays with no chip design exposure, so they belong in Technology, not Semiconductors.

`NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `SMCI`, `ARM` are removed from the original Technology list and placed in Semiconductors.

### 2 — Subreddit expansion

`r/Stocks_picks` and `r/StockInvest` are added to **both** Technology and Semiconductors subreddit lists, extending reach to two additional investing communities.

**Technology subreddits:** `investing`, `stocks`, `wallstreetbets`, `technology`, `artificial`, `Stocks_picks`, `StockInvest`.

**Semiconductors subreddits:** `investing`, `stocks`, `wallstreetbets`, `hardware`, `chipdesign`, `Stocks_picks`, `StockInvest`.
Keywords for Semiconductors: `semiconductor`, `chip`, `foundry`, `fabless`, `wafer`, `EUV`, `lithography`, `GPU`, `AI chip`, `data center`, `HBM`, `packaging`.

Rationale: the two new subreddits are general stock-picking communities active on individual names; including them broadens coverage for both sectors without diluting sector-specific signal.

### 3 — Sector ETF ticker for the web UI
Use `SOXX` (iShares Semiconductor ETF) as the representative ticker displayed in the web selector card. This is the most widely recognised semiconductor benchmark.
Display name: `Semiconductors` (no abbreviation needed — fits the button).

### 4 — No backend code change needed
The `prospectai-backend` analytics store uses `analytics_store[sector]` with a plain string key. Adding a new sector value flows through automatically once the frontend passes `sector=Semiconductors` to `/api/analyze`. No `serve.py` change required.

## Risks / Trade-offs

- **Ticker ownership ambiguity** (`TSLA`, `AMZN`) — these multi-domain companies are left in Technology as the primary mapping. If a user wants chip-focused analysis, `Semiconductors` gives clean signal. → Acceptable trade-off; the separation goal is directional, not exhaustive.
- **Ticker duplication regression** — if any ticker appears in both lists, both sectors produce overlapping recommendations. → Mitigation: unit test asserts `set(Technology) & set(Semiconductors) == set()` after the change.
- **Web `data.js` sector name must exactly match backend sector string** — `name: 'Semiconductors'` in `data.js` must match what the Python package accepts. → Enforced by the single source of truth: `RedditSentimentTool.SECTOR_TICKERS` keys drive the CLI allowlist, and the web sends the name verbatim.
