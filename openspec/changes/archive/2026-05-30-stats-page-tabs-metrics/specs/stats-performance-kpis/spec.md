## ADDED Requirements

### Requirement: Performance tab displays four KPI cards above the track record table
The Performance tab SHALL render four headline KPI cards before the table: **Win Rate**, **Avg Return**, **Best Pick**, and **Worst Pick**. All values SHALL be computed client-side from the `/api/long-buy-history` response already fetched on page load.

#### Scenario: KPI cards populate when history data is available
- **WHEN** `/api/long-buy-history` returns 20 entries, 14 of which have a valid `roi_pct`
- **THEN** all four KPI cards are rendered with computed values before the track record table

#### Scenario: KPI cards show placeholders when history fetch fails
- **WHEN** `/api/long-buy-history` fails
- **THEN** all four KPI cards display "—" and no error is thrown

### Requirement: Win Rate computed as percentage of positive-ROI picks
Win Rate SHALL be `(count of entries where roi_pct > 0) / (count of entries where roi_pct is not null) * 100`, rounded to 1 decimal place, displayed as `X.X%`. If there are no entries with a valid ROI, the card SHALL show "—".

#### Scenario: Win rate with mixed results
- **WHEN** history contains 10 entries with valid ROI — 6 positive, 4 negative
- **THEN** Win Rate card displays `60.0%`

#### Scenario: Win rate with no valid ROI entries
- **WHEN** all entries have `roi_pct: null`
- **THEN** Win Rate card displays "—"

### Requirement: Avg Return computed as mean ROI across valid entries
Avg Return SHALL be the arithmetic mean of all non-null `roi_pct` values, rounded to 1 decimal place. Positive values SHALL be prefixed with `+`; negative with `−`. If no valid entries exist, SHALL display "—".

#### Scenario: Average return with positive mean
- **WHEN** valid ROI values are [10.0, 5.0, −2.0]
- **THEN** Avg Return displays `+4.3%`

#### Scenario: Average return with negative mean
- **WHEN** valid ROI values are [−5.0, −3.0, −10.0]
- **THEN** Avg Return displays `−6.0%`

### Requirement: Best Pick shows the highest-ROI entry
Best Pick SHALL display the ticker symbol and ROI percentage of the entry with the highest `roi_pct`. If no valid entries exist, SHALL display "—".

#### Scenario: Best pick identified correctly
- **WHEN** history contains entries including one with ticker "MU" and `roi_pct: 34.0`
- **THEN** Best Pick card shows "MU" and "+34.0%"

### Requirement: Worst Pick shows the lowest-ROI entry
Worst Pick SHALL display the ticker symbol and ROI percentage of the entry with the lowest `roi_pct`. If no valid entries exist, SHALL display "—".

#### Scenario: Worst pick identified correctly
- **WHEN** history contains entries including one with ticker "REGN" and `roi_pct: -15.0`
- **THEN** Worst Pick card shows "REGN" and "−15.0%"
