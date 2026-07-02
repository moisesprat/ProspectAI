## Why

The Performance tab currently shows aggregate KPIs (Win Rate, Avg Return, Best Pick, Worst Pick) and the full track record table across all sectors, making it impossible to evaluate signal quality for a specific sector. Users need to isolate returns and win rate by sector to understand where ProspectAI performs best and where it needs improvement.

## What Changes

- Add a **sector filter dropdown** to the Performance tab, above the KPI cards and table.
- Default selection is **"All Sectors"**, preserving current behaviour.
- When a sector is selected, all four KPI cards **and** the track record table update client-side to show only entries matching that sector.
- The row-count subtitle updates to reflect the filtered count.
- The existing data rules (deduplication, 5-day exclusion, sorting) still apply within the filtered set.

## Capabilities

### New Capabilities
- `performance-sector-filter`: Sector dropdown that filters the Performance tab's KPI cards and track record table to a single sector (or all sectors). Computed entirely client-side from the already-fetched `/api/long-buy-history` response.

### Modified Capabilities
- `stats-performance-kpis`: KPI card computations must now accept a filtered subset of history entries (driven by the sector selection) rather than always computing over the full dataset.

## Impact

- **Frontend only** — `prospectai-web/stats.html` (JS + HTML).
- No backend or API changes required; sector data is already present in each `/api/long-buy-history` entry.
- No new dependencies.
