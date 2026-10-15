# Source and asset index (for reuse and later integration)

Concept visualization of the Nā Hiku spec home (Lot 25 design). Estimated and assumed items are listed in
docs/assumptions-register.md. Nothing here is approved for publication: the brochure-derived plan and
renderings are the developer's copyright.

## Single source of truth → generated data
| Layer | Edit here | Produces |
|---|---|---|
| Floor plan, walls, openings, roofs, furniture, site, cameras | `tools/gen_lot25.py` (+ `tools/details_ext.py`, `tools/details_int.py`) | `plans/lot25.json` (`python3 tools/gen_lot25.py`) |
| Real site (terrain, ground colour, roads, footprints, trees) | `scripts/geo_*.py` | `geodata/*` (sources and licences in `geodata/SOURCES.txt`) |
| Photo texture + sky library | `scripts/fetch_assets.py` | `assets/` (`manifest.json`: source, CC0 licence, tile size; binaries not in git) |

## Geometry builders (three.js, world units feet)
`src/house.js` (slabs, posts, beams), `src/walls.js` (walls, openings, shutters, doors), `src/roof.js` (hip /
Dutch-gable roofs), `src/pool.js` (pool, spa, vanishing edge), `src/site.js` (terrain, retaining walls, planting
proxies), `src/furniture.js`, `src/details*.js`, `src/neighborhood.js` + `src/realsite.js` (surroundings),
`src/materials.js` / `src/textures.js` (named materials).

## Exportable model
`node scripts/export.mjs lot25 <dir>` writes `<dir>/nahiku.glb` (glTF 2.0, metres, materials named by finish)
and `<dir>/nahiku-meta.json`. The meta file holds cameras, with position, target, FOV, sun direction and an
interior flag; lamps, rooms and the pool; palm and plant proxies; and the night camera path.
The glb is the hand-off format for any engine or web viewer.

## Interactive model view (local only)
`src/inspect.js` builds the one-home model view: orbit, exterior / cutaway / translucent, selectable spaces, and
questions saved in the browser. `plans/lot25-spaces.json` holds the per-space SOURCE / ESTIMATE / ASSUMED / UNKNOWN
wording. `scripts/inspect_qa.mjs` is the headless QA, which writes screenshots and `qa.json` to `shots/model-view/`.
See docs/model-view.md.

## Photoreal pipeline (Blender 5.2 Cycles)
`scripts/blender_render.py` is the entry point. It calls:
- `scripts/materials_bpy.py`: photo materials, sky and exposure
- `scripts/palms.py` and `scripts/plants_bpy.py`: vegetation grown from proxies
- `scripts/water_bpy.py`: pool, spa and falls shading

`scripts/blender_slot.sh` limits concurrent renders. `scripts/photo_finish.py` applies the camera finish, and
`scripts/label_preview.py` adds the concept/assumption caption.

Night film: `scripts/night_film.py`, `scripts/starpass.mjs`, `scripts/night_composite.py`.
360° tour: `tour.html`, `src/tour.js`.

## Cameras (buyer views)
These are defined in `plans/lot25.json` → `viewpoints`:
- `front` and `back`: brochure framing, 1.9:1, suns at real dates
- `front-wide` and `back-wide`
- interiors: `great-room`, `kitchen`, `primary`, `lanai`, `primary-bath`, `bedroom-3`, `courtyard`

## Review documents
- `docs/audit-brochure.md`: critic gap list
- `docs/real-life-details.md`: construction and lived-in detail inventory
- `docs/assumptions-register.md`
