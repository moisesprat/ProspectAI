## Why

The live-strip currently renders as static cards that require manual horizontal scroll to see all picks. A continuously scrolling ticker — the canonical financial-UI pattern — makes the strip self-animating, immediately readable at a glance, and visually communicates that the data is live.

## What Changes

- Replace the static `rw-cards` flex row with a CSS `@keyframes`-based infinite marquee that scrolls the card track from right to left.
- Duplicate the card set once so the loop is seamless (no blank gap at the wrap point).
- Pause animation on hover so users can read or inspect a card without it moving.
- Remove the manual `overflow-x: auto` scroll behavior (superseded by the marquee).
- The JS render logic in `recentWins.js` injects the duplicate track; no backend changes.

## Capabilities

### New Capabilities
- `wins-ticker-marquee`: Continuously scrolling horizontal marquee for the recent-wins strip, with seamless looping and hover-pause.

### Modified Capabilities
<!-- No existing spec-level requirements change — this is a pure UI behaviour change on an existing component. -->

## Impact

- `prospectai-web/ui/recentWins.js` — adds DOM duplication for seamless loop
- `prospectai-web/styles/style.css` — replaces overflow-scroll layout with CSS marquee animation
- No backend, API, or schema changes
- No new dependencies (pure CSS animation)
