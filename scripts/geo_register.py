#!/usr/bin/env python3
"""Registration evidence: the painted site plan (src/neighborhood.js geometry, as laid out by
siteLayout) against the real place.

Anchor: the Na Hiku strip was graded in 2025-26 and shows as bare soil in every clear Sentinel-2
scene from June 2026 on (centre 450108 E 2420810 N, long axis grid bearing 135-138 deg, ~350 m long).
Our lot (7th of 14 from the north-west end) is placed on it, lot axis perpendicular to the strip.

The script reports how far the painted roads and ponds land from the real ones (OpenStreetMap via
Overture, Kukui'ula golf water hazards) for the plan scale K, and draws the overlay image.
    python3 scripts/geo_register.py <out.png> [K ...]
Needs in the cache: ov_segment.json, ov_land_use.json, ov_water.json (geo_overture.py), a Sentinel
TCI window tci_<scene>.png (444000..460000 E, 2414000..2428000 N) and dem1m.npy (lidar 1 m window).
"""
import json, math, sys, os
import numpy as np, pyproj
from shapely import wkb
from shapely.geometry import LineString, Point, Polygon
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import *

ll2utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32604', always_xy=True)
# bare-soil patch of the Na Hiku grading, PCA of the NDVI < 0.3 component in the Jun / Aug / Sep 2026
# scenes (S2C 20260611, S2C 20260820, S2B 20260914): centre, long-axis grid bearing, length, width (m)
STRIP = {'centre': (450108, 2420810), 'bearing': 136.3, 'length': 359, 'width': 149}
C = cache_dir()


def osm_named(names):
    out = {}
    for r in json.load(open(f'{C}/ov_segment.json')):
        n = (r.get('names') or {}).get('primary')
        if n in names:
            g = wkb.loads(bytes.fromhex(r['geometry']))
            xs, ys = ll2utm.transform(*np.array(g.coords).T)
            out.setdefault(n, []).append(LineString(list(zip(xs, ys))))
    return out


def water_hazards():
    out = []
    for r in json.load(open(f'{C}/ov_land_use.json')):
        if r.get('class') == 'water_hazard':
            g = wkb.loads(bytes.fromhex(r['geometry']))
            xs, ys = ll2utm.transform(*np.array(g.exterior.coords).T)
            out.append(Polygon(list(zip(xs, ys))))
    return out


def plan_utm(K):
    sp = siteplan(); f = siteplan_to_world(K)
    conv = lambda pts: np.array([world_to_utm(*f(p)) for p in pts])
    return {'roads': [conv(r) for r in sp['ROADS']], 'ponds': [conv(p) for p in sp['PONDS']], 'lots': conv(sp['LOTS']),
            'holes': [conv(h['path']) for h in sp['HOLES']], 'field': conv(sp['FIELD']), 'homes': conv(sp['HOMES'])}


def report(K):
    P = plan_utm(K)
    osm = osm_named({'Kaimalino Place', 'Kahela Place', 'Ala Haku Lei Loop', 'Aepo Nei Place', 'Pua Makalae Way'})
    pairs = [('Kaimalino Pl', 3, ['Kaimalino Place']), ('Kahela/Pua Makalae', 4, ['Kahela Place', 'Pua Makalae Way']), ('Ala Haku Lei Loop', 2, ['Ala Haku Lei Loop', 'Aepo Nei Place'])]
    rows = []
    for name, i, keys in pairs:
        real = [l for k in keys for l in osm.get(k, [])]
        # mean distance from the painted road's centroid to the nearest real road of that name, and the centroid offset
        pc = P['roads'][i].mean(0)
        rc = np.mean([np.array(l.coords).mean(0) for l in real], 0)
        rows.append((name, np.hypot(*(pc - rc)), pc - rc))
    wh = water_hazards()
    for j in (0, 1):
        pc = P['ponds'][j].mean(0)
        d = min(wh, key=lambda w: w.centroid.distance(Point(*pc)))
        rows.append((f'pond {j}', d.centroid.distance(Point(*pc)), pc - np.array(d.centroid.coords[0])))
    print(f'K = {K:.2f} ft/px  (lot spacing {K * math.hypot(445, 185) / 13:.1f} ft)')
    for n, d, v in rows: print(f'   {n:22s} off by {d:6.0f} m  (dE {v[0]:+5.0f}, dN {v[1]:+5.0f})')
    return P


