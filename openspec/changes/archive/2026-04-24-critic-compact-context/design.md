## Context

The Critic agent currently receives four context sections built by `critique_review()`:

```python
ctx = "\n\n".join([
    _fmt_ctx("Market Analysis Output",      _slim_market_for_strategy()),   # sector + 5 tickers × rationale
    _fmt_ctx("Technical Analysis Output",   _slim_technical()),             # sector + 5 tickers × indicators
    _fmt_ctx("Fundamental Analysis Output", _slim_fundamental()),           # sector + 5 tickers × grades
    _fmt_ctx("Draft Strategy Output",       _slim_draft()),                 # positions + allocations
])
```

The critic's checklist maps to two categories of checks:
- **Structural** (draft only): bucket sum, setup validity, R/R, trigger direction, allocation caps
- **Verification** (draft + specific raw values): RSI/Stochastic for overbought, sentiment for contradiction, valuation/health for ignored-risk

The full slim outputs contain far more than the Critic needs for verification checks, and risk encouraging the Critic to re-derive composite scores or re-assess investment theses rather than checking the draft's reasoning.

## Goals / Non-Goals

**Goals:**
- Replace the three upstream slim outputs in the Critic's context with a single compact per-ticker reference table.
- The reference table contains only the fields the Critic's checklist names explicitly: `rsi`, `stochastic_status`, `entry_zone_status`, `average_sentiment`, `valuation_grade`, `financial_health`, `momentum_score`.
- Keep the full `_slim_draft()` output as-is — the Critic needs all draft fields.
- Update `tasks.yaml` `critique_review` description to match the new context shape.

**Non-Goals:**
- Changing what the Critic checks or its output schema (`CriticOutput`).
- Changing how the Final Strategist builds its context (it still receives all slim outputs).
- Modifying any schema, agent, or tool file.

## Decisions

### D1: Reference table format — flat per-ticker JSON array

The reference table is a JSON array, one object per ticker, containing only the fields the Critic's issue-type checklist references by name:

```json
{
  "reference_table": [
    {
      "ticker": "NVDA",
      "rsi": 78.0,
      "stochastic_status": "Overbought",
      "macd_status": "Bullish",
      "entry_zone_status": "PULLBACK_ENTRY",
      "momentum_score": 8.1,
      "average_sentiment": 0.59,
      "valuation_grade": "VERY_EXPENSIVE",
      "financial_health": "STRONG"
    }
  ]
}
```

**Rationale:** Flat row-per-ticker mirrors how the Critic actually uses the data — one row per position under review. It is also the minimum possible context: no rationale prose, no full indicator sets, no investment thesis text.

**Alternatives considered:**
- Pass full slim outputs but add instructions to ignore irrelevant fields (rejected — LLM still processes and can be distracted by them)
- Separate sections per data type (rejected — increases formatting overhead for the same data)

### D2: Field selection — only checklist-referenced fields

Fields included are determined by an audit of every named field in the Critic's issue-type checklist in `tasks.yaml`:

| Issue type              | Field needed            | Source model                        |
|-------------------------|-------------------------|-------------------------------------|
| OVERBOUGHT_IGNORED      | rsi, stochastic_status  | TechnicalAnalysisOutput             |
| ENTRY_ZONE_VIOLATED     | entry_zone_status       | TechnicalAnalysisOutput             |
| PRICE_IN_ZONE_WAIT      | entry_zone_status       | TechnicalAnalysisOutput             |
| FABRICATED_SIGNAL       | momentum_score, macd_status | TechnicalAnalysisOutput         |
| SENTIMENT_CONTRADICTION | average_sentiment       | MarketAnalysisOutput                |
| VALUATION_IGNORED       | valuation_grade         | FundamentalAnalysisOutput           |
| WEAK_FUNDAMENTALS_BUY   | financial_health        | FundamentalAnalysisOutput           |

Fields NOT included: raw ATR, SMA values, Bollinger Band, EV/EBITDA, revenue growth, full rationale text, investment thesis — none are referenced by name in the checklist.

### D3: New helper `_critic_reference_table()` in ProspectAIFlow

Builds the reference table from the three typed state models already populated by the time `critique_review()` runs:

```python
def _critic_reference_table(self) -> str:
    mo = self.state.market_output       # MarketAnalysisOutput
    to = self.state.technical_output    # TechnicalAnalysisOutput
    fo = self.state.fundamental_output  # FundamentalAnalysisOutput

    # Build lookup dicts keyed by ticker
    sentiment_by_ticker = {s.ticker: s.average_sentiment for s in mo.candidate_stocks} if mo else {}
    tech_by_ticker      = {a.ticker: a for a in to.technical_analysis}                  if to else {}
    fund_by_ticker      = {a.ticker: a for a in fo.fundamental_analysis}                if fo else {}

    tickers = list(tech_by_ticker.keys()) or list(sentiment_by_ticker.keys())
    rows = []
    for ticker in tickers:
        ta = tech_by_ticker.get(ticker)
        fa = fund_by_ticker.get(ticker)
        ri = ta.raw_indicators if ta else None
        ma = ta.momentum_analysis if ta else None
        sr = ma.support_resistance if ma else None
        fr = fa.fundamental_rating if fa else None
        rows.append({
            "ticker":            ticker,
            "rsi":               ri.rsi               if ri else None,
            "stochastic_status": ri.stochastic_status if ri else None,
            "macd_status":       ri.macd_status        if ri else None,
            "entry_zone_status": ma.entry_zone_status  if ma else None,
            "momentum_score":    ma.momentum_score      if ma else None,
            "average_sentiment": sentiment_by_ticker.get(ticker),
            "valuation_grade":   fr.valuation          if fr else None,
            "financial_health":  fr.quality            if fr else None,
        })
    return json.dumps({"reference_table": rows})
```

### D4: tasks.yaml critique_review description update

The `STEP 1` of the `critique_review` task currently instructs the Critic to "Read the context. Find 'stock_analyses'" etc. This needs to be rewritten to match the new compact format: "Read the reference_table. For each ticker, the following fields are provided for verification: rsi, stochastic_status, ..."

This is important: if the task description still references `stock_analyses` but the context only has `reference_table`, the Critic will be confused.

## Risks / Trade-offs

- **Missing field risk**: If a new issue type is added to the Critic's checklist that references a field not in the reference table, the Critic will silently have no data for that check. Mitigation: the reference table is built programmatically from typed models — adding a field is a one-line change, and the design doc explicitly lists which fields map to which checks.
- **fundamental_health field name**: `FundamentalRating.quality` maps to "STRONG/ADEQUATE/WEAK" via the quality_map. The reference table should expose the mapped value, not the raw Pydantic Literal ("High/Medium/Low"), to match what the Critic's task description expects.
- **tasks.yaml coupling**: The Critic's task description is tightly coupled to context field names. Changing the context shape without updating tasks.yaml will degrade Critic output quality even if the code is correct.

## Migration Plan

All changes are confined to `prospect_ai_flow.py` and `config/tasks.yaml`. No schema changes, no API changes. The existing `_slim_market_for_strategy()`, `_slim_technical()`, and `_slim_fundamental()` helpers are unchanged — they are still used by `final_strategy()`.
