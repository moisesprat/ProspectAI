## ADDED Requirements

### Requirement: Live strip scrolls continuously from right to left
The recent-wins strip SHALL animate its card track horizontally from right to left in an infinite loop using CSS `@keyframes`, requiring no user interaction to reveal all cards.

#### Scenario: Marquee plays on page load
- **WHEN** the page loads and the API returns one or more wins
- **THEN** the card track SHALL begin scrolling from right to left within 100 ms of being inserted into the DOM

#### Scenario: Animation is seamless at loop boundary
- **WHEN** the first card set has fully scrolled off the left edge
- **THEN** the track SHALL snap back to its starting position without any visible blank gap or flicker

### Requirement: Marquee pauses on hover
The card track SHALL pause its animation when the user hovers over it, and resume when the cursor leaves.

#### Scenario: Hover pauses scroll
- **WHEN** the user moves the cursor over the `.recent-wins` section
- **THEN** the marquee animation SHALL be paused (cards remain stationary)

#### Scenario: Cursor leave resumes scroll
- **WHEN** the user moves the cursor away from the `.recent-wins` section
- **THEN** the marquee animation SHALL resume from the same position it paused at

### Requirement: Reduced-motion users see static scrollable strip
The marquee animation SHALL NOT play when the user's OS has `prefers-reduced-motion: reduce` set.

#### Scenario: Reduced-motion preference respected
- **WHEN** the user's system preference is `prefers-reduced-motion: reduce`
- **THEN** the strip SHALL render as a static horizontally scrollable row (prior behaviour) with no CSS animation

### Requirement: Edge fade masks hard clip on strip edges
The left and right edges of the strip SHALL fade to the page background colour so cards fade in/out rather than being cut off abruptly.

#### Scenario: Edge gradient applied
- **WHEN** the strip is visible
- **THEN** the leftmost and rightmost ~5% of the strip width SHALL be visually faded to transparent via a `mask-image` gradient

### Requirement: Strip fills viewport width regardless of card count
When fewer than 3 cards are returned by the API, the JS render function SHALL duplicate the card set enough times so the total track width always exceeds the viewport width, preventing blank space from showing during the loop.

#### Scenario: Single card duplicated to fill track
- **WHEN** the API returns exactly 1 win
- **THEN** the rendered track SHALL contain at least 6 copies of that card (3 copies × 2 for the loop duplicate)
