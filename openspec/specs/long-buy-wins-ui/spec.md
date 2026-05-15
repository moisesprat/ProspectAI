# Spec: long-buy-wins-ui

## Purpose

Render a "Recent Wins" section on the frontend that surfaces positive-ROI LONG-BUY picks from the last 30 days, displayed as horizontally scrollable cards.

## Requirements

### Requirement: Wins section renders on page load
The frontend SHALL fetch `GET /api/long-buy-wins` on page initialization and render a "Recent Wins" section if the response contains one or more items.

#### Scenario: Wins available
- **WHEN** the page loads and the endpoint returns 3 winning picks
- **THEN** a "Recent Wins" section appears between the header byline and the sample-preview section, showing 3 cards

#### Scenario: No wins available
- **WHEN** the page loads and the endpoint returns an empty array
- **THEN** no "Recent Wins" section is rendered (the space is not reserved)

#### Scenario: Endpoint unreachable
- **WHEN** the page loads and the fetch to `/api/long-buy-wins` fails (network error or non-200)
- **THEN** no "Recent Wins" section is rendered and no error is shown to the user

### Requirement: Each win card displays key data
Each card in the wins section SHALL display: the ticker symbol, the sector name, the ROI percentage (formatted with sign and 1 decimal place, e.g., "+9.5%"), and the time since recommendation (e.g., "3d ago", "2w ago").

#### Scenario: Card content
- **WHEN** a win item has `ticker: "MSFT"`, `sector: "Technology"`, `roi_pct: 4.21`, `recommended_at: "2026-05-10T07:00:00Z"`
- **THEN** the card displays "MSFT", "Technology", "+4.2%", and a relative time like "5d ago"

### Requirement: Cards are horizontally scrollable on mobile
The wins section SHALL render as a horizontal row that scrolls on viewports narrower than 640px and wraps naturally on wider viewports.

#### Scenario: Mobile viewport
- **WHEN** the viewport is 375px wide and there are 4 win cards
- **THEN** the cards overflow horizontally and the user can scroll to see all cards

#### Scenario: Desktop viewport
- **WHEN** the viewport is 1200px wide and there are 4 win cards
- **THEN** all cards are visible in a single row without scrolling

### Requirement: Section has a concise heading
The wins section SHALL include a heading line such as "Recent picks performing well" with a small disclaimer indicating these are past results (not guarantees).

#### Scenario: Heading and disclaimer
- **WHEN** the wins section is rendered
- **THEN** it shows a heading and a one-line disclaimer (e.g., "Past performance is not indicative of future results.")
