## 1. prospectai-backend — SSE heartbeat

- [x] 1.1 Replace the blocking `q.get()` call in `event_stream` with `asyncio.wait_for(loop.run_in_executor(None, q.get), timeout=20)` inside a `try/except asyncio.TimeoutError` block
- [x] 1.2 On `asyncio.TimeoutError`, yield `: heartbeat\n\n` and `continue` the loop (do not break or update any state)
- [x] 1.3 Verify the sentinel `None` still exits the loop cleanly after the change

## 2. prospectai-web — Client-side retry

- [x] 2.1 Add `let consecutiveErrors = 0` and `const MAX_ERRORS = 3` near the top of the `runAnalysis` promise block
- [x] 2.2 At the start of `source.onmessage`, reset `consecutiveErrors = 0` before processing the event; restore the normal status line if it was showing a "reconnecting" message
- [x] 2.3 Rewrite `source.onerror` to: if `streamSettled` → return; increment `consecutiveErrors`; if `consecutiveErrors < MAX_ERRORS` → call `panel.setStatusLine(...)` with "Connection interrupted — reconnecting (N/3)…" and return (do NOT call `finish()`); otherwise fall through to the existing failure path (set `streamSettled = true`, track error, show message, call `finish()`)

## 3. Deploy

- [x] 3.1 Commit backend change and run `modal deploy serve.py` from `prospectai-backend/`
- [x] 3.2 Commit web change and push to GitHub (Cloudflare Pages auto-deploys)
