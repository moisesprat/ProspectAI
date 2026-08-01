# sentiment-availability-sentinel Specification

## Purpose
Ensures that when sentiment data (Reddit and Serper fallback) is unavailable for a sector,
the pipeline treats it as explicitly missing rather than fabricating a neutral score —
propagating `sentiment_available=False` through Market Analysis, Composite Scoring, Critic
review, and the final report.

## Requirements

### Requirement: Sentiment unavailability is explicit, never a fabricated neutral score
`MarketAnalysisOutput` SHALL include `sentiment_available: bool` (default `True`). When
both `RedditSentimentTool` and the Serper fallback fail to produce sentiment data for the
sector, the Market Analyst SHALL set `sentiment_available=False` and SHALL set
`average_sentiment=null` for the affected candidates, rather than `0.0`.

#### Scenario: Both sentiment sources fail
- **WHEN** `RedditSentimentTool` sets `fallback_required=True` and the Serper fallback also
  fails
- **THEN** `MarketAnalysisOutput.sentiment_available` is `False` and `average_sentiment` is
  `null` for every candidate, not `0.0`

#### Scenario: At least one sentiment source succeeds
- **WHEN** `RedditSentimentTool` returns usable data
- **THEN** `sentiment_available=True` and `average_sentiment` holds the measured value

### Requirement: Composite scoring renormalizes when sentiment is unavailable
`CompositeScoreTool` SHALL check `sentiment_available` (or `average_sentiment=null`) per
stock. When unavailable, it SHALL compute `composite_score` from the technical and
fundamental components only, with their weights renormalized so the maximum attainable
score is still 100, rather than defaulting `sentiment_component` to a fixed value or
leaving the composite capped at 70.

#### Scenario: Composite score for a stock with unavailable sentiment
- **WHEN** a stock has `average_sentiment=null`, `momentum_score=8`, `financial_health=STRONG`,
  `growth_outlook=HIGH`
- **THEN** `composite_score` is computed from renormalized technical + fundamental weights
  only, and the response marks `fundamental_unknown=false` and includes an explicit
  sentiment-unavailable flag for that stock

### Requirement: Critic and report treat unavailable sentiment as out of scope, not neutral
When `sentiment_available=False`, the Critic SHALL NOT raise sentiment-based findings for
the affected candidates, and the final report SHALL render "sentiment: no data" for those
tickers instead of a sentiment-derived phrase.

#### Scenario: Critic does not fault a position for sentiment when data is unavailable
- **WHEN** a position's `sentiment_available=False`
- **THEN** the Critic's review SHALL NOT include a finding whose basis is the stock's
  sentiment score or trend

#### Scenario: Report renders unavailable sentiment explicitly
- **WHEN** a ticker in the final result has `sentiment_available=False`
- **THEN** the rendered report shows "sentiment: no data" for that ticker rather than a
  neutral-sentiment description
