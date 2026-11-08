# Spec: Semiconductor Sector Support

## Purpose

Define the Semiconductors sector as a first-class analysis target in ProspectAI, including its ticker universe, CLI accessibility, web UI representation, and analytics tracking. This capability separates semiconductor names from the Technology sector to enable focused chip-industry analysis.

## Requirements

### Requirement: Semiconductors sector ticker universe
The system SHALL define a `Semiconductors` sector in `utils.sector_universe.SECTOR_TICKERS` containing the following tickers: `NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `ASML`, `TSM`, `KLAC`, `LRCX`, `AMAT`, `ARM`, `SMCI`. No ticker in this list SHALL appear in any other sector's ticker list.

#### Scenario: Semiconductors sector returns correct tickers
- **WHEN** `SECTOR_TICKERS["Semiconductors"]` is read
- **THEN** it holds only tickers from the Semiconductors universe and no Technology-sector tickers

#### Scenario: Technology sector excludes semiconductor tickers
- **WHEN** `SECTOR_TICKERS["Technology"]` is read
- **THEN** none of `NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `SMCI`, `ARM` appear in it

#### Scenario: No ticker duplication across sectors
- **WHEN** all sector ticker lists are compared pairwise
- **THEN** the intersection of `Technology` tickers and `Semiconductors` tickers SHALL be empty

### Requirement: Technology sector includes IT services tickers
The Technology sector ticker list SHALL include IT services companies `EPAM`, `INFY`, `CTSH`, `ACN`, `WIT`, `IBM`, `GLOB`, `DXC` in addition to its existing software/internet/cloud names.

#### Scenario: IT services tickers are reachable via Technology sector
- **WHEN** `SECTOR_TICKERS["Technology"]` is read
- **THEN** `EPAM`, `INFY`, `CTSH`, `ACN`, `WIT`, `IBM`, `GLOB`, `DXC` are in it

### Requirement: Semiconductors sector accessible via CLI
The CLI `--sector` argument SHALL accept `Semiconductors` as a valid value and reject unknown sector names with a clear error.

#### Scenario: Valid Semiconductors sector runs pipeline
- **WHEN** `python3 main.py --sector Semiconductors` is executed
- **THEN** the full 6-phase pipeline runs and produces an `InvestorStrategicOutput` for the Semiconductors sector

#### Scenario: CLI help text includes Semiconductors
- **WHEN** `python3 main.py --help` is run
- **THEN** `Semiconductors` appears in the listed choices for `--sector`

### Requirement: Semiconductors sector card in web UI
The web frontend SHALL render a `Semiconductors` sector button in the sector selector grid, using `SOXX` as the representative ETF ticker.

#### Scenario: Semiconductors card is visible and selectable
- **WHEN** a user loads the ProspectAI web app
- **THEN** a sector card labelled `Semiconductors` with ticker `SOXX` is rendered in the grid

#### Scenario: Selecting Semiconductors card enables Run button
- **WHEN** a user clicks the `Semiconductors` card
- **THEN** the card becomes selected and the Run Analysis button becomes enabled

#### Scenario: Run Analysis sends correct sector to backend
- **WHEN** a user selects `Semiconductors` and clicks Run Analysis
- **THEN** the frontend sends `sector=Semiconductors` in the `/api/analyze` query string

### Requirement: Semiconductors analytics tracked automatically
The backend analytics store SHALL record a run count for `Semiconductors` using the same mechanism as all other sectors — no backend code change is required.

#### Scenario: Analytics counter increments for Semiconductors
- **WHEN** a Semiconductors analysis completes successfully
- **THEN** `GET /api/analytics` returns a `by_sector` entry for `Semiconductors` with a count ≥ 1
