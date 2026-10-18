# Community view

The **Community** button (or `?mode=community`) lifts the camera over Kukuiʻula. The view flies in from high over the sea to the home, and you can orbit, pan and zoom across the whole community. It shows:
- real terrain;
- the reef in its surveyed depths (2013);
- roads, paths, pools, ponds, beaches and golf features;
- buildings and trees;
- pins for the places around.

Pick a pin to fly there. Its card gives the place's category, its straight-line distance from the home and its source. The live sky still runs, so the sun, the shadows and the time of day all work here too. Code: `src/community.js`. Data bake: `scripts/geo_community.py`.

**What it is:** a concept visualization: a map rendering of open public data. It is not an aerial photograph, it is not the developer's map, and nothing in it is copied from kukuiula.com. The home is this project's concept model, placed to ±25 m (register I-9). A soft gold patch marks its modelled lot, and the home's card says what it is: the modelled lot, with an assumed size (61.5 × 184.4 ft, register I-6). It is not a surveyed lot line, and none is drawn. The home's pin reads "Concept home (modelled)". The other thirteen Nā Hiku homes are shown as assumed copies of this design (register I-14). They stand on lawns the bake paints over the modelled row; in 2025–26 imagery that strip is graded, unbuilt land. No surveyed lot lines, neighbourhood boundaries or views from the lot are shown or claimed.

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
| Trees | Meta / WRI High Resolution Canopy Height Maps (Tolan et al. 2024), 1 m | CC BY 4.0 | Every crown, its shading and its shadow |
| Lines | OpenStreetMap through Overture Maps 2026-09-23: roads with class widths, paths, ponds, golf water hazards, pools, beaches, bare rock, golf course outlines; mapped fairways, greens, tees, bunkers and driving ranges. 29 road segments (about 3.7 km, class unknown, drawn as narrow paved roads) come from TomTom through Overture | ODbL 1.0 | Crisp edges |
| Buildings | OSM and Microsoft ML footprints (Overture), with eave heights and roof colours from `geodata/features.json` | ODbL 1.0 | 3D buildings in the view, and their shadows on the tiles |
| Places | OSM names (through Overture), and Overture places at confidence ≥ 0.9 | OSM entries ODbL 1.0; Overture places entries CDLA-Permissive-2.0 (`places.json` links both) | Pins (`geodata/community/places.json`) |

The view's credits line is built from `community.json` `attribution` and `places.json` `attribution`.

