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
| `?preset=` | `live` `sunrise` `golden` `sunset` `fullmoon` `stars` `winter` `summer` (see *Sun, moon and weather*) |
| `?date=2026-06-21T19:10` | any moment (HST unless a zone is given); or `?doy=172&hst=19:10` |
| `?wx=` | `clear` `partly` `cloudy` `rain` `windy`, or `?weather={"cloud_cover":60,...}` (Open-Meteo fields) |
| `?sunpath=1` | show the sun-path overlay (on by itself in the fly-over) |
| `?mode=fly` | start in the fly-over (orbit) view of the neighbourhood |
| `?view=<id>` | fixed camera from `viewpoints` (used by the critic loop) |
| `?q=low` | lighter rendering for phones (no ambient occlusion, smaller shadows) |
| `?hood=0` | skip the neighbourhood |

Walk: WASD / arrows + mouse (desktop), drag left/right halves (phone). The map jumps you to a room.

## Sun, moon and weather

The walkthrough opens on **Live**: the sky over the lot at this minute, Hawaiʻi time (HST, UTC−10, no
daylight saving), with the live weather. The panel at the bottom left takes it to any day of the year
and any minute; presets jump to sunrise, golden hour, sunset, the next full-moon night, the year's best
evening for Nā Hiku (the Big Dipper high over the house on a moonless night), and the winter- and
summer-solstice sunsets. “Night sky” goes to that Nā Hiku night and back, without reloading.

* **Sun and moon** — `src/ephemeris.js` with astronomy-engine (`vendor/astronomy.module.min.js`, MIT):
  topocentric positions with refraction, rise and set as the almanacs define them, golden hour
  (+6° to −4°), moon phase, illumination, distance, and the night of the Hawaiian lunar month.
  Checked against an independent NOAA/Meeus calculation (`scripts/sun_moon.py --table 2026`):

  | 2026, Kukuiʻula | sunrise | sunset | rises at | sets at |
  |---|---|---|---|---|
  | Mar equinox (20 Mar) | 6:41 am | 6:49 pm | 89.6° (E) | 270.6° (W) |
  | Jun solstice (21 Jun) | 5:55 am | 7:23 pm | 64.2° (ENE) | 295.7° (WNW) |
  | Sep equinox (22 Sep) | 6:26 am | 6:33 pm | 89.5° | 270.2° |
  | Dec solstice (21 Dec) | 7:12 am | 6:00 pm | 115.0° (ESE) | 245.0° (WSW) |

* **Light** — `src/atmosphere.js`: a spherical atmosphere with Rayleigh scattering, sea-salt haze and
  the ozone layer, single-scattered from the sun and the moon, plus a fitted multiple-scattering term
  for deep twilight (3.4 lux at −6°, 0.008 at −12°). It gives the sun's colour through the air at its
  altitude (white at noon, gold, then red at the horizon), the sky (`src/skydome.js`, rendered to a
  texture when the sun moves, and the scene's image-based light), the blue hour and the pink belt of
  Venus. The moon lights the night from its magnitude and phase; its disc is drawn at its true phase
  and tilt. Stars (`src/sky.js`) turn with sidereal time, fade by the naked-eye limit the sky's
  brightness allows (none at civil dusk, a few hundred under a full moon, thousands on a new moon), and
  hide behind clouds. Everything is computed in lux and cd/m² and then mapped the way an eye adapts
  (`key()` in `src/daylight.js`): sunset is ~3× darker than noon, the end of dusk ~8×; a full-moon
  night reads silver, a new-moon night dark. House, pool and garden lights come on through dusk.
* **Sun path** — `src/sunpath.js`: the chosen day's arc over the house with hour marks, the June and
  December arcs that bound the year, true north, and where the sun rises and sets.
* **Weather** — `src/weather.js`: Open-Meteo (`api.open-meteo.com`, no key) every 10 minutes, falling
  back to a typical trade-wind day (79 °F, ENE 14 mph gusting 22, a third of the sky in cumulus).
  Cloud cover sets the trade cumulus (ray-marched at half resolution, drifting with the wind, heavier
  over the mountains inland) and an overcast sky; a cloud crossing the sun dims it. Rain brings
  streaks, haze and wet, glossy paving and roofs (`src/rain.js`).
* **Wind** — `src/wind.js`: palm fronds, areca, shrubs and the distant palms bend downwind, sway, gust
  and flutter with the wind's speed and direction (one vertex-shader term, shadows included); the
  pool's ripples run downwind.
* **For the Blender renders** — `python3 scripts/sun_moon.py 2026-12-21T17:55 --meta blender/nahiku-meta.json`
  prints the sun and moon directions in the same world frame as `nahiku-meta.json` (`dir_three`, for
  `blender_render.set_sun`), Blender's frame, the sun's colour, the moon's phase and the day's events.

Stills keep the plan's fixed suns (`?view`, `?cam`, the films, the export) unless a sky parameter
(`?preset`, `?date` with `?dyn`, `?hst`, `?doy`, `?wx`, `?weather`, `?sunpath`) is given.

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
