Fetch and display ProspectAI usage analytics from the Modal backend.

---

## Step 1 — Call the analytics endpoint

Run:
```
curl -s "https://moisesprat--prospectai-backend-fastapi-app.modal.run/api/analytics"
```

---

## Step 2 — Display results

Parse the JSON response and print a formatted summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ProspectAI Analytics
  Total runs : <total>
  Leading    : <leading_sector>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  By sector (sorted descending):
  <sector>: <count>
  ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  By risk profile:
  <profile>: <count>
  ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Action breakdown by sector:
  (only shown if action_breakdown is non-empty)

  <sector> (<total> recommendations):
  ACTION TYPE       COUNT   PCT
  LONG-BUY            <n>  <pct>%
  WAIT-FOR-ENTRY      <n>  <pct>%
  MONITOR             <n>  <pct>%
  AVOID               <n>  <pct>%

  (repeat for each sector that has action data, sorted by sector name)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Render action type rows only for action types that exist in the data (skip zero-count types).
Sort action types in the canonical order: LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID.

After the per-sector breakdown, if `action_totals.total > 0`, add a summary section:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Action totals (all sectors, <total> recommendations):
  ACTION TYPE       COUNT   PCT
  LONG-BUY            <n>  <pct>%
  WAIT-FOR-ENTRY      <n>  <pct>%
  MONITOR             <n>  <pct>%
  AVOID               <n>  <pct>%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Apply the same canonical sort order (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID) and skip zero-count types.

If `action_breakdown` is absent or empty, omit both the per-sector and totals sections entirely.

If the request fails, print: `Analytics unavailable — Modal backend did not respond.`
