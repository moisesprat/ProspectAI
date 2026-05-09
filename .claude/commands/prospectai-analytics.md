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
```

If the request fails, print: `Analytics unavailable — Modal backend did not respond.`
