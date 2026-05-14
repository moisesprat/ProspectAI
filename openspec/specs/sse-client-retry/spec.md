## Purpose

Make the frontend resilient to transient SSE connection errors by tolerating up to 3 consecutive failures before surfacing a terminal error, and showing reconnecting status during the retry window.

## Requirements

### Requirement: Frontend tolerates up to 3 consecutive connection errors before failing
The `runAnalysis` function SHALL maintain a consecutive-error counter and only call `finish()` / surface `connection_failed` after 3 consecutive `onerror` events without an intervening successful `onmessage`.

#### Scenario: First onerror does not terminate the session
- **WHEN** `source.onerror` fires for the first time and `streamSettled` is false
- **THEN** the error counter increments to 1, a "reconnecting (1/3)" status is shown, and `finish()` is NOT called

#### Scenario: Successful message resets the error counter
- **WHEN** `source.onmessage` fires after one or two previous `onerror` events
- **THEN** the consecutive-error counter resets to 0 and the normal status line is restored

#### Scenario: Third consecutive onerror triggers failure
- **WHEN** `source.onerror` fires and the counter reaches 3 without any intervening `onmessage`
- **THEN** `streamSettled` is set to true, `trackAnalysisError` is called with `'connection_failed'`, the error message is displayed, and `finish()` is called

#### Scenario: onerror after streamSettled is ignored
- **WHEN** `source.onerror` fires after `streamSettled` is already true
- **THEN** no action is taken (existing behaviour preserved)

### Requirement: Frontend shows reconnecting status during retry window
The panel status line SHALL display "Connection interrupted — reconnecting (N/3)…" when `errorCount` is between 1 and 2 inclusive (retry window active).

#### Scenario: Status shown on first retry
- **WHEN** the first `onerror` fires and `errorCount` becomes 1
- **THEN** the panel status line reads "Connection interrupted — reconnecting (1/3)…"

#### Scenario: Status cleared on reconnect
- **WHEN** a successful `onmessage` is received after a retry-status was shown
- **THEN** the panel status line reverts to the normal processing status
