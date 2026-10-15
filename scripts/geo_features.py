#!/usr/bin/env python3
"""Real things on the real ground, in world feet, for src/realsite.js -> geodata/features.json:
  roads      OpenStreetMap road centre lines (Overture transportation/segment), class and width
  buildings  footprints (OpenStreetMap and Microsoft ML building footprints, via Overture), with an
             eave height and a roof colour read from the Sentinel-2 mosaic
  trees      tree tops found in the Meta / WRI 1 m global canopy height map (CC BY 4.0), kept only
             where the 2025-26 Sentinel-2 mosaic is still green (no trees on what has been graded)
The modelled neighbourhood (keep rect from siteLayout, passed in world feet) gets none of them.
    python3 scripts/geo_features.py <chm.tif> [keep x0 z0 x1 z1]
"""
import os, sys, json, math
import numpy as np, pyproj
from shapely import wkb
from shapely.geometry import Polygon, MultiPolygon, LineString, box as sbox
from shapely.ops import transform as stransform
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import *

C = cache_dir()
OUT = os.path.join(ROOT, 'geodata')
ll2utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32604', always_xy=True)
WIDTH = {'motorway': 40, 'trunk': 36, 'primary': 34, 'secondary': 30, 'tertiary': 26, 'residential': 22, 'unclassified': 20,
         'living_street': 18, 'service': 13}


def to_world_geom(g):
    def f(x, y, z=None):
        E, N = ll2utm.transform(x, y)
        return utm_to_world(E, N)
    return stransform(f, g)


def s2_sampler():
    z = np.load(f'{C}/s2_aoi.npz')
    refl = np.nan_to_num(z['refl'].astype(np.float32), nan=0.02); box = tuple(z['box']); res = float(z['res'])
    def at(E, N):
        r = (box[3] - np.asarray(N)) / res - 0.5; c = (np.asarray(E) - box[0]) / res - 0.5
        return np.stack([map_coordinates(refl[..., k], [r, c], order=1, cval=0.02) for k in range(4)], -1)
    return at


def roads(within):
    out = []
    for r in json.load(open(f'{C}/ov_segment.json')):
        cls = r.get('class')
        if cls not in WIDTH: continue
        g = to_world_geom(wkb.loads(bytes.fromhex(r['geometry'])))
        if not g.intersects(within): continue
        pts = np.round(np.array(g.coords), 1).ravel().tolist()
        out.append({'c': cls, 'w': WIDTH[cls], 'n': (r.get('names') or {}).get('primary'), 'p': pts})
    return out


def buildings(within, keep, s2):
    out = []
    for r in json.load(open(f'{C}/ov_building.json')):
        g = wkb.loads(bytes.fromhex(r['geometry']))
        if r.get('is_underground'): continue
        g = to_world_geom(g)
        polys = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
        for p in polys:
            if p.geom_type != 'Polygon' or p.area < 120 or not within.contains(p.centroid) or keep.intersects(p): continue
            p = p.simplify(1.2, preserve_topology=True)
            area_m2 = p.area * FT * FT
            floors = r.get('num_floors') or (1 if area_m2 < 380 else 2 if area_m2 < 1800 else 3)
            h = r.get('height')
            eave = (h / FT * 0.8) if h else 10.5 + (floors - 1) * 10.5
            # roof colour: the 10 m pixel over the roof, nudged towards real roof finishes
            cx, cz = p.centroid.coords[0]
            E, N = world_to_utm(cx, cz)
            rf = s2(np.atleast_1d(E), np.atleast_1d(N))[0, :3] * 1.12
            lum = float(rf @ [0.2126, 0.7152, 0.0722])
            if rf[0] > rf[1] * 1.18 and rf[0] > 0.09: roof = [0.32, 0.14, 0.09]          # rusty red / terracotta
            elif lum > 0.17: roof = [0.42, 0.42, 0.40]                                  # light grey metal, white membrane
            elif rf[1] > rf[0] * 1.1 and rf[1] > 0.07: roof = [0.11, 0.15, 0.12]       # green metal (Koloa)
            else: roof = [0.10, 0.10, 0.10] if lum < 0.08 else [0.17, 0.16, 0.15]      # charcoal / weathered grey
            ext = np.round(np.array(p.exterior.coords)[:-1], 1).ravel().tolist()
            mrr = p.minimum_rotated_rectangle
            rect = p.area / max(mrr.area, 1)
            out.append({'p': ext, 'e': round(eave, 1), 'r': [round(v, 3) for v in roof], 'q': round(rect, 2)})
    return out


