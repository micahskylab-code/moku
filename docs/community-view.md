# Community view

The **Community** button (or `?mode=community`) lifts the camera over Kukuiʻula. The view flies in from high over the sea to the home, and you can orbit, pan and zoom across the whole community. It shows:
- real terrain;
- the reef in its surveyed depths (2013);
- roads, paths, pools, ponds, beaches and golf features;
- buildings and trees;
- pins for the places around.

Pick a pin to fly there. Its card gives the place's category, its straight-line distance from the home and its source. The live sky still runs, so the sun, the shadows and the time of day all work here too. Code: `src/community.js`. Data bake: `scripts/geo_community.py`.

**What it is:** a concept visualization: a map rendering of open public data. It is not an aerial photograph, it is not the developer's map, and nothing in it is copied from kukuiula.com. The home is this project's concept model, placed to ±25 m (register I-9). A soft gold tint with a feathered edge marks its modelled lot, and the home's card says what it is: the modelled lot, with an assumed size (61.5 × 184.4 ft, register I-6). It is not a surveyed lot line, and none is drawn. The home's pin reads "Concept home (modelled)". The other thirteen Nā Hiku homes are shown as assumed copies of this design (register I-14). They stand on lawns the bake paints over the modelled row; in 2025–26 imagery that strip is graded, unbuilt land. No surveyed lot lines, neighbourhood boundaries or views from the lot are shown or claimed.

## Why the ground is drawn rather than photographed
No sub-metre aerial imagery of Kukuiʻula could be used from this build environment:
- **USDA NAIP Hawaiʻi 2021–23** (0.6 m, public domain) is the right source, but every host that serves it was blocked. The hosts are `planetarycomputer.microsoft.com`, `naipeuwest.blob.core.windows.net`, `coastalimagery.blob.core.windows.net` and `imagery.geoplatform.gov`. The AWS copy charges the requester.
- **The state's Vivid imagery** is licensed from Maxar, and commercial use is not allowed.

So each half-metre tile is drawn from measured data:

| Layer | Source | Licence | Used for |
|---|---|---|---|
| Ground shape | USGS 3DEP 1 m lidar DEM, HI_FEMAR9Kauai_2019_D19 (2019–21), from `prd-tnm` on S3. Where the lidar has no ground on land, voids within 30 m of the sea (wave-washed rock, reef tops) take the topobathy below, and the rest take the 2 m merged DEM | Public domain | Mesh heights (5 m grid); normals at 1 m, so the live sun lights every bench, berm and gully |
| Seafloor | USACE NCMP 2013 Kauaʻi topobathy lidar, bare earth 1 m (NOAA Digital Coast 9335, AWS Open Data `noaa-nos-coastal-lidar-pds`). Gaps in the survey inside the sea, mostly under breaking surf, are filled from the depths around them; only beyond the survey's outer edge is depth estimated from the distance offshore. Patches the sea encloses where the lidar found no ground and the satellite sees no plants (reef tops awash, surveyed at about 0 m) are drawn as very shallow sea | Public domain | Sea colour from depth (light attenuated to the bottom and back; sand where the seafloor is smooth, reef where it is rough), surf on the reef crests, the shoreline |
| Colour | Copernicus Sentinel-2 L2A median mosaic, 10 m, 2023–26. Over the sea the near-infrared band is subtracted from the visible ones, which takes off the sun-glint and haze offset | Copernicus free and open: "Contains modified Copernicus Sentinel data 2023–2026" | Which cover each place has (grass, red earth, scrub, rough, fairway, sand, rock) and its tint over 25 m; the open sea's colour |
| Trees | Meta / WRI High Resolution Canopy Height Maps (Tolan et al. 2024), 1 m, resampled to the tiles and drawn as crowns, shading and shadows | CC BY 4.0 (modified) | Every crown, its shading and its shadow; which mapped ponds have grown over |
| Lines | OpenStreetMap through Overture Maps 2026-09-23: roads with class widths, paths, ponds, golf water hazards, pools, beaches, bare rock, golf course outlines; mapped fairways, greens, tees, bunkers and driving ranges. 29 road segments (about 3.7 km, class unknown, drawn as narrow paved roads) come from TomTom through Overture. A mapped pond is drawn as water only where the canopy map and the satellite still see open water (below) | ODbL 1.0 | Crisp edges |
| Buildings | OSM and Microsoft ML footprints (Overture), drawn from `geodata/features.json`: eave heights mostly guessed from footprint area, roof colours snapped from the 10 m satellite colour | ODbL 1.0 | 3D buildings in the view, and their shadows on the tiles |
| Places | OSM names (through Overture), and Overture places at confidence ≥ 0.9 | OSM entries ODbL 1.0; Overture places entries CDLA-Permissive-2.0 (`places.json` links both) | Pins (`geodata/community/places.json`) |

