#!/usr/bin/env python3
"""Bake the real-site rasters in the walkthrough's world frame (feet, world axes) into geodata/.

Inputs (cache, see geo_dem.py, geo_s2_mosaic.py, geo_overture.py):
  dem_aoi_10m.npy, dem_near_2m.npy   USGS lidar / 1/3" DEM, UTM 4N, m above local mean sea level
  s2_aoi.npz                         Sentinel-2 L2A median mosaic, surface reflectance B04 B03 B02 B08
  ov_water.json, ov_land_use.json    OpenStreetMap water and golf water hazards (Overture)
Outputs (geodata/):
  far_h.bin, near_h.bin   Uint16 little-endian height grids, row j = world z, col i = world x;
                          y_ft = hmin + v / 65535 * (hmax - hmin), world feet (0 = our floor level)
  far.jpg, far_2k.jpg     true-colour albedo (sRGB) over the far square, 4096 / 2048 px
  near.jpg                true-colour albedo over the near square, 2048 px (Sentinel upsampled, crisp
                          shorelines, pond and pool edges from the lidar / OSM water masks)
  far_w.png, near_w.png   water mask (255 water), 1024 px — roughness / ripples in the shader
  realsite.json           grids, anchor, sea level, attributions
    python3 scripts/geo_build.py
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import *

OUT = os.path.join(ROOT, 'geodata')
C = cache_dir()


def load_dem(name):
    a = np.load(f'{C}/{name}.npy'); g = json.load(open(f'{C}/{name}.json'))
    return a, g['box'], g['res']


def sample_utm(arr, box, res, E, N, order=1, cval=np.nan):
    """Sample a north-up UTM raster (row 0 = north edge) at points E, N."""
    r = (box[3] - N) / res - 0.5; c = (E - box[0]) / res - 0.5
    return map_coordinates(arr, [r, c], order=order, cval=cval, mode='constant', prefilter=False)


def world_grid(half, n):
    (px, pz), _ = plan_lot_centre()
    t = (np.arange(n) + 0.5) / n * 2 * half - half
    X, Z = np.meshgrid(px + t, pz + t)          # row j = z, col i = x
    return X, Z, [px - half, pz - half, px + half, pz + half]


def heights_m(E, N, dems):
    """Merged elevation (m) at UTM points: near 2 m lidar where available, else 10 m AOI; NaN = ocean."""
    out = np.full(E.shape, np.nan, np.float32)
    for arr, box, res in dems:                   # finest first
        inside = (E > box[0] + res) & (E < box[2] - res) & (N > box[1] + res) & (N < box[3] - res) & np.isnan(out)
        if not inside.any(): continue
        # NaN-aware bilinear: interpolate values and validity separately
        v = np.nan_to_num(arr, nan=0.0); m = (~np.isnan(arr)).astype(np.float32)
        hv = sample_utm(v, box, res, E[inside], N[inside], cval=0); hm = sample_utm(m, box, res, E[inside], N[inside], cval=0)
        h = np.where(hm > 0.5, hv / np.maximum(hm, 1e-6), np.nan)
        o = out[inside]; o[:] = h; out[inside] = o
    return out


def srgb(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def albedo(refl):
    """Surface reflectance -> display albedo. L2A BOA reflectance is close to albedo at these angles;
    a mild gain lifts it to the brightness of the hand-made materials (the median of many dates is a
    little flatter than any one day, so saturation gets a small lift back, no more)."""
    rgb = refl[..., :3].astype(np.float32) * 1.18
    lum = (rgb * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
    rgb = lum + (rgb - lum) * 1.06
    return np.clip(rgb, 0, 1)


def water_polys_utm():
    import pyproj
    from shapely import wkb
    t = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32604', always_xy=True)
    polys = []
    for fn, keep in (('ov_water.json', lambda r: r.get('subtype') in ('pond', 'reservoir', 'water', 'lake') or r.get('class') in ('pond', 'reservoir', 'basin', 'swimming_pool')),
                     ('ov_land_use.json', lambda r: r.get('class') == 'water_hazard')):
        p = f'{C}/{fn}'
        if not os.path.exists(p): continue
        for r in json.load(open(p)):
            if not keep(r): continue
            g = wkb.loads(bytes.fromhex(r['geometry']))
            for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
                if gg.geom_type != 'Polygon': continue
                xs, ys = t.transform(*np.array(gg.exterior.coords).T)
                polys.append((np.stack([xs, ys], 1), r.get('class')))
    return polys


def raster_polys(polys, X, Z, n):
    """Rasterise UTM polygons onto a world grid (n x n, bounds from X, Z)."""
    x0, z0 = X[0, 0], Z[0, 0]; dx = X[0, 1] - X[0, 0]
    im = Image.new('L', (n, n), 0); d = ImageDraw.Draw(im)
    for P, cls in polys:
        wx, wz = utm_to_world(P[:, 0], P[:, 1])
        pts = list(zip((wx - x0) / dx + 0.5, (wz - z0) / dx + 0.5))
        if len(pts) >= 3: d.polygon(pts, fill=255)
    return np.asarray(im) > 127


def build(name, half, n_h, n_tex, dems, s2, polys, grade):
    print(name, 'heights', flush=True)
    X, Z, bounds = world_grid(half, n_h)
    E, N = world_to_utm(X, Z)
    hm = heights_m(E, N, dems)
    # spectral water on the height grid
    rf = s2_at(s2, E, N)
    ndwi = (rf[..., 1] - rf[..., 3]) / (rf[..., 1] + rf[..., 3] + 1e-6)
    ocean = np.isnan(hm) | ((hm < 1.0) & (ndwi > 0.05))
    lab, nl = ndi.label(ocean)
    # ocean = water connected to the edge of the far grid or below 1 m; small inland holes are ponds
    ponds = raster_polys(polys, X, Z, n_h)
    inland = ((ndwi > 0.25) & ~ocean & (hm > 2)) | ponds
    inland = ndi.binary_opening(inland, iterations=1) | ponds
    # pond surfaces: flat at the lowest rim height of each pond
    labp, npd = ndi.label(inland)
    for k, sl in enumerate(ndi.find_objects(labp)):
        sl = tuple(slice(max(0, s.start - 3), s.stop + 3) for s in sl)
        m = labp[sl] == k + 1
        rim = ndi.binary_dilation(m, iterations=2) & ~m
        hv = hm[sl]
        if not (rim & ~np.isnan(hv)).any(): continue
        lvl = np.nanmin(np.where(rim, hv, np.nan))
        hv[m] = lvl - 0.3                                  # flat water a little below the bank
    hm = np.where(ocean, 0.0, hm)
    hm = np.where(np.isnan(hm), 0.0, hm)
    y = (hm - LOT_GROUND_M) / FT + grade
    hmin, hmax = float(y.min()) - 1, float(y.max()) + 1
    q = np.round((y - hmin) / (hmax - hmin) * 65535).astype('<u2')
    q.tofile(f'{OUT}/{name}_h.bin')
    water = ocean | inland
    if name == 'near':
        # the water mask at texture resolution, from OSM pond outlines where there are some (crisp shores)
        Xw, Zw, _ = world_grid(half, 2048); Ew, Nw = world_to_utm(Xw, Zw)
        hw = heights_m(Ew, Nw, dems)
        rw = s2_at(s2, Ew, Nw); nd = (rw[..., 1] - rw[..., 3]) / (rw[..., 1] + rw[..., 3] + 1e-6)
        wm = np.isnan(hw) | ((hw < 1.0) & (nd > 0.05)) | raster_polys(polys, Xw, Zw, 2048) | ((nd > 0.25) & (hw > 2))
        wm = ndi.gaussian_filter(wm.astype(np.float32), 0.7)
        Image.fromarray((np.clip(wm, 0, 1) * 255).astype(np.uint8)).save(f'{OUT}/{name}_w.png', optimize=True)
    else:
        Image.fromarray((water * 255).astype(np.uint8)).resize((min(1024, n_h), min(1024, n_h)), Image.BILINEAR).save(f'{OUT}/{name}_w.png', optimize=True)

    print(name, 'texture', flush=True)
    Xt, Zt, _ = world_grid(half, n_tex)
    Et, Nt = world_to_utm(Xt, Zt)
    rf = s2_at(s2, Et, Nt, order=3)
    if name == 'near':
        # under and around the modelled lots, the ground as it was before the 2025-26 grading
        before = os.path.join(C, 's2_before.npz')
        if os.path.exists(before):
            zb = np.load(before); sb = (np.nan_to_num(zb['refl'].astype(np.float32), nan=0.02), tuple(zb['box']), float(zb['res']))
            k = keep_rect(); dx = np.maximum.reduce([k[0] - Xt, Xt - k[2], np.zeros_like(Xt)]); dz = np.maximum.reduce([k[1] - Zt, Zt - k[3], np.zeros_like(Zt)])
            w = 1 - np.clip((np.hypot(dx, dz) - 150) / 200, 0, 1)
            rf = rf * (1 - w[..., None]) + s2_at(sb, Et, Nt, order=3) * w[..., None]
    rgb = albedo(rf)
    if name == 'near':
        rgb = guided_detail(rgb, Xt, Zt, Et, Nt, n_tex)
    # crisp water edges: inside OSM ponds / pools use the local water colour; ocean beyond the
    # lidar shoreline gets no land colour bleeding in
    ponds_t = raster_polys(polys, Xt, Zt, n_tex)
    if ponds_t.any():
        wcol = np.array([0.035, 0.07, 0.065])           # murky golf-course pond body colour (albedo)
        soft = ndi.gaussian_filter(ponds_t.astype(np.float32), 0.8)[..., None]
        rgb = rgb * (1 - soft) + wcol * soft
    img = (srgb(rgb) * 255 + 0.5).astype(np.uint8)
    im = Image.fromarray(img)
    if name == 'far':
        im.save(f'{OUT}/far.jpg', quality=88, optimize=True, progressive=True)
        im.resize((2048, 2048), Image.LANCZOS).save(f'{OUT}/far_2k.jpg', quality=88, optimize=True, progressive=True)
    else:
        im.save(f'{OUT}/{name}.jpg', quality=90, optimize=True, progressive=True)
    return {'box': bounds, 'hsize': n_h, 'hmin': hmin, 'hmax': hmax, 'height': f'{name}_h.bin', 'water': f'{name}_w.png',
            'tex': f'{name}.jpg', 'texSize': n_tex, **({'texLow': 'far_2k.jpg'} if name == 'far' else {})}


def box_mean(a, r):
    """Mean over a (2r+1)^2 window, per channel (edges replicated)."""
    return ndi.uniform_filter(a, size=(2 * r + 1, 2 * r + 1) + (1,) * (a.ndim - 2), mode='nearest')


def guided_detail(rgb, Xt, Zt, Et, Nt, n):
    """Sharpen the 10 m Sentinel colour with crisp 1-2 m guides: tree canopy (Meta/WRI 1 m canopy
    height), building footprints, roads (OSM) and water. A multichannel guided filter fits, in every
    ~30 m window, colour = a . guides + b on the guides blurred to Sentinel's resolution, then applies
    it to the sharp guides: the real colours, at the guides' detail."""
    feats = os.path.join(OUT, 'features.json')
    if not os.path.exists(feats): return rgb
    F = json.load(open(feats))
    x0, z0 = Xt[0, 0], Zt[0, 0]; dx = Xt[0, 1] - Xt[0, 0]
    P = lambda xs, zs: list(zip((np.asarray(xs) - x0) / dx + 0.5, (np.asarray(zs) - z0) / dx + 0.5))
    def layer(draw):
        im = Image.new('L', (n, n), 0); draw(ImageDraw.Draw(im)); return np.asarray(im).astype(np.float32) / 255
    def bld(d):
        for b in F['buildings']:
            p = np.array(b['p']).reshape(-1, 2)
            if abs(p[0, 0] - Xt.mean()) < (n + 50) * dx and abs(p[0, 1] - Zt.mean()) < (n + 50) * dx: d.polygon(P(p[:, 0], p[:, 1]), fill=255)
    def rds(d):
        for r in F['roads']:
            p = np.array(r['p']).reshape(-1, 2)
            d.line(P(p[:, 0], p[:, 1]), fill=255, width=max(1, int(round(r['w'] * 0.8 / dx))), joint='curve')
    G_b = layer(bld); G_r = np.clip(layer(rds) - G_b, 0, 1)
    # canopy height (m), resampled from the 1 m Meta/WRI map
    chm = np.zeros((n, n), np.float32)
    chm_path = os.environ.get('GEO_CHM') or os.path.join(C, '..', 'dl_chm', '022211101.tif')
    if os.path.exists(chm_path):
        import rasterio, pyproj
        with rasterio.open(chm_path) as ds:
            t = pyproj.Transformer.from_crs('EPSG:32604', 'EPSG:3857', always_xy=True)
            X3, Y3 = t.transform(Et, Nt)
            w = rasterio.windows.from_bounds(X3.min() - 20, Y3.min() - 20, X3.max() + 20, Y3.max() + 20, ds.transform).round_offsets().round_lengths()
            a = ds.read(1, window=w).astype(np.float32); tr = ds.window_transform(w)
            col = (X3 - tr.c) / tr.a - 0.5; row = (Y3 - tr.f) / tr.e - 0.5
            chm = map_coordinates(a, [row, col], order=1, cval=0)
    G_t = np.clip((chm - 1.5) / 5, 0, 1) * (1 - G_b)
    G_w = raster_polys(water_polys_utm(), Xt, Zt, n).astype(np.float32)
    G = np.stack([G_t, G_b, G_r, G_w], -1)
    # work at half resolution for the fit
    h = n // 2
    Gh = G.reshape(h, 2, h, 2, -1).mean((1, 3)); Ph = rgb.reshape(h, 2, h, 2, 3).mean((1, 3))
    sig = 5.5 / (2 * dx * FT) * 1.0                    # Sentinel PSF ~ 13 m FWHM, in half-res texels
    Gl = np.stack([ndi.gaussian_filter(Gh[..., k], sig) for k in range(4)], -1)
    r = int(round(30 / (2 * dx * FT)))
    mI = box_mean(Gl, r); mP = box_mean(Ph, r)
    k = Gl.shape[-1]
    cov = box_mean(Gl[..., :, None] * Gl[..., None, :], r) - mI[..., :, None] * mI[..., None, :]
    cIP = box_mean(Gl[..., :, None] * Ph[..., None, :], r) - mI[..., :, None] * mP[..., None, :]
    A = np.linalg.solve(cov + 0.004 * np.eye(k), cIP)           # (h, h, k, 3)
    A = box_mean(A.reshape(h, h, -1), r)
    A = ndi.zoom(A, (2, 2, 1), order=1).reshape(n, n, k, 3)
    # detail injection: the measured colour plus what the sharp guides add above their blurred selves
    Gfl = np.stack([ndi.gaussian_filter(G[..., j], sig * 2) for j in range(k)], -1)
    out = rgb + np.einsum('...k,...kc->...c', G - Gfl, A)
    # keep within reason of the measured colour (no ringing into impossible colours)
    lo = np.minimum(rgb * 0.45, rgb - 0.03); hi = rgb * 1.8 + 0.03
    out = np.clip(out, np.maximum(lo, 0), hi)
    # a little crown shading from the canopy height (sun from the south-east at the Sentinel overpass)
    gy, gx = np.gradient(ndi.gaussian_filter(chm, 0.8), dx * FT)
    E_, N_ = world_axes()
    # world grid gradient (x, z) -> east, north components
    ge = gx * E_[0] + gy * world_axes()[1][0]; gn = gx * E_[1] + gy * world_axes()[1][1]
    shade = np.clip(1 + 0.18 * (-ge * 0.5 + gn * 0.7) / (1 + np.hypot(ge, gn)), 0.75, 1.15)
    out = out * np.where(G_t[..., None] > 0.2, shade[..., None], 1)
    print('  guided detail: trees %.2f buildings %.3f roads %.3f water %.3f' % tuple(G.mean((0, 1))))
    return np.clip(out, 0, 1)


