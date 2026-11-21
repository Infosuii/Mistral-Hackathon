# GAMBIT interface

## Direction

A political atlas viewed from a situation room. Cool sea, warm chart lettering,
and five clear territorial colours. The resource bar and operational panels sit
at the edges so the map takes up most of the screen. The phone uses signal red.
Barlow Condensed carries names and numbers, with Barlow for readable body copy.

## References

- `MASTER_PROMPT.md`, Tamim block, and `ideas.md` §12 for the screen and hierarchy.
- Browser grand-strategy games for map-first navigation. Geography and artwork are original.

## Decisions

- 2026-11-21 — The first view opens on Valdoria's seat with Ostrava selected. News is a paper dispatch at the bottom of the map.
- 2026-11-21 — `src/theme.ts` holds the visual tokens. `src/map.json` holds fixed geography, and the state supplies province ownership.

## Open questions

- How prominent should the phone be when a crisis starts?
- How much political detail should stay visible during a call?
