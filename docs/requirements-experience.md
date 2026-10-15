# Future requirement: the experience *from* the home (recorded, not scheduled)

**Status: future brief.** It does not change the first milestone, which is the consolidated front/back concept preview plus critique.
No builders or renders are planned for it yet.

## Requirement (Micah)
An ultra-realistic, emotionally compelling experience seen from inside the Nā Hiku home: eye-level
interior and lānai views, sunset, moon and stars at night, and sun angles across seasons and years.

Later controls should cover:
- date and year, and local Hawaiʻi time (HST, UTC−10, no DST)
- sun azimuth and elevation in degrees
- sunrise and sunset times
- geolocated moon phase and position
- the star field
- realistic material and light transitions

Constraints:
- Ephemeris needs verified site coordinates, elevation and true-north orientation, with the assumptions stated.
- No guaranteed views.
- No fabricated terrain, neighbour or vegetation occlusion, weather or visibility.

## What already exists (do not re-implement)
These modules are built but not yet reviewed. The agent that wrote them was stopped before it reported.

| Need | Existing file | What it does |
|---|---|---|
| Ephemeris | `src/ephemeris.js` (astronomy-engine, MIT, vendored) | Sun and moon az/alt for any instant; topocentric moon, refraction, rise/set (upper limb), golden hour, moon phase. HST fixed |
| Python ephemeris (for Cycles stills) | `scripts/sun_moon.py` | Sun and moon directions in world coordinates for any ISO datetime, using true north from the meta |
| Physically based day/night light | `src/daylight.js`, `src/atmosphere.js` | One physical light scale for sun, sky, moon and airglow, mapped like eye or camera adaptation. Rayleigh, Mie and ozone sky. House lights at night |
| Sky, sun and moon discs, clouds | `src/skydome.js` | GPU sky texture, moon disc at true phase, image-based light, procedural cumulus and cirrus |
| Star field | `src/sky.js` (`makeNightSky`, `equatorialToWorld`) | Real star positions (d3-celestial / Yale BSC), Nā Hiku (Big Dipper) lines |
| Date and time UI | `src/timepanel.js` | Day-of-year and time sliders, presets, sun and moon times, Live mode |
| Sun-path study | `src/sunpath.js` | Day's arc with hour marks, solstice arcs, true-north ring, rise/set points |
| Wind and rain | `src/wind.js`, `src/rain.js` | Vertex sway by material name; rain streaks and wet surfaces |
| Weather | `src/weather.js` | Open-Meteo live data; `?wx=` / `?weather=` simulation |
| Night film (Cycles) | `scripts/night_film.py`, `scripts/starpass.mjs`, `scripts/night_composite.py` | Path-traced night plate plus the real star layer |
| Site frame | `geodata/realsite.json` | Lot lat/lon, true north, pad elevation, sea level |

## Gaps and conflicts with this brief (for later)
1. **Fabricated weather.** `weather.js` falls back to a simulated "typical trade-wind day" when live data fails, and `skydome.js` draws procedural clouds. That conflicts with "no fabricated weather or visibility". Later, default to a clear, labelled sky. Show live weather only from real data, labelled with its source and time.
2. **Year control.** The UI has day-of-year and time; an explicit year field and an az/el degrees readout still need checking or adding.
3. **Cycles stills by date/time.** `blender_render.py` takes a per-view `sunDir`, not a date/time. It needs a small hook to `sun_moon.py`. Night mode uses a fixed moon lamp; it needs the moon direction and phase from `sun_moon.py`.
4. **Star layer is stale.** `blender/stars` was rendered with the old true north and must be regenerated before any night output.
5. **Site inputs are not survey-verified:**
   - coordinates ±25 m, from imagery and lidar registration
   - pad elevation 17.6 m, from the USGS DEM
   - true north from the same registration (plan +x bearing 46.3°)

   For verified ephemeris, a site survey with coordinates and finished-floor elevation is needed (assumptions register I-9).
6. **Occlusion honesty.** The far-field terrain is real (USGS DEM). Neighbouring homes and planting are assumptions (I-13, I-14). Views from the home must be captioned "concept: surroundings partly assumed; views not guaranteed" (the brochure itself disclaims views).

## Keep compatible
- Cameras stay in `plans/lot25.json` viewpoints.
- Materials keep stable names (Blender and the three.js light transitions both key on them).
- The world frame and true north live only in `geodata/realsite.json` and `siteLayout()`.

## Next-phase buyer priorities (appended; not scheduled, no implementation yet)
**First**
- Eye-level camera presets for the living room (great room), primary bedroom and lānai. The `great-room`, `primary` and `lanai` viewpoints already exist in `plans/lot25.json`; they still need reviewing at eye height.
- A floor-plan overlay and camera locator showing where each view stands and looks. The model-on-plan overlay method already exists (`scratchpad/verify/plan_overlay.jpg`, script inline in the recovery log). The walkthrough minimap is a start.

**Later**
- Seasonal sun and shade on the outdoor areas (lānai, pool, lawn) across the year. This builds on `src/ephemeris.js`, `src/sunpath.js` and `scripts/sun_moon.py`.
- Labelled finish options that keep **confirmed inclusions** separate from **optional concepts**. No finish or inclusion may be shown as confirmed without a developer source: today only the p7 design board ("concept") exists, so everything is a concept (assumptions register I-12).
- Shareable saved views with question context, so a buyer can send a specific view and ask about it.