S2 = {}
def s2_at(s2, E, N, order=1):
    refl, box, res = s2
    out = np.empty(E.shape + (4,), np.float32)
    for k in range(4):
        out[..., k] = sample_utm(refl[..., k], box, res, E, N, order=order, cval=0.02)
    return out


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    (_, _), plan = plan_lot_centre(); grade = plan.get('grade', -0.6)
    near_dem = load_dem('dem_near_2m'); aoi_dem = load_dem('dem_aoi_10m')
    z = np.load(f'{C}/s2_aoi.npz')
    refl = z['refl'].astype(np.float32); refl = np.nan_to_num(refl, nan=0.02)
    s2 = (refl, tuple(z['box']), float(z['res']))
    polys = water_polys_utm()
    near = build('near', NEAR_HALF_FT, 1024, 2048, [near_dem, aoi_dem], s2, polys, grade)
    far = build('far', FAR_HALF_FT, 1024, 4096, [near_dem, aoi_dem], s2, polys, grade)
    import pyproj
    lon, lat = pyproj.Transformer.from_crs('EPSG:32604', 'EPSG:4326', always_xy=True).transform(*LOT_UTM)
    meta = {
        'about': "Real terrain and satellite colour of south Kaua'i around Na Hiku, Kukui'ula, in the walkthrough's world frame (feet).",
        'anchor': {'lotUTM': LOT_UTM, 'crs': 'EPSG:32604', 'lat': lat, 'lon': lon, 'xBearing': X_BEARING, 'convergence': CONVERGENCE,
                   'lotGround_m': LOT_GROUND_M, 'regErr_m': REG_ERR_M},
        'north': true_north_world(),
        'seaLevel': (0 - LOT_GROUND_M) / FT + grade,
        'grade': grade,
        'far': far, 'near': near,
        'attribution': [
            'Elevation: U.S. Geological Survey 3DEP 1 m DEM (HI_FEMAR9Kauai_2019_D19) and 1/3 arc-second DEM, public domain',
            'Imagery: contains modified Copernicus Sentinel-2 data 2023-2026 (ESA), via AWS Open Data (Element 84)',
            'Water, roads, buildings: OpenStreetMap contributors (ODbL) and Microsoft ML building footprints (ODbL), via Overture Maps',
        ],
    }
    json.dump(meta, open(f'{OUT}/realsite.json', 'w'), indent=1)
    print('sea level (world ft) %.1f' % meta['seaLevel'])
