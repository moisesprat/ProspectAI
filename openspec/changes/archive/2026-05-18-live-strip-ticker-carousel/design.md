## Context

The `recentWins` component (`ui/recentWins.js` + `.recent-wins` CSS) fetches `/api/long-buy-wins` and renders a horizontal row of cards. Currently the row is a `flex` container with `overflow-x: auto` — cards are static and the user must swipe/scroll to see them all. The goal is to replace this with a CSS marquee that animates continuously without JS timers or external libraries.

## Goals / Non-Goals

**Goals:**
- Infinite right-to-left scroll using a pure CSS `@keyframes` marquee
- Seamless loop — no visible jump or blank gap at wrap point
- Pause on hover to let users read a card
- Works correctly when there is only 1 card (edge case: enough duplicate cards to always fill the viewport width)
- No new npm dependencies

**Non-Goals:**
- Touch/drag-to-scrub interaction
- Variable scroll speed controls exposed to the user
- Changes to card content, styling, or the backend API

## Decisions

### 1 — Pure CSS animation over JS `requestAnimationFrame`

CSS `@keyframes` with `animation: marquee linear infinite` runs on the compositor thread — no JS event loop involvement, no jank during heavy React/LLM SSE updates. A JS loop would compete with the SSE stream processor.

**Alternative considered:** `IntersectionObserver` + `scrollLeft` — more control but heavier and unnecessary here.

### 2 — DOM duplication (2×) for seamless loop

The JS render function appends a clone of the card set inside the same track container. The `@keyframes` animation translates the track by exactly `-50%` (which equals one copy's width), then snaps back to `0` — visually seamless because the second copy is identical to the first.

**Alternative considered:** CSS `animation-fill-mode` with a very wide single track — breaks when card count is small and viewport is wide.

### 3 — Scroll speed: `30s` linear per cycle

A 30-second cycle feels natural for 8 cards (≈3.75 s/card visible dwell). Speed is set as a CSS custom property `--ticker-duration` on `.rw-track` so it can be adjusted in one place.

**Alternative considered:** Speed proportional to card count — more complex, no real UX benefit for the expected 4–12 card range.

### 4 — Overflow mask via `mask-image` gradient fade on edges

Left and right edges fade to transparent using `mask-image: linear-gradient(to right, transparent, black 5%, black 95%, transparent)`. This avoids a hard clip that would cut off the first/last card abruptly.

## Risks / Trade-offs

- **Single card edge case** → Mitigation: always duplicate at least 3× if `wins.length < 3` so the track is always wider than the viewport.
- **Reduced motion preference** → Mitigation: wrap animation in `@media (prefers-reduced-motion: no-preference)` so it only plays when the user hasn't opted out; falls back to the current static scroll.
- **Safari mask-image** → Mitigation: prefix with `-webkit-mask-image`.

## Migration Plan

1. Update `recentWins.js` to emit a `.rw-track` wrapper with duplicated cards.
2. Update `style.css`: add `@keyframes marquee`, `.rw-track`, and `.rw-cards` marquee layout; remove `overflow-x: auto`.
3. No server or build changes required.
4. Rollback: revert the two files; no data or schema impact.