def trees(chm_path, within, keep, s2, limit, blds=None):
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    x0, z0, x1, z1 = within.bounds
    cs = [world_to_utm(x, z) for x, z in [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]]
    E0, N0 = min(c[0] for c in cs), min(c[1] for c in cs); E1, N1 = max(c[0] for c in cs), max(c[1] for c in cs)
    res = 1.0
    W, H = int((E1 - E0) / res), int((N1 - N0) / res)
    chm = np.zeros((H, W), np.float32)
    with rasterio.open(chm_path) as ds:
        to3857 = pyproj.Transformer.from_crs('EPSG:32604', 'EPSG:3857', always_xy=True)
        bx0, by0 = to3857.transform(E0 - 50, N0 - 50); bx1, by1 = to3857.transform(E1 + 50, N1 + 50)
        w = rasterio.windows.from_bounds(bx0, by0, bx1, by1, ds.transform).round_offsets().round_lengths()
        a = ds.read(1, window=w).astype(np.float32)
        reproject(a, chm, src_transform=ds.window_transform(w), src_crs=ds.crs, dst_transform=from_origin(E0, N1, res, res), dst_crs='EPSG:32604', resampling=Resampling.bilinear)
    sm = ndi.gaussian_filter(chm, 1.2)
    peak = (sm == ndi.maximum_filter(sm, size=7)) & (sm >= 3.0)
    rr, cc = np.nonzero(peak)
    E = E0 + (cc + 0.5) * res; N = N1 - (rr + 0.5) * res; h = chm[rr, cc]
    # still vegetated in 2025-26 (NDVI of the recent mosaic)
    rf = s2(E, N); ndvi = (rf[:, 3] - rf[:, 0]) / (rf[:, 3] + rf[:, 0] + 1e-6)
    ok = ndvi > 0.3
    x, z = utm_to_world(E, N)
    from shapely import contains_xy
    ok &= contains_xy(within, x, z) & ~contains_xy(keep.buffer(60), x, z)
    # not on a roof (the canopy model sometimes calls a building a tree)
    if blds:
        from shapely.ops import unary_union
        roofs = unary_union([Polygon(np.array(b['p']).reshape(-1, 2)).buffer(4) for b in blds])
        ok &= ~contains_xy(roofs, x, z)
    x, z, h, E, N, rf = x[ok], z[ok], h[ok], E[ok], N[ok], rf[ok]
    # crown radius: allometric, capped by the distance to the next tree top
    from scipy.spatial import cKDTree
    kd = cKDTree(np.stack([E, N], 1)); d, _ = kd.query(np.stack([E, N], 1), k=2); nn = d[:, 1]
    r = np.minimum(0.32 * h + 1.0, 0.62 * nn + 0.6); r = np.clip(r, 1.3, 9.0)
    # keep the nearest `limit` trees to the lot (the rest is in the imagery)
    (px, pz), _ = plan_lot_centre()
    order = np.argsort(np.hypot(x - px, z - pz))[:limit]
    col = np.clip(rf[order, :3] * 1.18, 0, 1)
    print(f'trees: {peak.sum()} tops, {ok.sum()} kept as green, {len(order)} written')
    return {'x': np.round(x[order], 1).tolist(), 'z': np.round(z[order], 1).tolist(),
            'h': np.round(h[order] / FT, 1).tolist(), 'r': np.round(r[order] / FT, 1).tolist(),
            'c': np.round(col, 3).ravel().tolist()}


if __name__ == '__main__':
    chm = sys.argv[1]
    keep = [float(v) for v in sys.argv[2:6]] if len(sys.argv) >= 6 else None
    (px, pz), plan = plan_lot_centre()
    if keep is None: keep = keep_rect()
    keep_poly = sbox(*keep)
    s2 = s2_sampler()
    near = sbox(px - NEAR_HALF_FT, pz - NEAR_HALF_FT, px + NEAR_HALF_FT, pz + NEAR_HALF_FT)
    far = sbox(px - FAR_HALF_FT, pz - FAR_HALF_FT, px + FAR_HALF_FT, pz + FAR_HALF_FT)
    blds = buildings(far, keep_poly, s2)
    out = {'keep': keep, 'roads': roads(near), 'buildings': blds,
           'trees': trees(chm, near, keep_poly, s2, 24000, [b for b in blds if near.contains(Polygon(np.array(b['p']).reshape(-1, 2)).centroid)])}
    json.dump(out, open(f'{OUT}/features.json', 'w'), separators=(',', ':'))
    print('roads', len(out['roads']), 'buildings', len(out['buildings']), 'trees', len(out['trees']['x']),
          'size %.1f MB' % (os.path.getsize(f'{OUT}/features.json') / 1e6))
