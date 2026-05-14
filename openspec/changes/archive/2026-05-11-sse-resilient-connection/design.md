## Context

ProspectAI streams pipeline progress from a Modal/FastAPI backend to the browser via SSE (`EventSource`). A full pipeline run takes 5–15 minutes; between agents the stream can be idle for 1–3 minutes. Two bugs combine to cause `connection_failed`:

1. **Backend silence**: `event_stream` blocks on `q.get()` indefinitely. When no event is in the queue (LLM is processing), the SSE connection carries zero bytes. Proxies and browsers impose idle-connection timeouts (typically 60–120 s) and drop the socket.
2. **Frontend eagerness**: The `onerror` handler calls `finish()` and `source.close()` on the very first error event, defeating `EventSource`'s built-in reconnect. Even a one-second network blip kills the session permanently.

## Goals / Non-Goals

**Goals:**
- Prevent proxy/browser idle-timeout by keeping the SSE wire active during LLM processing gaps.
- Survive transient network interruptions (tab backgrounding, brief Wi-Fi drops) without showing an error.
- Give the user clear status feedback when a reconnect is in progress.

**Non-Goals:**
- Resume a pipeline run mid-execution after a long disconnect — requires server-side session state which is out of scope.
- Eliminate the error UI entirely — after sustained failure the user must still see a clear message.

## Decisions

### 1 — Backend heartbeat via SSE comments (not a `data:` event)

SSE specifies that lines beginning with `:` are comments and are forwarded to the client but do **not** fire `onmessage`. This is the standard mechanism for keep-alive. We use `: heartbeat` at 20-second intervals.

**Why 20 s?** Common proxy idle timeouts start at 60 s. A 20 s heartbeat leaves a comfortable margin. 

**Alternative considered**: Send a `data: {"type":"heartbeat"}` event and ignore it client-side. Rejected: adds parsing overhead and noise to the event log.

**Implementation**: Replace the blocking `q.get()` in `event_stream` with `asyncio.wait_for(…, timeout=20)`. On `asyncio.TimeoutError`, yield the comment line and continue.

### 2 — Client-side retry counter (max 3 consecutive errors)

`EventSource` transitions to `CONNECTING` on error and retries automatically — unless the application calls `source.close()`. The current code closes immediately. The fix: count consecutive `onerror` events; only close and fail after 3. Reset the counter on every successful `onmessage`.

**Why 3?** One retry handles a brief blip; two handles a slow reconnect; three is enough to distinguish "transient" from "sustained failure" without making the user wait more than ~30–60 s total.

**Alternative considered**: Use `Page Visibility API` to pause the counter when the tab is hidden and only start retrying when visible again. Adds complexity for marginal gain — the heartbeat already prevents most background drops. Deferred.

### 3 — Status line feedback during retry

When `onerror` fires but `errorCount < MAX_ERRORS`, update the panel status line to "Connection interrupted — reconnecting (N/3)…" so the user knows the system is still alive. On successful reconnect (next `onmessage`), restore the normal status.

## Risks / Trade-offs

- **Duplicate pipeline runs**: If the connection drops after the heartbeat has been silenced (e.g., Modal container cold-starts), `EventSource` auto-reconnect opens a new GET which starts a *new* pipeline. The backend pipeline from the dropped connection is orphaned but completes in its daemon thread (wasted compute, no user impact). Mitigation: the 3-retry window is short enough (~60 s) that in practice this only happens on hard failures.
- **Modal 900 s timeout**: The backend function timeout is 900 s. A pipeline that runs close to this limit cannot be saved by heartbeat alone. No change needed — this is a separate operational concern.
- **No version bump needed**: Both files (`serve.py`, `pipeline.js`) are deployed as source; no PyPI package change required.

## Migration Plan

1. Deploy updated `serve.py` to Modal (`modal deploy serve.py`).
2. Push updated `pipeline.js` to GitHub → Cloudflare Pages auto-deploys.
3. No database migrations, no breaking API changes, no rollback required — both changes are backwards-compatible (heartbeat comments are ignored by unmodified clients; old backends simply don't send them and the new client retries as before).