**Drawn, not measured:**
- Surface texture: grass grain, clods, sand ripples, leaf clumps, asphalt grain and mower stripes.
- The crisp edges between covers. They follow the satellite's own 10 m boundaries, roughened at the metre scale.
- A rough canopy surface given to dense scrub, so that it takes light and shade.
- The modelled Nā Hiku row (the walkthrough's neighbourhood rectangle): a striped lawn under the 3D homes, over land that is bare graded soil in the 2025–26 imagery.
- The seafloor in the filled survey gaps: depth from the survey around each gap, and as rough as the reef around it.

**Kukuiʻula's golf turf is inferred.** Inside the Kukuiʻula course, OpenStreetMap maps the outline, its ponds, one green and the driving range, but no fairways, tees or bunkers. On a course where mapped fairways and driving ranges cover less than 5% of it, fairways are drawn where the 10 m colour is lighter than the course around them (60 m context), on tree-free, mown-looking grass. That applies to Kukuiʻula; Kiahuna's fairways are mapped and drawn from the map. Greens, tees, bunkers and driving ranges are drawn wherever they are mapped, at Kukuiʻula too.

## Tiles
The tiles are north-up UTM 4N squares of 1 km over E 447 500–453 500, N 2 418 000–2 423 000. That runs from Lāwaʻi Bay to Poʻipū, and from the sea to the Kōloa bypass. `geodata/community/community.json` gives the box, the transform to the walkthrough's world frame (feet), the channel encodings, the open sea's colour (`deepSea`, linear) and the credits.

| File | Size | Content |
|---|---|---|
| `a_c_r.webp` | 2048² | Albedo, 0.49 m per texel. Loaded for the nearest tiles |
| `s_c_r.webp` | 512² | The same albedo at 2 m per texel, loaded first and used for distant tiles |
| `n_c_r.webp` | 1024², lossless | Lidar ground and crown normals (east, north), and the height of what casts shadow: canopy and eaves, 0.1 m steps |
| `w_c_r.png` | 512² | Signed distance to the sea's edge, pond water, and sea depth |
| `h.bin` | 1200 × 1000 | Uint16 ground heights, 5 m, world feet; each pond level at its lidar water surface, no higher than its bank. The hosted copy carries it as `h.b64.txt` |

## In the viewer
- **Ground:** each tile is a 10 m mesh (20 m on low quality). Inside the modelled neighbourhood's rectangle it carries that neighbourhood's heights, easing into the real ground over 300 ft; its outer 150 m eases into the walkthrough's real-site terrain. While the view is open, the walkthrough's own lot ground is hidden and the tiles carry the ground everywhere, so there is no hole. The real-site terrain is clipped inside the tile box and shows only beyond it.
- **Shading:** the tile shader replaces the normals with the lidar's and traces each pixel's shadow across the height map toward the live sun (18 steps, up to about 40 m; 8 coarser steps and a nearer limit on low quality). Both fade out before the nearest tile that has only its 2 m albedo, so no lighting seam shows at a tile edge.
- **Water:** the sea and the ponds get glassy, wind-rippled water. Swell rolls in over the shallow reef and breaks where it is shallowest, and the swash moves at the shore.
- **Streaming:** the nearest tiles stream in at full resolution (10 on desktop, 4 on phones), and the rest stay at 2 m.
- **Haze and exposure:** the walkthrough's haze is thinned to 40% from the air, and the exposure is raised by 18% (an eye adapted to a bright sea and sky); both are restored on exit.
- **Credits and notice:** the credits line, built from the bake's and the places' attribution with the licences linked, starts with "Map rendering of open data, not an aerial photograph" and stays readable on every layout (on phones the card sits above it).
- **Labels:** pins are HTML labels. Overlapping ones give way by priority and distance, and each category can be switched off.

## Rebuild
```
python3 scripts/geo_dem1m.py          # USGS 1 m DEM over the box  -> <cache>/dem_comm_1m.npy
python3 scripts/geo_bathy.py          # USACE 2013 topobathy        -> <cache>/bathy_comm_1m.npy
python3 scripts/geo_overture.py <cache> base/land -159.515 21.86 -159.445 21.915   # beaches, bare rock
python3 scripts/geo_community.py      # all 30 tiles (about 2 min each), heights, community.json
python3 scripts/geo_community.py --only "2,2;1,2"   # some tiles (community.json lists the tiles on disk)
node scripts/community_qa.mjs [out]   # screens: opening, establishing, overview, home, coast, golf
```
The other inputs (`s2_aoi.npz`, `dem_near_2m.npy`, `ov_*.json`, the canopy tile, `features.json`) are those of the real-site bake (`geodata/SOURCES.txt`). `places.json` is written by hand from OSM and Overture records.

## To add later
- Neighbourhood names (Aepo Nei, Kāhela, Kaimalino and others) as italic labels, marked "≈", placed at their OSM street names and with no boundaries. The Club Neighborhood, Kainani, Kaulu, Kahalawai and The Farm stay out unless their locations are confirmed.
- County parcel lines (needs `maps.kauai.gov` or `services1.arcgis.com` allowed), and NAIP 0.6 m imagery (needs `planetarycomputer.microsoft.com` and `naipeuwest.blob.core.windows.net` allowed).
- 2019 lidar point clouds for true crowns, roofs and intensity (needs `rockyweb.usgs.gov` allowed).