def overlay(out, Ks, box=(449300, 2420350, 450900, 2421400), px=0.8, scene='S2B_4QDK_20260914_0_L2A'):
    E0, N0, E1, N1 = box
    W, H = int((E1 - E0) / px), int((N1 - N0) / px)
    e = E0 + (np.arange(W) + 0.5) * px; n = N1 - (np.arange(H) + 0.5) * px
    EE, NN = np.meshgrid(e, n)
    tci = np.asarray(Image.open(f'{C}/../tci_{scene}.png')).astype(np.float32) / 255
    col = np.stack([map_coordinates(tci[..., k], [(2428000 - NN) / 10 - 0.5, (EE - 444000) / 10 - 0.5], order=3) for k in range(3)], -1)
    col = np.clip(col * 1.9, 0, 1) ** 0.85
    z = np.load(f'{C}/../dem1m.npy')
    gy, gx = np.gradient(np.nan_to_num(z, nan=0), 1.0)
    sl = np.arctan(np.hypot(gx, gy) * 1.5); asp = np.arctan2(-gx, gy)
    hs = np.sin(np.radians(45)) * np.cos(sl) + np.cos(np.radians(45)) * np.sin(sl) * np.cos(np.radians(315) - asp)
    hsr = map_coordinates(hs, [(2423500 - NN) - 0.5, (EE - 448500) - 0.5], order=1, cval=0.7)
    im = Image.fromarray((np.clip(col * (0.45 + 0.75 * hsr[..., None]), 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    T = lambda pts: [((x - E0) / px, (N1 - y) / px) for x, y in pts]
    for r in json.load(open(f'{C}/ov_segment.json')):
        if r.get('class') in ('footway', 'path', 'steps', 'track'): continue
        g = wkb.loads(bytes.fromhex(r['geometry']))
        xs, ys = ll2utm.transform(*np.array(g.coords).T)
        d.line(T(zip(xs, ys)), fill=(255, 255, 255), width=3)
    for w in water_hazards(): d.polygon(T(w.exterior.coords), outline=(0, 255, 255), width=2)
    colors = [((255, 0, 255), (255, 255, 0)), ((255, 140, 0), (255, 140, 0))]
    for K, (rc, lc) in zip(Ks, colors):
        P = plan_utm(K)
        for r in P['roads']: d.line(T(r), fill=rc, width=2)
        for h in P['holes']: d.line(T(h), fill=(60, 120, 255), width=2)
        for p in P['ponds']: d.polygon(T(p), outline=(0, 140, 255), width=2)
        for x, y in T(P['lots']): d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=lc, width=2)
    # the 2026 grading (bare soil in the Sentinel-2 scenes of Jun-Sep 2026, PCA rectangle of the patch)
    c0 = np.array(STRIP['centre']); b = math.radians(STRIP['bearing']); u = np.array([math.sin(b), math.cos(b)]); v = np.array([u[1], -u[0]])
    rect = [c0 + u * a * STRIP['length'] / 2 + v * w * STRIP['width'] / 2 for a, w in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    d.polygon(T(rect), outline=(255, 230, 0), width=2)
    # the model as laid out now: fourteen lots in a row, LOT_PITCH apart, ours in red
    (pcx, pcz), plan = plan_lot_centre(); lot = plan['site']['lot']
    for i in range(14):
        dz = (i - OUR_LOT) * LOT_PITCH_FT
        corners = [world_to_utm(x, zz + dz) for x, zz in [(lot[0], lot[1]), (lot[2], lot[1]), (lot[2], lot[3]), (lot[0], lot[3])]]
        d.polygon(T(corners), outline=(255, 0, 0) if i == OUR_LOT else (255, 255, 255), width=3 if i == OUR_LOT else 1)
    k = keep_rect()
    d.polygon(T([world_to_utm(x, zz) for x, zz in [(k[0], k[1]), (k[2], k[1]), (k[2], k[3]), (k[0], k[3])]]), outline=(255, 120, 120), width=1)
    for g in range(int(E0 // 250 + 1) * 250, int(E1), 250):
        d.line([((g - E0) / px, 0), ((g - E0) / px, 10)], fill=(255, 255, 0)); d.text(((g - E0) / px + 2, 12), str(g), fill=(255, 255, 0))
    for g in range(int(N0 // 250 + 1) * 250, int(N1), 250):
        d.line([(0, (N1 - g) / px), (10, (N1 - g) / px)], fill=(255, 255, 0)); d.text((12, (N1 - g) / px - 5), str(g), fill=(255, 255, 0))
    # north arrow and legend
    d.line([(W - 40, 90), (W - 40, 30)], fill=(255, 255, 255), width=3); d.polygon([(W - 48, 40), (W - 32, 40), (W - 40, 24)], fill=(255, 255, 255)); d.text((W - 44, 94), 'N', fill=(255, 255, 255))
    leg = ['white: real roads (OSM)', 'cyan: real ponds (OSM water hazards)', 'yellow: bare soil of the 2026 grading (Sentinel-2)',
           'red box: our lot; white boxes: the other 13 lots as modelled (70 ft apart); pink: area kept as modelled',
           f'magenta/yellow: painted site plan, K={Ks[0]:.2f} ft/px'] + ([f'orange: painted site plan, K={Ks[1]:.2f} ft/px'] if len(Ks) > 1 else []) + ['blue: painted golf holes and ponds']
    for i, s in enumerate(leg): d.text((14, H - 16 * (len(leg) - i) - 6), s, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    im.save(out)


if __name__ == '__main__':
    out = sys.argv[1]
    Ks = [float(k) for k in sys.argv[2:]] or [1.66]
    for K in Ks: report(K)
    lonlat = pyproj.Transformer.from_crs('EPSG:32604', 'EPSG:4326', always_xy=True).transform(*LOT_UTM)
    print('our lot centre: UTM 4N %.0f E %.0f N  = %.5f N %.5f W; world +x grid bearing %.1f; true north on the plan %s' % (*LOT_UTM, lonlat[1], -lonlat[0], X_BEARING, np.round(true_north_world(), 3)))
    overlay(out, Ks)