On wide screens the view's credits line is built from `community.json` `attribution` and `places.json` `attribution`. On small screens (≤600 px wide or ≤480 px tall) a short line names the main sources with the licences linked, and a Credits button opens the full list.

**Drawn, not measured:**
- Surface texture: grass grain, clods, sand ripples, leaf clumps, asphalt grain and mower stripes.
- The crisp edges between covers. They follow the satellite's own 10 m boundaries, roughened at the metre scale. Red earth's edges are softened over about 2 m and broken up, as grass thins into dirt.
- A floor on the tone of crowns: their colour is kept at about 4.5% reflectance in green or above, and under crowns and thickets the broad (9 m) baked occlusion is softened and nothing ends darker than about 3%, so tree-filled gullies keep their shape but read as forest rather than black under the live shadows.
- A rough canopy surface given to dense scrub, so that it takes light and shade.
- The modelled Nā Hiku row (the walkthrough's neighbourhood rectangle): a striped lawn under the 3D homes, over land that is bare graded soil in the 2025–26 imagery.
- The seafloor in the filled survey gaps: depth from the survey around each gap, and as rough as the reef around it.
- 3D buildings: footprints are mapped (OSM, Microsoft), but almost all heights are guessed from footprint area (10.5 ft a storey: one storey 10.5 ft, two 21 ft, three 31.5 ft; only about 0.6% of the footprints carry a height or floor count), roofs are drawn hipped, and roof colour is the 10 m satellite pixel snapped to one of five finishes.

**Kukuiʻula's golf turf is inferred.** Inside the Kukuiʻula course, OpenStreetMap maps the outline, its ponds, one green and the driving range, but no fairways, tees or bunkers. On a course where mapped fairways and driving ranges cover less than 5% of it, fairways are drawn where the 10 m colour is lighter than the course around them (60 m context), on tree-free, mown-looking grass. That applies to Kukuiʻula; Kiahuna's fairways are mapped and drawn from the map. Greens, tees, bunkers and driving ranges are drawn wherever they are mapped, at Kukuiʻula too.

**Mapped ponds that are no longer open water are drawn as land.** OpenStreetMap still maps reservoirs that have grown over: four in the gulches 1.9–2.4 km north-west and north of the home, one about 550 m north-north-east of it where trees stand in the outline, and a small pond under trees. It also maps a golf water-hazard outline along the shore about 700 m south-south-west of the home that is mown grass, and a pond near the coast about 1.4 km south-east of the home where the satellite sees land. A mapped pond is drawn as water only if both of these hold:
- trees (canopy height over 2 m) cover less than 15% of it;
- it is not both green in the satellite colour (Sentinel-2 NDVI median over 0.3; open water is below 0) and as bright as its banks in the near-infrared (median at least 0.75 of the land 10–30 m around it).

Water absorbs near-infrared whatever grows in it. Kukuiʻula's golf ponds are green with algae and only a few 10 m pixels across, so they read 0.35–0.7 in NDVI, but their near-infrared is between a fifth and three quarters of their banks', and they stay water. Ponds too small to hold a whole 10 m pixel are judged by the canopy alone. Eight outlines are left as land this way: they get no water paint, no pond water in `w_*.png` and no levelling in `h.bin`, and the ground there is drawn from the colour and the canopy like the land around it. Inside the ponds drawn as water, the canopy map's crowns are removed, so no crown, crown shading or shadow stands in the water.

## Tiles
The tiles are north-up UTM 4N squares of 1 km over E 447 500–453 500, N 2 418 000–2 423 000. That runs from Lāwaʻi Bay to Poʻipū, and from the sea to the Kōloa bypass. `geodata/community/community.json` gives the box, the transform to the walkthrough's world frame (feet), the channel encodings (`encoding`, and `sdfPerM`: the sea distance's steps per metre in `w_*.png`), the open sea's measured colour (`deepSea`, linear; the viewer draws the open sea in a lifted cobalt, below) and the credits.

