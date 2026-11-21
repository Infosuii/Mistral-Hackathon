# GAMBIT continuation prompt

Continue work in Infosuii/Mistral-Hackathon on branch om/map-decision-animations. Fetch main and check the diff and recent team decisions before integrating. The branch includes the atlas, construction, saves, diplomacy, Red Phone improvements, gameplay rail, and the latest continuous top-down art pass.

The user wants an original strategy map inspired by the supplied overhead city reference. Keep the normal campaign view as the only map surface. The city art should be visible at the starting scale, with densely built neighbourhoods, industrial zones, curving streets, motorways, interchanges, river bridges, railway stations, and airports. Clicking a city should show its connections and select its nation without changing the camera. The five starting countries should stay contiguous, and the authored atlas remains about 60% land and 40% water.

## Current implementation

- The latest production build passed. The previous atlas revision had 103 passing automated tests. Run the full suite and a fresh browser pass for the latest art pass.
- The separate city zoom scene and its button are removed. UrbanFabric draws neighbourhoods directly into all 40 provinces. The Biomes view and province hover cards expose boreal forest, woodland, highlands, farmland, floodplain, and dry coastal scrub.
- The atlas generator emits a shared river and road network. Motorway routes use land corridors, mark river crossings as bridges, and animate vehicles at biome-dependent speeds. Cross-border road traffic follows current trade and war status.
- Rail routes already credit actual resources each month. The airport sprites now have runways, terminals, and taxiways. Existing airfield aircraft still fly local patrol loops.
- The previous branch cut includes real fleet orders and blockades, capture animation, New Seed confirmation, construction, durable saves, History, News and intercepted dispatches.

## Continue from here

1. Open the ordinary Political map in Chromium at desktop and phone widths. Compare the full campaign view to the user's screenshot. Look for legibility at the starting scale, plausible city density, usable motorway hierarchy, and airports or bridges hidden beneath other markers. Verify city clicks leave the camera unchanged.
2. Make road logistics and airport-to-airport traffic part of gameplay. Use the atlas infrastructure data, actual district ownership, facilities, terrain and diplomatic links. Render traffic from those same rules. Test trade opening a route, war closing it, and land or water constraining its path. Keep existing rail income and save loading intact.
3. Refine urban layouts and infrastructure together in the normal map view. Prioritize connected neighbourhood streets, readable junctions and airport access. Check that river bridges visibly span the river rather than ending on water. Keep motion budget reasonable and preserve reduced-motion support.
4. Verify the frontend build, automated tests, and smoke flow before integrating. Preserve the existing One Berth crisis, alliance exits, construction, history, saves, and Red Phone controls.

## Working files and commands

- Atlas sources are web/scripts/generate-atlas.py and web/scripts/atlas_infrastructure.py. Generated data is web/src/atlas.json and data/{atlas_adjacency,sea_routes,rail,infrastructure}.json. Regeneration requires Shapely 2.1+ and GEOS 3.12+.
- Map entry is web/src/PoliticalMap.tsx. Urban fabric, road traffic, airports, and terrain are under web/src/hud in Cities.tsx, Infrastructure.tsx, and Terrain.tsx. Engine rail and construction are in engine/core.py.
- Run npm ci in web, then npm --prefix web run build from the repo root. Run python -m pytest -q engine/tests voice e2e and scripts/smoke.sh. Use scripts/demo.sh --offline for the local demo, or scripts/demo.sh with the configured Mistral key for live voice.
