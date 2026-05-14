## ADDED Requirements

### Requirement: Backend emits keep-alive comments during idle periods
The `event_stream` generator SHALL yield an SSE comment line (`: heartbeat\n\n`) at most every 20 seconds when no real event has been enqueued, preventing proxy and browser idle-connection timeouts.

#### Scenario: Heartbeat sent when queue is idle
- **WHEN** no event is placed on the queue within 20 seconds
- **THEN** the generator yields `: heartbeat\n\n` and resumes waiting

#### Scenario: Heartbeat not sent when events are flowing
- **WHEN** events are enqueued faster than the 20-second window
- **THEN** the generator yields only real `data:` events and does not insert comment lines

#### Scenario: Stream terminates cleanly after sentinel
- **WHEN** the pipeline thread puts `None` onto the queue (sentinel)
- **THEN** the generator stops yielding and the response ends, regardless of heartbeat state

#### Scenario: Heartbeat is invisible to onmessage
- **WHEN** the client receives a `: heartbeat` line
- **THEN** the browser `EventSource` does not fire `onmessage` for that line
