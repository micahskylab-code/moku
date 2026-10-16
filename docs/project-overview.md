# Project overview (start here)

The Nā Hiku walkthrough is a three.js model of the Nā Hiku spec home (the brochure's "Lot 25" design) at Kukuiʻula, Kauaʻi. It has:
- a walkable house on its site, with the neighbourhood and the real terrain;
- the real sun, moon and stars for any date, with weather;
- a model view for inspecting the home: orbit, cutaway and translucent displays, selectable rooms, and questions saved locally;
- a Blender/Cycles pipeline for photoreal stills.

**Status:** independent concept visualization. It is not construction or as-built documentation, not approved architecture, not produced or endorsed by the developer, and its views are not verified.
- The brochure floor plan (p6) has no dimensions. Every traced size is an estimate at a scale fitted to the stated areas (±3–8 % linear).
- The garage, the ʻohana's siting, the lot, the pool, the heights and the finishes are assumptions from the renderings.
- `docs/assumptions-register.md` lists every item as supplied, estimated or inferred.
- The plan data is traced from the developer's brochure. The brochure images themselves are not included.

## Run it
- **Viewer:** serve this folder over HTTP, e.g. `python3 -m http.server 8000` or `npx http-server -c-1 .`. Then open:
  - `http://localhost:8000/` for the walkthrough;
  - `http://localhost:8000/?mode=model` for the model view.

  Opening `index.html` as a file does not work: ES modules need HTTP. three.js r160 and astronomy-engine are vendored in `vendor/`, so no install is needed.
- **Regenerate the plan:** `python3 tools/gen_lot25.py` writes `plans/lot25.json`. Rooms, walls, openings, roofs, furniture, site and cameras are all defined in that script.
- **Headless tests:** `node scripts/inspect_qa.mjs`. Needs Playwright with Chromium; it writes screenshots and `qa.json` to `shots/model-view/`.
- **Export for path tracing:** `node scripts/export.mjs lot25 <dir>` writes `nahiku.glb` and `nahiku-meta.json`.
- **Photoreal render:** `blender -b -P scripts/blender_render.py -- ...` (Blender 5.x, Cycles). See `shots/preview4/run.sh` for a full front/back run with `scripts/photo_finish.py` and `scripts/label_preview.py`. The run scripts and `scripts/blender_slot.sh` contain absolute paths from the original build machine; edit them before use.
- **Photo textures and HDRIs:** `scripts/fetch_assets.py` downloads the CC0 library listed in `assets/manifest.json`. The textures are not included: they total about 850 MB, and only the Blender renders need them.

## Where things are
| Area | Files |
|---|---|
| Plan data (source of truth) | `tools/gen_lot25.py` (+ `tools/details_ext.py`, `tools/details_int.py`) → `plans/lot25.json` |
| Viewer entry, modes, camera, minimap | `index.html`, `src/main.js` |
| Model view | `src/inspect.js`, with per-room wording in `plans/lot25-spaces.json`. The display modes, room picking, info cards and local questions are documented in `docs/model-view.md` |
| House geometry | `src/house.js` (slabs, posts, beams), `src/walls.js`, `src/roof.js`, `src/furniture.js`, `src/details*.js` |
| Site | `src/site.js` (terrain, retaining walls, palms), `src/plants.js`, `src/pool.js` |
| Surroundings | `src/neighborhood.js` (the other 13 homes, mirrored and varied), `src/shell.js`, `src/realsite.js` (USGS lidar terrain, Sentinel-2 colour, OSM/Overture roads and buildings from `geodata/`) |
| Sky, light, weather | `src/ephemeris.js` (astronomy-engine), `src/daylight.js`, `src/atmosphere.js`, `src/skydome.js`, `src/sky.js` (stars), `src/sunpath.js`, `src/timepanel.js`, `src/weather.js` (Open-Meteo), `src/wind.js`, `src/rain.js` |
| Materials | `src/materials.js`, `src/textures.js` (procedural, for the viewer) and `scripts/materials_bpy.py` (photo materials for Blender) |
| Blender pipeline | `scripts/blender_render.py`, `scripts/palms.py`, `scripts/plants_bpy.py`, `scripts/water_bpy.py`, `scripts/photo_finish.py`, `scripts/label_preview.py` |
| Real-site data build | `scripts/geo_*.py` → `geodata/` (sources and licences in `geodata/SOURCES.txt`) |
| Private-page build | `scripts/build_artifact.py` (a hosted copy that loads three.js and astronomy-engine from jsDelivr) |
| Docs | `README.md` (URL parameters, sky and weather), `docs/assumptions-register.md`, `docs/model-view.md`, `docs/assets-index.md`, `docs/requirements-experience.md`, `docs/real-life-details.md`, and `docs/critique-*.json` (review scores and defects for each render round) |

## Conventions
- **World units:** feet, y up. Plan x maps to world x and plan y to world z. Room polygons are in plan feet.
- **Sun:** `[altitude, worldAz]`, with world azimuth measured from +x toward +z. True north is world azimuth 313.9°, and plan +x bears 46.3°.
- **Fixed sun:** stills and the export use each viewpoint's fixed sun. The interactive viewer uses the live sky.

## Open items
- Render round 5:
  - the back-view waterfall and catch basin;
  - a near tree that reads as CG;
  - a patchy lawn strip;
  - the back framing.

  Scores and details are in `docs/critique-preview4-*.json`.
- **Missing documents:** dimensioned plans, elevations and sections, the roof plan, the site plan or plat, and the landscape and pool plans. The window/door and finish schedules are missing too, so the matching labels say UNKNOWN or ASSUMED.
