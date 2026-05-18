## 1. CSS — Marquee animation

- [x] 1.1 Add `@keyframes marquee` that translates from `0` to `-50%` on the X axis
- [x] 1.2 Add `.rw-track` rule: `display: flex`, `width: max-content`, `animation: marquee var(--ticker-duration, 30s) linear infinite`
- [x] 1.3 Replace `.rw-cards` `overflow-x: auto` layout with a clip container (`overflow: hidden`, `width: 100%`) and remove scrollbar-hide rules
- [x] 1.4 Add `mask-image` + `-webkit-mask-image` edge-fade gradient on `.rw-cards` (5% → 95%)
- [x] 1.5 Add `.recent-wins:hover .rw-track { animation-play-state: paused }` hover-pause rule
- [x] 1.6 Wrap the animation declaration in `@media (prefers-reduced-motion: no-preference)` so reduced-motion users get the static scrollable fallback

## 2. JS — Track duplication in `recentWins.js`

- [x] 2.1 Extract card HTML generation into a helper `renderCards(wins)` that returns the cards markup string
- [x] 2.2 Compute a minimum repeat count: `Math.max(2, Math.ceil(6 / wins.length))` so single-card edge case always fills the viewport
- [x] 2.3 Wrap all card copies in a `<div class="rw-track">` instead of directly in `.rw-cards`; emit `repeatCount × 2` copies (×2 for the seamless loop duplicate)

## 3. Verification

- [ ] 3.1 Run `npm run dev` in `prospectai-web` and confirm the strip scrolls continuously right-to-left
- [ ] 3.2 Confirm hover pauses the strip and cursor-leave resumes from the same position
- [ ] 3.3 Confirm no blank gap at the loop wrap point
- [ ] 3.4 Test with browser devtools `prefers-reduced-motion: reduce` emulation — strip should be static and scrollable
- [ ] 3.5 Test with a mocked single-card response — strip should still fill the viewport width
