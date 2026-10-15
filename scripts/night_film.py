"""Night film timeline: one fixed camera on the pool lawn, a slow tilt from the lit house up to
Na Hiku with a gentle widening of the lens. Writes blender/timeline.json, used by
  - scripts/blender_render.py --plate   (the path-traced 360 night plate, cropped to what the move sees)
  - scripts/starpass.mjs                 (the real star field for each frame, from the walkthrough's sky)
  - scripts/night_composite.py           (frames = plate re-projected + stars + title)
"""
import json, math, sys
meta = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'blender/nahiku-meta.json'))
FT = 0.3048
fps, seconds = 24, 16
n = fps * seconds
pos = meta['night']['frames'][-1]['pos']                     # metres, three.js axes (y up)
house = [14 * FT, 7 * FT, 20 * FT]

# Na Hiku centre for the film's date at Kukui'ula (same formula as src/sky.js)
D = math.pi / 180
lat, lon = 21.895, -159.47
from datetime import datetime, timezone
date = datetime.fromisoformat(meta['night']['date'].replace('Z', '+00:00'))
jd = date.timestamp() / 86400 + 2440587.5
gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360
nx, ny = meta['night']['north']; ex, ey = -ny, nx
stars = [[165.93, 61.75], [165.46, 56.38], [178.46, 53.69], [183.86, 57.03], [193.51, 55.96], [200.98, 54.93], [206.89, 49.31]]
cx = cy = cz = 0
for ra, de in stars:
    H = (gmst + lon - ra) * D; d = de * D; p = lat * D
    U = math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(H)
    N = math.cos(p) * math.sin(d) - math.sin(p) * math.cos(d) * math.cos(H)
    E = -math.cos(d) * math.sin(H)
    cx += N * nx + E * ex; cy += U; cz += N * ny + E * ey
L = math.sqrt(cx * cx + cy * cy + cz * cz); cx, cy, cz = cx / L, cy / L, cz / L
star_yaw, star_pitch = math.atan2(cz, cx), math.asin(cy)
hx, hy, hz = house[0] - pos[0], house[1] - pos[1], house[2] - pos[2]
house_yaw, house_pitch = math.atan2(hz, hx), math.atan2(hy, math.hypot(hx, hz))

ease = lambda t: t * t * (3 - 2 * t)
clamp = lambda t: max(0.0, min(1.0, t))
frames = []
for i in range(n):
    t = i / (n - 1)
    k = ease(clamp((t - 0.22) / 0.6))
    frames.append(dict(
        yaw=house_yaw + (star_yaw - 0.03 - house_yaw) * k,
        pitch=house_pitch + 0.03 + (star_pitch - 0.2 - house_pitch - 0.03) * k,
        fov=44 + (60 - 44) * ease(clamp(t / 0.85)),
        lines=0.32 * ease(clamp((t - 0.74) / 0.14)),
        caption=ease(clamp((t - 0.8) / 0.12)),
        twinkle=t * seconds,
    ))
# angular extent the move needs from the plate (with margin)
aspect = 16 / 9
def bounds():
    lons, lats = [], []
    for f in frames:
        vf = math.radians(f['fov']); hf = 2 * math.atan(math.tan(vf / 2) * aspect)
        lons += [f['yaw'] - hf / 2, f['yaw'] + hf / 2]; lats += [f['pitch'] - vf / 2 - 0.08, f['pitch'] + vf / 2 + 0.08]
    return min(lons) - 0.06, max(lons) + 0.06, max(-math.pi / 2, min(lats)), min(math.pi / 2, max(lats))
y0, y1, p0, p1 = bounds()
json.dump(dict(fps=fps, frames=frames, pos=pos, yawRange=[y0, y1], pitchRange=[p0, p1]), open('blender/timeline.json', 'w'))
print('frames', n, 'yaw', [round(math.degrees(v), 1) for v in (y0, y1)], 'pitch', [round(math.degrees(v), 1) for v in (p0, p1)])
