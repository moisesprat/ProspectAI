## Why

Pipeline runs intermittently show `connection_failed` when the user backgrounds the browser tab or the machine sleeps mid-run. Two root causes: (1) the backend SSE stream goes silent for minutes while LLMs process, causing proxies and browsers to drop the idle connection, and (2) the frontend immediately treats the first `onerror` event as fatal and closes the `EventSource`, defeating its built-in auto-retry.

## What Changes

- **Backend**: Emit an SSE keep-alive comment (`: heartbeat`) every 20 seconds when no real event is queued, preventing proxy/browser idle-connection timeouts.
- **Frontend**: Replace the "fail immediately on first error" `onerror` handler with a retry loop — tolerate up to 3 consecutive `onerror` events, showing a "reconnecting" status each time, and only surface `connection_failed` after all retries are exhausted.
- **Frontend**: Reset the error counter on every successful `onmessage`, so brief hiccups during a long run don't accumulate toward the failure threshold.
- **Frontend**: Detect `visibilitychange` (tab coming back to foreground) while retrying and update the status line to communicate reconnect state clearly.

## Capabilities

### New Capabilities
- `sse-heartbeat`: Backend emits periodic SSE comment lines to keep idle connections alive through proxies and browsers.
- `sse-client-retry`: Frontend retries on transient `onerror` events with a counter-based policy before declaring the connection permanently failed.

### Modified Capabilities

## Impact

- `prospectai-backend/serve.py` — `event_stream` generator: switch from blocking `q.get()` to a timeout-based loop that yields heartbeat comments when the queue is empty.
- `prospectai-web/ui/pipeline.js` — `runAnalysis`: replace the single-shot `onerror` handler with a counter-based retry handler; add `visibilitychange` listener.
- No API contract changes, no new dependencies, no version bump required.
