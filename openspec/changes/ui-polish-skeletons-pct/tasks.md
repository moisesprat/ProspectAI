## 1. CSS — Add skeleton styles to main page stylesheet

- [ ] 1.1 Add `.skeleton` class and `@keyframes skeleton-pulse` to `prospectai-web/styles/style.css` (same pattern as `stats.css`: opacity pulse 0.35 → 0.65 → 0.35, 1.4s infinite)
- [ ] 1.2 Add `.rw-skeleton` placeholder strip styles to `style.css`: a `recent-wins`-height row of 3 ghost card shapes with the same background as `.skeleton`

## 2. JS — Version tag skeleton in `analytics.js`

- [ ] 2.1 In `analytics.js` `render()`, replace the initial `v—` text of `#version-tag` with a skeleton span before the fetch: `versionEl.innerHTML = '<span class="skeleton" style="width:38px;height:13px;display:inline-block;vertical-align:middle;border-radius:2px"></span>'`
- [ ] 2.2 In `analytics.js` `refresh()`, on version fetch success set `versionEl.textContent = \`v${data.version}\``; on failure set `versionEl.textContent = 'v—'` (clears the skeleton either way)

## 3. JS — Runs count skeleton in `analytics.js`

- [ ] 3.1 In `analytics.js` `render()`, replace the `—` initial text inside `.analytics-count` with a skeleton span inline in the `innerHTML` template
- [ ] 3.2 In `analytics.js` `refresh()`, on analytics fetch success set `countEl.textContent = (data.total ?? 0).toLocaleString()` (already does this — verify it replaces the skeleton correctly by setting textContent which clears innerHTML)

## 4. JS — Recent wins skeleton in `recentWins.js`

- [ ] 4.1 At the top of `recentWins.js` `render()`, inject a `.rw-skeleton` placeholder div into `parent` before `beforeEl` (same insertion point as the real section)
- [ ] 4.2 After the fetch completes (success or failure), remove the `.rw-skeleton` element before rendering the real section (or returning if no wins)

## 5. JS — Remove counts from donut legends in `stats.js`

- [ ] 5.1 In `buildLegend()`, remove the `<span class="stats-legend-count">${sl.value}</span>` line — keep only dot, label, and percentage

## 6. QA

- [ ] 6.1 Verify version tag shows skeleton on load and is replaced by `v1.9.0` (or current version) when analytics resolves
- [ ] 6.2 Verify runs count shows skeleton on load and is replaced by the actual number
- [ ] 6.3 Verify recent wins area shows ghost placeholder cards while fetching, then real marquee (or nothing)
- [ ] 6.4 Verify risk profile donut legend shows "Aggressive · 75.9%" format with no raw count
- [ ] 6.5 Verify decisions donut legend shows "LONG-BUY · 62.3%" format with no raw count
