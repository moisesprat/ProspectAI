## Why

Semiconductors — especially AI-chip makers (fabless designers, foundries, equipment suppliers) — are a distinct investment domain that is currently lumped into the Technology sector, diluting signal on both sides: software/SaaS stocks skew the sentiment data for chip plays, and chip-specific volatility distorts tech recommendations. With AI infrastructure spending accelerating, analysts need a dedicated Semiconductors sector that surfaces the right tickers and applies domain-appropriate evaluation criteria.

## What Changes

- Add `Semiconductors` as a first-class sector option in the ProspectAI pipeline.
- Define a curated ticker list for Semiconductors (ASML, TSM, NVDA, AMD, AVGO, QCOM, MRVL, ALAB, INTC, MU, KLAC, LRCX, AMAT) in `RedditSentimentTool.SECTOR_TICKERS`.
- **BREAKING** — Remove all semiconductor tickers from the `Technology` sector list so the two sectors are mutually exclusive.
- Expose `Semiconductors` in the CLI `--sector` argument.
- Add a `Semiconductors` sector selector in the `prospectai-web` frontend UI.
- Add `Semiconductors` support to the `prospectai-backend` analytics endpoint so historical runs for this sector are tracked and retrievable.

## Capabilities

### New Capabilities
- `semiconductor-sector`: Defines the Semiconductors sector — its ticker universe, sector label, and the guardrail that excludes software/internet tickers from this sector and semiconductor tickers from Technology.

### Modified Capabilities
- None — no existing spec-level requirements change; this is an additive sector entry.

## Impact

- **`utils/reddit_sentiment_tool.py`** — `SECTOR_TICKERS` dict: add `Semiconductors` key, remove semiconductor tickers from `Technology`.
- **`main.py`** — `--sector` choices list extended.
- **`prospectai-backend/serve.py`** — analytics sector filter must recognise `Semiconductors`.
- **`prospectai-web/ui/`** — sector selector component must include `Semiconductors` option.
- No schema changes, no new agents, no new tools.