| File | Size | Content |
|---|---|---|
| `a_c_r.webp` | 2048² | Albedo, 0.49 m per texel. Loaded for the nearest tiles |
| `s_c_r.webp` | 512² | The same albedo at 2 m per texel, loaded first and used for distant tiles |
| `n_c_r.webp` | 1024², lossless | Lidar ground and crown normals (east, north), and the height of what casts shadow: canopy and eaves, 0.1 m steps |
| `w_c_r.png` | 512² | R: signed distance to the sea's edge, 128 + 1 per metre (sea positive, ±127 m; `sdfPerM`). G: water in the ponds drawn as water. B: sea depth, 10 per metre |
| `h.bin` | 1200 × 1000 | Uint16 ground heights, 5 m, world feet; each pond drawn as water level at its lidar water surface, no higher than its bank. The hosted copy carries it as `h.b64.txt` |

## In the viewer
- **Ground:** each tile is a 10 m mesh (20 m on low quality). Inside the modelled neighbourhood's rectangle it carries that neighbourhood's heights, easing into the real ground over 300 ft; its outer 150 m eases into the walkthrough's real-site terrain. While the view is open, the walkthrough's own lot ground is hidden and the tiles carry the ground everywhere, so there is no hole. Inside the tile box the walkthrough's coarse real-site terrain is sunk below the tiles rather than clipped, so its valleys, which sit above the lidar ground, cannot show through; beyond the box it carries the ground as before. Both are restored on exit.
- **The modelled lot:** a soft gold tint with a feathered edge, drawn on the ground by the tile shader.
- **Shading:** the tile shader replaces the normals with the lidar's and traces each pixel's shadow across the height map toward the live sun (18 steps, up to about 30 m; 8 coarser steps, about 25 m, on low quality). Both fade out only at an edge a tile shares with a tile that has only its 2 m albedo, so no lighting seam shows there.
- **Water:** the sea and the ponds drawn as water get glassy, wind-rippled water. Swell rolls in over the shallow reef, its sets following the distance from the shore (stored out to 127 m), and breaks where it is shallowest; the swash moves at the shore. Its sun highlights are capped and its roughness has a floor (0.12 near, 0.5 far), so the ripples never sparkle into white specks.
- **The open sea, drawn:** the measured deep water (`deepSea`, about 0.003 / 0.009 / 0.025 linear) reads near black from the air, so the viewer draws the open sea in a cobalt lifted from it (0.006 / 0.025 / 0.09 linear, `uDeep` in `src/community.js`). Water deeper than about 10 m hands over to it by 24 m (the stored depth stops at 25.5 m, and the albedo's dark streaks run on below that); over the last 300 m of the box the whole sea takes it. The reef above 10 m keeps its baked colour.
- **Ponds:** a lighter teal-grey margin where the water meets its bank (the pond channel's anti-aliased edge), the water a shade lighter, and a little more of the sky in its reflection.
- **The sea beyond the tiles:** while the view is open, the walkthrough's sea beyond the tiles has the mosaic's glint and haze offset taken off, and all but its bright shallows take the same cobalt, so it meets the tiles' sea; the open-sea skirt to the horizon takes it too. The offset is read from the mosaic's smoothed red channel and is taken off only water near sea level. It is restored on exit.
- **The edge of the world:** inland (within about 65° of north from the home), the walkthrough's far terrain fades over its outer 4 km into the sky behind it (the sky texture and that frame's cumulus, so the dome shows through), and the sea skirt beyond it takes the sky's horizon haze: the island goes into haze instead of ending at a straight edge with a flat sea-level plane beyond. Seaward the skirt keeps a crisp sea horizon. Only while the view is open (`src/realsite.js`, gated by `SEA_LIFT`).
- **Streaming:** the nearest tiles stream in their 2048 px albedo and 1024 px normals (10 tiles); on low quality 4 tiles, at 1024 and 512 px. The rest stay at 2 m.
- **Light and grade (a sunny trade-wind day):** while the view is open, `src/daylight.js` applies the view's look (`main.js` switches it with the mode; nothing else changes it, and leaving the view gives every mode its own light back):
  - the haze thinned to 55% from the air, and by day tinted a light sky blue (at the haze's own brightness) instead of the horizon's grey; the low sky (within about 15° of the horizon) takes the same hue, so distant land fades into a sky of its own colour instead of standing out as a blue cut-out against a grey band;
  - the exposure raised by 40% by day (18% at night): an eye adapted to a bright sea and sky;
  - by day the sun a touch warmer (luminance kept), twice the sky's hemisphere fill, and a little bloom on highlights (not on low quality);
  - a display grade after the tone mapping (`src/grade.js`): darks lifted a little, vibrance (dull colours gain saturation, vivid ones hardly any), olive greens pulled a few degrees toward yellow-green with a little more colour and light;
  - the sky: rounder cumulus tops (`uDome` 0.3 against 0.06), each ray marched at most 4.5 km into the deck (low rays marched whole smeared each cloud into a column), no cirrus, at most about a quarter of the sky in cloud unless it is overcast, and no cloud bank over the mountains (its flat top read as a flat-topped mountain).
  
  The daytime parts fade out as the sun goes down (from 14° above the horizon to 1° below), so dusk, night and the night sky look as they do elsewhere.
- **The hero frame:** the flight in ends inland of the home (north-north-west of it on wide screens, north-west in phone portrait, about north in landscape), looking over the golf course and the home to the coast, the reef and the sea, with the horizon about a third down and sky above it, and the sun from the side. The home sits on a lower third point of the part of the screen the chrome leaves free (below the header, above a phone's bottom card, right of a card column); the target is solved for that with the view's own projection, so it holds on desktop, in phone portrait (closer, the home near the middle) and in landscape. Where the card stands as a column on the left (wide screens, and phones held in landscape) the view is centred in the space to its right.
- **Credits and notice:** the credits start with "Map rendering of open data, not an aerial photograph". On wider screens the line lists the bake's and the places' attribution with the licences linked. On small screens (≤600 px wide or ≤480 px tall) the card folds to its title (tap it to open), and a short credits line names the main sources with the licences linked; a Credits button opens the full list.
- **Labels:** pins are HTML labels. Overlapping ones give way by priority and distance, and each category can be switched off.

## Rebuild
```
python3 scripts/geo_dem1m.py          # USGS 1 m DEM over the box  -> <cache>/dem_comm_1m.npy
python3 scripts/geo_bathy.py          # USACE 2013 topobathy        -> <cache>/bathy_comm_1m.npy
python3 scripts/geo_overture.py <cache> base/land -159.515 21.86 -159.445 21.915   # beaches, bare rock
python3 scripts/geo_community.py      # all 30 tiles (about 3 min each), heights, community.json
python3 scripts/geo_community.py --only "2,2;1,2"   # some tiles (community.json lists the tiles on disk)
# two halves side by side (4 CPUs): --only with the tiles whose c + r is even, and another with the odd ones;
# each rewrites h.bin and community.json, identically, when it ends
node scripts/community_qa.mjs [out]   # screens: opening, establishing, overview, home, coast, golf
```
The other inputs (`s2_aoi.npz`, `dem_near_2m.npy`, `ov_*.json`, the canopy tile, `features.json`) are those of the real-site bake (`geodata/SOURCES.txt`). `places.json` is written by hand from OSM and Overture records.

## To add later
- Neighbourhood names (Aepo Nei, Kāhela, Kaimalino and others) as italic labels, marked "≈", placed at their OSM street names and with no boundaries. The Club Neighborhood, Kainani, Kaulu, Kahalawai and The Farm stay out unless their locations are confirmed.
- NAIP 0.6 m imagery (needs `planetarycomputer.microsoft.com` and `naipeuwest.blob.core.windows.net` allowed). Parcel or lot lines stay out: the view makes no boundary claims.
- 2019 lidar point clouds for true crowns, roofs and intensity (needs `rockyweb.usgs.gov` allowed).
