## 1. CSS — Sortable header styles

- [x] 1.1 Add `.col-sortable`, `.sort-arrow` and `.sort-arrow.active` styles to `stats.css`

## 2. HTML — Mark sortable column headers

- [x] 2.1 Add `class="col-roi col-sortable" id="th-roi"` and a `<span class="sort-arrow active">↓</span>` to the Return `<th>`
- [x] 2.2 Add `class="col-date col-sortable" id="th-date"` and a `<span class="sort-arrow">↕</span>` to the Signal Date `<th>`

## 3. JS — Sort state and logic

- [x] 3.1 Add a module-level `_perfHistory = []` cache and `_sort = { col: 'roi', dir: 'desc' }` state variable
- [x] 3.2 Add `sortHistory(history, col, dir)` that returns a sorted copy: ROI sort puts nulls last regardless of direction; date sort uses `recommended_at` timestamp comparison
- [x] 3.3 Add `updateSortHeaders(col, dir)` that sets the active header's arrow to ↓/↑ (amber) and the inactive header's arrow to ↕ (dim)
- [x] 3.4 Add `initSortHeaders()` that attaches click handlers to `#th-roi` and `#th-date`; each click toggles direction if same column or sets `desc` if switching column, then calls `renderHistory(sortHistory(...))` and `updateSortHeaders()`
- [x] 3.5 In `renderHistory()`, store the passed array into `_perfHistory` and call `initSortHeaders()` once (guard with a flag so handlers aren't re-attached on re-renders)
- [x] 3.6 Ensure KPI cards are NOT re-computed on sort (they're based on the filtered dataset, not the display order)

## 4. QA

- [x] 4.1 Verify default load shows Return ↓ active, rows sorted ROI desc
- [x] 4.2 Verify clicking Return toggles ↓→↑ and re-orders rows
- [x] 4.3 Verify clicking Signal Date sorts by date desc, Return shows ↕
- [x] 4.4 Verify null-ROI rows remain at the bottom when sorting by Return in both directions
