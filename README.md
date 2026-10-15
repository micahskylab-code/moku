# Nā Hiku walkthrough

A walkable, to-scale three.js model of the Nā Hiku spec home (the "Lot 25" design from the Nā Hiku
Buyer Preview Package), set on one of the fourteen Nā Hiku homesites at Kukuiʻula, Kauaʻi, with the
neighbourhood around it and the real night sky overhead.

```
npx http-server -c-1 .     # then open http://localhost:8080/
```

| URL parameter | what |
|---|---|
| `?time=night` | night: house lights, pool glow, the sky over Kukuiʻula on 19 Mar 2026, 9 pm HST |
| `?mode=fly` | start in the fly-over (orbit) view of the neighbourhood |
| `?view=<id>` | fixed camera from `viewpoints` (used by the critic loop) |
| `?q=low` | lighter rendering for phones (no ambient occlusion, smaller shadows) |
| `?hood=0` | skip the neighbourhood |

Walk: WASD / arrows + mouse (desktop), drag left/right halves (phone). The map jumps you to a room.

## Where the numbers come from

* **Floor plan** — `tools/gen_lot25.py`. Every wall, window and door is measured off the Lot 25 floor
  plan rendered at 300 dpi; scale 23 px = 1 ft, checked against the brochure's own areas
  (covered lānai 494 sq ft, ʻohana 352 sq ft, main house 2,300 sq ft).
* **Exterior** — the two exterior renderings: Dutch-hip standing-seam roofs with louvered gablets,
  white lap siding, black window frames, wood shutters and lānai beams, the shuttered ʻohana and the
  cedar carriage-door garage pavilions either side of the walk, infinity pool and spa over a
  coral-stone retaining wall. The garage is not on the plan; it is modelled from the rendering.
* **Interior** — the interior design concept board: white oak, cane, coral stone, white
  board-and-batten walls, tongue-and-groove vaulted ceilings, black fixtures, teak outdoors.
* **Neighbourhood** — the Kukuiʻula site plan: the fourteen Nā Hiku homesites between the Nā Hiku
  road and fairway 7, built as this spec design; golf holes, ponds, the ag field, and the Kaimalino,
  Kaupili, Kāhela and Aepo Nei homesites as massing.
* **Night sky** — real star positions (d3-celestial / Yale Bright Star catalogue, BSD) computed for
  Kukuiʻula's latitude/longitude and the chosen date; Nā Hiku (the Big Dipper) stands ~33° up in the
  north-north-east, over the house as seen from the pool.

## Builder / critic loop

1. `python3 tools/gen_lot25.py` regenerates `plans/lot25.json`.
2. `node scripts/shoot.mjs lot25 [view ...]` renders viewpoints to `shots/lot25/`.
3. A critic with fresh context compares each shot with its reference (`ref/`, not committed) and names
   the biggest gap; fix, re-shoot, repeat.
4. `node scripts/video.mjs lot25 night` renders the night film to `shots/lot25-night.mp4`.

## Photoreal renders (Blender Cycles)

The browser model is real-time; for photographs the same scene is path traced in Blender
(`pip install bpy`, CPU, OpenImageDenoise, AgX):

```
node scripts/export.mjs lot25                       # scene -> blender/nahiku.glb + nahiku-meta.json
python3 scripts/blender_render.py blender/nahiku.glb blender/nahiku-meta.json shots/cycles \
    --views front back great-room kitchen --samples 256 --res 1920x1200
```

* `scripts/blender_render.py` gives the scene physical sky and sun, refracting glass and water,
  translucent leaves and filmic tone mapping.
* `scripts/palms.py` regrows every palm (ours and the other thirteen lots) leaf by leaf: ringed
  trunks, crownshafts, foxtail and areca fronds of individual leaflets, fruit, dead fronds.
* **Night film:** `scripts/night_film.py` (timeline), `--night --plate` (one path-traced 360° night
  plate), `scripts/starpass.mjs` (real star field per frame), then `scripts/night_composite.py` →
  `shots/lot25-night.mp4`.
* **360° tour:** `--panos tour/panos.json` renders equirectangular panoramas to `tour/`;
  `tour.html` shows them with hotspots between rooms.

The brochure's images, plans and the site plan are the developer's copyright ("no content may be
copied, republished, posted or distributed without prior permission"). They are used here only as
reference and are not in this repository. Get the developer's permission before publishing this
model.
