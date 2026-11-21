# GAMBIT interface

## Direction

**21 Nov, Abi (co-owner): grand-strategy game screen.** Abi wants the genre feel of browser war games and HOI4-style map games, not a dashboard: the map is the game. We take the genre's conventions and draw our own art (no copied maps, icons, unit art or layouts). The leaders must feel alive on the map, and judges should have things to hover and click.

- Full-bleed map: the sea fills the window behind floating glass panels; the continent stays centred between the rails.
- Terrain: procedural relief shading (soft-light over nation colours), seeded mountain, forest and hill glyphs per province, sea graticule and swell.
- Borders: thin dashed province lines; thick ink national borders computed from ownership, so they move with conquests. Large spaced nation names across each nation's territory.
- Units: military-map counters (infantry symbol, stacked by army strength) at capitals and on war fronts.
- Leaders on the map: portrait medallion at each capital with a mood ring (hostile/wary/neutral/friendly from relations or trust), a pulse when calling, the crisis decision tag, and a speech bubble: one leader speaks at a time, fresh statements first.
- HUD: icon resource bar with month-over-month change; nation list as leader cards (portrait, mood, relations, trust bar, protests); scrolling news wire.
- Crisis on the map: pulsing Port Kessar focus, the two grain ships waiting (they dock when a nation chooses dock), a storm.
- Code: `src/hud/` (Terrain, MapLayers, Icons, hud.css); tokens in `theme.ts`.

Earlier direction:

Tamim, Abi and Om share ownership of website design. List your in-progress files
in [Tamim's #26](https://github.com/Infosuii/Mistral-Hackathon/issues/26),
[Om's #27](https://github.com/Infosuii/Mistral-Hackathon/issues/27) or
[Abi's #28](https://github.com/Infosuii/Mistral-Hackathon/issues/28).

A political atlas viewed from a situation room. Cool sea, warm chart lettering,
and five clear territorial colours. The resource bar and operational panels sit
at the edges so the map takes up most of the screen. The phone uses signal red.
Barlow Condensed carries names and numbers, with Barlow for readable body copy.

## References

- `MASTER_PROMPT.md`, Tamim block, and `ideas.md` §12 for the screen and hierarchy.
- Browser grand-strategy games for map-first navigation. Geography and artwork are original.

### Run the site locally

From the repository root, with Node 22.12+ (or Node 20.19+ on the 20.x line):

```sh
git pull --ff-only origin main
cd web
npm ci
npm run dev
```

Open the URL Vite prints, normally [localhost:5173](http://localhost:5173/).
With the engine stopped, the page uses the [example state](../contracts/examples/state.json).
The checkout includes [map geometry](src/map.json), [flags and portraits](src/nations),
and the [phone widget](../voice/talk-button.js). The npm lockfile supplies the fonts.

For live world changes, crises and endings with stub leaders, open a second
terminal at the repository root and start the engine on port 8000. This mode
requires Python 3.12 and uses cached audio where available.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
MISTRAL_API_KEY= GAMBIT_AGENTS=stub VOICE_AUDIO_BASE=/api/audio \
  .venv/bin/python -m uvicorn engine.app:app --port 8000
```

Set `GAMBIT_EXTRA_CRISES=1`, `GAMBIT_MEDIATOR=1` or `GAMBIT_PRIVATE_STRATEGY=1`
on that last command to preview the optional screens. Start design work in
[theme.ts](src/theme.ts), [screen.css](src/screen.css) and [App.tsx](src/App.tsx).
Run `npm --prefix web run build` and the shared smoke check before merging.

## Decisions

- 2026-11-21 — (Abi) Grand-strategy pass: terrain map, unit counters, leader medallions with mood and speech, hover dossier cards, icon HUD, news wire, crisis focus. Interactivity (player actions from the map) proposed for Om.

- 2026-11-21 — The first view opens on Valdoria's seat with Ostrava selected. News is a paper dispatch at the bottom of the map.
- 2026-11-21 — `src/theme.ts` holds the visual tokens. `src/map.json` holds fixed geography, and the state supplies province ownership. The initial IDs and owners match `contracts/examples/state.json`.

- 2026-11-21 — Original SVG flag marks identify contacts. Leader portraits sit in the nation dossier.
- 2026-11-21 — Abi and Om joined Tamim as co-owners of the site design.

## Open questions

- How prominent should the phone be when a crisis starts?
- How much political detail should stay visible during a call?
