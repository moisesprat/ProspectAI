## 1. Data Preparation

- [x] 1.1 After `allHistory` is populated from `/api/long-buy-history`, extract unique non-null `sector` values and sort them alphabetically into a `sectorOptions` array
- [x] 1.2 Store `allHistory` (raw, pre-rule) at module scope so the sector dropdown can always re-filter from the full dataset

## 2. Sector Dropdown UI

- [x] 2.1 Add a `<select id="sector-filter">` element above the KPI cards in the Performance tab HTML (or inject it dynamically on tab render)
- [x] 2.2 Populate the dropdown with "All Sectors" as the first `<option>` followed by each entry in `sectorOptions`
- [x] 2.3 Hide or disable the dropdown when `sectorOptions` is empty (no sector data in history)

## 3. Filter Logic

- [x] 3.1 Extract a `getFilteredHistory(sector)` helper that returns `allHistory` filtered to `sector` (or all entries when sector is `"all"`)
- [x] 3.2 Wire the `"change"` event on `#sector-filter` to call `getFilteredHistory`, apply existing data rules (dedup + 5-day exclusion), and re-render KPI cards and table
- [x] 3.3 Ensure the initial render on tab activation uses "All Sectors" (passes full `allHistory` through data rules) to preserve current behaviour

## 4. KPI Cards

- [x] 4.1 Confirm that the four KPI card computation functions (Win Rate, Avg Return, Best Pick, Worst Pick) accept the filtered-and-ruled subset as their input rather than always reading from a global — refactor if they currently reference a global directly
- [x] 4.2 Verify KPI cards all display "—" when the filtered subset is empty (no qualifying entries)

## 5. Table and Subtitle

- [x] 5.1 Ensure the track record table render function uses the same filtered-and-ruled subset as the KPI cards (single source of truth per render cycle)
- [x] 5.2 Update the row-count subtitle to reflect the count of rows in the filtered-and-ruled subset
- [x] 5.3 Show "No signals yet for this sector." empty-state message in the table area when the filtered subset is empty

## 6. Verification

- [x] 6.1 Manual test: select "Technology" — KPI cards and table update to Technology entries only
- [x] 6.2 Manual test: switch back to "All Sectors" — full dataset restored
- [x] 6.3 Manual test: select a sector with no qualifying entries — all KPI cards show "—" and empty-state message appears, no JS error in console
- [x] 6.4 Manual test: "All Sectors" default on page load matches previous behaviour exactly
