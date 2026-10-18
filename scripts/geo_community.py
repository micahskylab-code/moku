#!/usr/bin/env python3
"""Bake the Kukui'ula community map: half-metre ground tiles in north-up UTM, for the community view
(src/community.js). A map rendering of open data, not an aerial photograph.

The ground is drawn, not photographed: there is no open sub-metre aerial imagery of Kukui'ula that this
pipeline can use (docs/community-view.md). Every pixel is placed by data:
  - colour, from the Sentinel-2 L2A median mosaic (10 m): it decides grass vs soil vs reef, and the hue;
  - shape, from the USGS 3DEP 1 m lidar DEM (2019-21) and the Meta/WRI 1 m canopy height map (2024):
    shorelines, slopes, every tree crown;
  - depth, from the USACE 2013 topobathy lidar (seafloor colour, surf, the shoreline);
  - lines, from OpenStreetMap via Overture (roads, a few of them TomTom's; paths, ponds, pools, beaches, bare
    rock, golf features where mapped) and building footprints (OSM + Microsoft); a mapped pond is drawn as water only
    while the canopy map and the satellite still see open water there (Inputs._pond_check);
and drawn with procedural surface texture (grass grain, mowing stripes, sand, crowns, asphalt) whose
colour follows the measured colour. Golf turf on courses where OSM maps (almost) no fairways (Kukui'ula's) is
inferred from the satellite colour (tree-free mown grass, lighter than the course around it); greens, tees and
bunkers are drawn wherever they are mapped.

Inputs (cache): dem_comm_1m.npy (scripts/geo_dem1m.py), bathy_comm_1m.npy (scripts/geo_bathy.py),
dem_near_2m.npy (scripts/geo_dem.py), s2_aoi.npz, ov_segment.json, ov_land_use.json, ov_water.json, ov_land.json;
geodata/features.json (buildings with eave height and roof colour); the canopy height tile.
Outputs (geodata/community/):
  a_<c>_<r>.webp   albedo, 2048 px over 1 km (0.49 m per texel), sRGB
  s_<c>_<r>.webp   the same, 512 px (2 m), loaded first and for distant tiles
  n_<c>_<r>.webp   1024 px, lossless: R, G = surface normal east / north (lidar ground + canopy), B = height of
                   what casts shadow (canopy, buildings), 0.1 m per step
  w_<c>_<r>.png    512 px: R = signed distance to the sea's edge (128 + 1 per m, sea positive, +-127 m), G = pond
                   water (land) or the harbour's calm (sea, CALM_G per unit), B = sea depth (10 per m), or on land more
                   than LC_SHORE_M from the sea: 16 x land-cover class (LC_NAMES) + dryness 0-15
  h.bin            Uint16 ground heights over the whole box, 5 m, world feet (as geodata/realsite.json)
  community.json   box, tiles, transforms, attribution
    python3 scripts/geo_community.py [--only "c,r;c,r"]
"""
import os, sys, json, math, argparse
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import *
from geo_dem1m import COMM_BOX

OUT = os.path.join(ROOT, 'geodata', 'community')
C = cache_dir()
TILE = 1000.0                     # m
TEX = 2048                        # albedo texels per tile
MARGIN = 200                      # texels of context around a tile (98 m: blurs up to 25 m sigma, normals, AO)
PX = TILE / TEX
HRES = 5.0                        # m, mesh height grid
SDF_PER_M = 1                     # w_*.png R: 128 + this per metre from the sea's edge (+-127 m: surf sets out to the reef edge)


# ------------------------------------------------------------------ noise (seamless: a function of E, N)
def _hash(ix, iy, seed):
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + seed * 1442695041) & 0xffffffff
    h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
    return ((h ^ (h >> 16)) & 0xffffff).astype(np.float32) / 0xffffff


def vnoise(E, N, s, seed):
    x, y = E / s, N / s
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = (x - ix).astype(np.float32), (y - iy).astype(np.float32)
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, seed), _hash(ix + 1, iy, seed)
    c, d = _hash(ix, iy + 1, seed), _hash(ix + 1, iy + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def cells(E, N, s, seed):
    """Id (0-1) of the nearest point of a jittered grid s m apart (Worley cells): patches about the size of a crown."""
    x, y = E / s, N / s
    ix, iy = np.floor(x), np.floor(y)
    best = np.full(x.shape, 9.0, np.float32); bid = np.zeros(x.shape, np.float32)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = ix + dx, iy + dy
            d = (cx + _hash(cx, cy, seed) - x) ** 2 + (cy + _hash(cx, cy, seed + 7) - y) ** 2
            m = d < best
            best = np.where(m, d, best); bid = np.where(m, _hash(cx, cy, seed + 13), bid)
    return bid


def fbm(E, N, s, octaves, seed, gain=0.5):
    out, amp, tot = 0, 1.0, 0
    for k in range(octaves):
        out = out + amp * vnoise(E, N, s / 2 ** k, seed + 17 * k)
        tot += amp; amp *= gain
    return out / tot


# ------------------------------------------------------------------ inputs
def lin2srgb(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def lum(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def sat(c, k):
    l = lum(c)[..., None]
    return np.clip(l + (c - l) * k, 0, 1)


class Inputs:
    def __init__(self):
        print('inputs', flush=True)
        self.dem = np.load(f'{C}/dem_comm_1m.npy')                    # north-up, row 0 = N1
        z = np.load(f'{C}/s2_aoi.npz')
        self.s2 = np.nan_to_num(z['refl'].astype(np.float32), nan=0.02); self.s2box = tuple(z['box']); self.s2res = float(z['res'])
        self.box = COMM_BOX
        bp = f'{C}/bathy_comm_1m.npy'                                   # seafloor (scripts/geo_bathy.py)
        self.bathy = np.load(bp) if os.path.exists(bp) else np.full_like(self.dem, np.nan)
        self._sea()
        self._bathy_gaps()
        self._deep_colour()
        self._fill_voids()
        self._vectors()
        self._chm()
        self._pond_check()
        self._golf_global()

    # sea: no lidar ground, or below 0.3 m and spectrally water, connected to the open sea
    def _sea(self):
        d = self.dem
        E0, N0, E1, N1 = self.box
        n2r, n2c = (N1 - N0) // 2, (E1 - E0) // 2
        blk = d[:n2r * 2, :n2c * 2].reshape(n2r, 2, n2c, 2)
        with np.errstate(invalid='ignore'):
            h2 = np.nanmean(blk, axis=(1, 3))
        Ec = E0 + (np.arange(n2c) + 0.5) * 2; Nc = N1 - (np.arange(n2r) + 0.5) * 2
        EE, NN = np.meshgrid(Ec, Nc)
        rf = self.s2_at(EE, NN)
        ndwi = (rf[..., 1] - rf[..., 3]) / (rf[..., 1] + rf[..., 3] + 1e-6)
        b = self.bathy[:n2r * 2, :n2c * 2].reshape(n2r, 2, n2c, 2)
        with np.errstate(invalid='ignore'):
            b2 = np.nanmean(b, axis=(1, 3))
        # the topobathy survey decides where it has a return (below mean sea level = sea); elsewhere the lidar
        # ground and the satellite's water index
        cand = np.where(np.isnan(b2), np.isnan(h2) | ((h2 < 0.3) & (ndwi > 0.0)), b2 < -0.1)
        lab, _ = ndi.label(cand)
        edge = np.unique(np.concatenate([lab[-1], lab[:, 0], lab[:, -1]]))   # south, west, east edges touch the sea
        edge = edge[edge > 0]
        sea = np.isin(lab, edge)
        sea = ndi.binary_opening(sea, iterations=1) | (np.isnan(h2) & sea)
        sea = ndi.binary_fill_holes(sea) & cand | sea
        # patches the sea encloses where the lidar found no ground at all and the satellite sees no plants are reef tops
        # awash in the surf (the survey's return at about 0 m): very shallow sea, not islands
        hole = ndi.binary_fill_holes(sea) & ~sea
        if hole.any():
            lab, nh = ndi.label(hole)
            ndvi = (rf[..., 3] - rf[..., 0]) / (rf[..., 3] + rf[..., 0] + 1e-6)
            k = np.nonzero((np.asarray(ndi.mean(np.isnan(h2), lab, np.arange(1, nh + 1))) > 0.95) &
                           (np.asarray(ndi.mean(ndvi, lab, np.arange(1, nh + 1))) < 0.25))[0]
            awash = np.isin(lab, k + 1); sea |= awash
            print(f'  {len(k)} reef tops awash ({int(awash.sum()) * 4} m2) drawn as sea', flush=True)
        self.sea2 = sea
        self.sdf2 = (ndi.distance_transform_edt(sea) - ndi.distance_transform_edt(~sea)) * 2.0   # m, + in the sea
        self.h2 = h2
        print('  sea %.0f%% of the box' % (100 * sea.mean()), flush=True)

    def _bathy_gaps(self):
        """Survey gaps inside the sea (mostly under breaking surf, where the lidar got no return) are filled from the
        depths around them, so they are not drawn as deep holes in a 1 m reef; only the gap that reaches the box's
        south, west or east edge is 'beyond the survey' and keeps the deep-water fallback. self.bfill marks the
        filled cells (their bottom takes the roughness around them in the bake)."""
        b = self.bathy
        sea1 = np.repeat(np.repeat(self.sea2, 2, 0), 2, 1)[:b.shape[0], :b.shape[1]]
        gap = np.isnan(b) & sea1
        lab, _ = ndi.label(gap)
        outer = np.unique(np.concatenate([lab[-1], lab[:, 0], lab[:, -1]])); outer = outer[outer > 0]
        inner = gap & ~np.isin(lab, outer); del lab, gap
        self.bfill = np.zeros(b.shape, np.uint8)
        if inner.any() and (~np.isnan(b)).any():
            self.bfill[inner] = 1
            dist, idx = ndi.distance_transform_edt(np.isnan(b), return_indices=True)
            near = b[idx[0], idx[1]]; del idx
            w = np.clip(dist / 10.0, 0, 1).astype(np.float32); del dist      # wider smoothing deeper into a gap
            b[inner] = (ndi.gaussian_filter(near, 3.0) * (1 - w) + ndi.gaussian_filter(near, 10.0) * w)[inner]
            print(f'  filled {int(inner.sum())} m2 of survey gaps inside the sea', flush=True)

    def _deep_colour(self):
        """The open sea's colour in the satellite mosaic (deeper than 30 m, or beyond the survey 300 m out): what the
        reef colours fade into with depth. The mosaic's open water carries a spectrally flat offset (sun glint and
        haze: near-infrared about equal to red, where clear deep water reflects almost no infrared), so the
        near-infrared band is taken off the visible ones first."""
        E0, N0, E1, N1 = self.box
        b = self.bathy[::10, ::10]; sdf = self.sdf2[::5, ::5][:b.shape[0], :b.shape[1]]
        deep = ((b < -30) | (np.isnan(b) & (sdf > 300)))
        r, c = np.nonzero(deep)
        rf = self.s2_at(E0 + c * 10 + 5.0, N1 - r * 10 - 5.0)
        self.deep_rgb = np.clip(np.median(np.clip(rf[:, :3] - rf[:, 3:4], 0.002, None), 0) * 1.18, 0, 1).astype(np.float32)
        print('  open-sea colour (linear)', np.round(self.deep_rgb, 4), f'from {len(r)} pixels', flush=True)

    def _fill_voids(self):
        """Holes in the 1 m DEM (no lidar ground) on land: near the shore (within 30 m of the sea: wave-washed rock and
        reef tops) the measured topobathy there; elsewhere the 2 m merged DEM (scripts/geo_dem.py), else the nearest
        lidar ground. The sea stays at 0."""
        d = self.dem
        sea1 = np.repeat(np.repeat(self.sea2, 2, 0), 2, 1)[:d.shape[0], :d.shape[1]]
        void = np.isnan(d)
        fill = void & ~sea1
        if fill.any():
            coast = np.repeat(np.repeat(self.sdf2 > -30, 2, 0), 2, 1)[:d.shape[0], :d.shape[1]]
            tb = fill & coast & ~np.isnan(self.bathy)
            d[tb] = self.bathy[tb]
            print(f'  {int(tb.sum())} m2 of shore voids from the topobathy', flush=True)
            r, c = np.nonzero(fill & ~tb)
            E = self.box[0] + c + 0.5; N = self.box[3] - r - 0.5
            p2 = f'{C}/dem_near_2m.npy'
            if os.path.exists(p2):
                a2 = np.load(p2); g2 = json.load(open(f'{C}/dem_near_2m.json'))
                v = map_coordinates(a2, [(g2['box'][3] - N) / g2['res'] - 0.5, (E - g2['box'][0]) / g2['res'] - 0.5], order=1, cval=np.nan, prefilter=False)
                d[r, c] = v
            still = np.isnan(d) & ~sea1
            if still.any():
                idx = ndi.distance_transform_edt(np.isnan(d), return_distances=False, return_indices=True)
                d[still] = d[idx[0][still], idx[1][still]]
            self._seamless(d, fill & ~tb)
            print(f'  filled {fill.mean():.1%} of the box (inland lidar voids)', flush=True)
        d[np.isnan(d)] = 0.0

    @staticmethod
    def _seamless(d, hole, sigma=20.0):
        """The 2 m merged DEM carries its own seams inside the 1 m lidar's voids (a ridge or a trench a metre or two in
        from the rim, 10 m blocks inside), which drew a black, jagged 'crack' and a row of pale teeth beside the Nā Hiku
        strip. Inside each void only its broad shape is kept (smoothed over 20 m), and the difference to the lidar along
        the void's rim is spread inward as a membrane (Laplace), so the fill meets the lidar with no step."""
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import spsolve
        lab, nl = ndi.label(hole)
        done = 0
        for k, sl in enumerate(ndi.find_objects(lab)):
            r0, r1 = max(sl[0].start - 14, 0), min(sl[0].stop + 14, d.shape[0])
            c0, c1 = max(sl[1].start - 14, 0), min(sl[1].stop + 14, d.shape[1])
            sub = d[r0:r1, c0:c1]; m = lab[r0:r1, c0:c1] == k + 1
            if m.sum() < 4: continue
            nan = np.isnan(sub); full = sub
            if nan.any():                                                    # the sea beside it (no ground): its nearest land
                full = sub[tuple(ndi.distance_transform_edt(nan, return_distances=False, return_indices=True))]
            sm = ndi.gaussian_filter(full, sigma)
            res = (full - sm).astype(np.float64)                            # outside the void: the lidar's difference
            m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = False                  # (the box keeps a known border)
            ii = -np.ones(m.shape, np.int64); ii[m] = np.arange(m.sum())
            rr, cc = np.nonzero(m)
            rows, cols, vals = [np.arange(len(rr))], [np.arange(len(rr))], [np.full(len(rr), 4.0)]
            b = np.zeros(len(rr))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                j = ii[rr + dr, cc + dc]; inn = j >= 0
                rows.append(np.nonzero(inn)[0]); cols.append(j[inn]); vals.append(-np.ones(inn.sum()))
                b[~inn] += res[rr[~inn] + dr, cc[~inn] + dc]
            A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(len(rr),) * 2).tocsr()
            sub[m] = sm[m] + spsolve(A, b)
            done += int(m.sum())
        if done: print(f'  {done} m2 of inland voids blended into the lidar around them', flush=True)

    def s2_at(self, E, N, order=1):
        r = (self.s2box[3] - N) / self.s2res - 0.5; c = (E - self.s2box[0]) / self.s2res - 0.5
        return np.stack([map_coordinates(self.s2[..., k], [r, c], order=order, cval=0.02, mode='nearest', prefilter=order > 1)
                         for k in range(4)], -1).astype(np.float32)

    def grid_at(self, arr, res, E, N, order=1, cval=np.nan):
        E0, N0, E1, N1 = self.box
        r = (N1 - N) / res - 0.5; c = (E - E0) / res - 0.5
        return map_coordinates(arr, [r, c], order=order, cval=cval, mode='nearest', prefilter=False)

    def _chm(self):
        import rasterio, pyproj
        path = os.environ.get('GEO_CHM') or os.path.join(C, '..', 'dl_chm', '022211101.tif')
        E0, N0, E1, N1 = self.box
        t = pyproj.Transformer.from_crs('EPSG:32604', 'EPSG:3857', always_xy=True)
        xs, ys = t.transform([E0 - 200, E1 + 200, E0 - 200, E1 + 200], [N0 - 200, N0 - 200, N1 + 200, N1 + 200])
        with rasterio.open(path) as ds:
            w = rasterio.windows.from_bounds(min(xs), min(ys), max(xs), max(ys), ds.transform).round_offsets().round_lengths()
            self.chm_a = ds.read(1, window=w).astype(np.float32); self.chm_tr = ds.window_transform(w)
        self.chm_t = t
        self.chm_a[~np.isfinite(self.chm_a)] = 0

    def _pond_check(self):
        """Mapped ponds that are no longer open water stay land: an overgrown reservoir that OSM still maps (trees
        standing in it, a plant canopy over it) and golf 'water hazard' outlines around dry ground. A pond is drawn
        as land when trees (canopy height > 2 m) cover 15% of it or more, or when its Sentinel-2 NDVI median is above
        0.3 (open water is below 0) and it is not dark in the near-infrared: its median NIR is at least 0.75 of its
        banks' (the land 10-30 m around it). Water absorbs near-infrared whatever grows in it; a pond's 10 m pixels
        take in the turf around it, and Kukui'ula's golf ponds (algae-green, a few pixels across) read 0.35-0.7 in
        NDVI while their NIR is a fifth to three quarters of their banks'. The satellite test applies only to ponds with a
        whole 10 m pixel inside them (at least 100 m2 after a 5 m inset); smaller ones are judged by the canopy alone.
        A dropped pond gets no water paint, no pond bit in w_*.png and no levelling in the heights."""
        E0, N0, E1, N1 = self.box
        kept, dropped, seen = [], 0, {}
        for P in self.ponds:
            key = (round(float(P[0][:, 0].mean())), round(float(P[0][:, 1].mean())), len(P[0]))
            if key not in seen:                                              # OSM water and golf hazard copies of one pond
                x0, y0 = P[0].min(0) - 32; x1, y1 = P[0].max(0) + 32
                nc, nr = int(np.ceil(x1 - x0)) + 1, int(np.ceil(y1 - y0)) + 1
                m = Canvas(x0, y1, nc, 1.0, nr).polys([P], ss=2) > 0.5
                if not m.any(): seen[key] = True
                else:
                    E, N = np.meshgrid(x0 + np.arange(nc) + 0.5, y1 - np.arange(nr) - 0.5)
                    share = float((self.chm_at(E[m], N[m]) > 2.0).mean())
                    rf = self.s2_at(E, N)
                    ndvi = float(np.median(((rf[..., 3] - rf[..., 0]) / (rf[..., 3] + rf[..., 0] + 1e-6))[m]))
                    r2 = np.clip(((N1 - N) / 2).astype(int), 0, self.sea2.shape[0] - 1)
                    c2 = np.clip(((E - E0) / 2).astype(int), 0, self.sea2.shape[1] - 1)
                    bank = ndi.binary_dilation(m, iterations=30) & ~ndi.binary_dilation(m, iterations=10) & ~self.sea2[r2, c2]
                    nir_r = float(np.median(rf[..., 3][m]) / max(np.median(rf[..., 3][bank]), 1e-3)) if bank.sum() > 50 else 0.0
                    seen_px = ndi.binary_erosion(m, iterations=5).sum() >= 100
                    water = share < 0.15 and not (seen_px and ndvi > 0.3 and nir_r >= 0.75)
                    seen[key] = water
                    if not water:
                        dropped += 1
                        print(f'  pond at E{P[0][:, 0].mean():.0f} N{P[0][:, 1].mean():.0f} ({int(m.sum())} m2) drawn as land: '
                              f'canopy {share:.0%}, NDVI {ndvi:+.2f}, NIR {nir_r:.2f} of its banks', flush=True)
            if seen[key]: kept.append(P)
        print(f'  ponds: {len(kept)} drawn as water, {len(self.ponds) - len(kept)} outlines ({dropped} places) left as land', flush=True)
        self.ponds = kept

    def _golf_global(self):
        """Golf turf over the whole box at 2 m, so that every tile gets the same answer at the same place: the fairways
        inferred on courses where OSM maps (almost) none (their 60 m context reaches across tiles), and, for every mown
        patch, the centre and long axis its mower stripes follow."""
        E0, N0, E1, N1 = self.box; R = 2.0
        nc, nr = int((E1 - E0) / R), int((N1 - N0) / R)
        E, N = np.meshgrid(E0 + (np.arange(nc) + 0.5) * R, N1 - (np.arange(nr) + 0.5) * R)
        rf = self.s2_at(E, N, order=3)
        rf = np.stack([ndi.gaussian_filter(rf[..., k], 1.0) for k in range(4)], -1)
        lumS = lum(np.clip(rf[..., :3] * 1.18, 0, 1))
        ndvi = (rf[..., 3] - rf[..., 0]) / (rf[..., 3] + rf[..., 0] + 1e-6)
        chm = self.chm_at(E, N)
        cv = Canvas(E0, N1, nc, R, nr)
        courses = cv.polys(self.courses, ss=1) > 0.5
        bld = cv.polys([[P] for P, h, r in self.blds], ss=1) > 0.5
        paved = cv.lines([(ROAD_W[c], L) for c, L, k in self.roads if c in PAVED and k == 'road'], ss=1) > 0.5
        water = cv.polys(self.ponds, ss=1) > 0.5
        sea = self.sea2[:nr, :nc]
        turf = (chm < 1.2) & (ndvi > 0.42) & ~bld & ~paved & ~water & ~sea
        # per course: infer only where OSM maps fairways or driving ranges over less than 5% of it (a lone mapped
        # green or tee does not switch it off)
        lab_c, ncrs = ndi.label(courses)
        fw = cv.polys([P for c, P in self.golf if c in ('fairway', 'driving_range')], ss=1) > 0.5
        has = np.ones(ncrs + 1, bool)                                       # label 0 (outside every course) never infers
        if ncrs: has[1:] = np.asarray(ndi.mean(fw, lab_c, index=np.arange(1, ncrs + 1))) > 0.05
        infer = courses & ~has[lab_c]
        print(f'  golf: {ncrs} courses, fairways inferred on {int((~has[1:]).sum())}', flush=True)
        tm = (infer & turf).astype(np.float32)
        lm = ndi.gaussian_filter(lumS * tm, 60 / R) / np.maximum(ndi.gaussian_filter(tm, 60 / R), 1e-3)
        fi = infer & turf & (lumS > lm * 1.02)
        fi = ndi.binary_opening(fi, iterations=3)                            # 6 m
        self.fair_inf2 = ndi.gaussian_filter(fi.astype(np.float32), 2.0)     # 4 m
        # mown patches (inferred and mapped fairways, driving ranges, tees): each one's centre and long axis
        osm = cv.polys([P for c, P in self.golf if c in ('fairway', 'driving_range', 'tee')], ss=1)
        mown = np.maximum(osm, self.fair_inf2) > 0.5
        lab, nl = ndi.label(mown)
        P = np.zeros((nl + 1, 5), np.float32)                               # ce, cn (local m), axis E, axis N, phase
        Eo, No = (E - E0).astype(np.float32), (N - N0).astype(np.float32)
        for k, sl in enumerate(ndi.find_objects(lab)):
            m = lab[sl] == k + 1
            e, n_ = Eo[sl][m], No[sl][m]
            if len(e) < 3: P[k + 1] = [e.mean(), n_.mean(), 1, 0, k]; continue
            w, v = np.linalg.eigh(np.cov(np.stack([e - e.mean(), n_ - n_.mean()])))
            P[k + 1] = [e.mean(), n_.mean(), v[0, 1], v[1, 1], 0.5 + k]
        idx = ndi.distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
        self.mown_id = lab[idx[0], idx[1]]                                  # every pixel: its nearest patch
        self.mown_par = P
        print(f'  golf: {nl} mown patches, {self.fair_inf2.mean() * 100:.1f}% of the box inferred fairway', flush=True)

    def stripes_at(self, E, N, Eo, No, width):
        """+-1 mower bands `width` m wide, parallel to the long axis of the nearest mown patch (global, seamless)."""
        k = self.grid_at(self.mown_id.astype(np.float32), 2.0, E, N, order=0, cval=0).astype(np.int32)
        p = self.mown_par[k]
        across = (Eo - p[..., 0]) * -p[..., 3] + (No - p[..., 1]) * p[..., 2]
        return ndi.gaussian_filter(np.sign(np.sin(across * np.pi / width + p[..., 4])).astype(np.float32), 0.7)

    def chm_at(self, E, N):
        X3, Y3 = self.chm_t.transform(E, N)
        tr = self.chm_tr
        return map_coordinates(self.chm_a, [(Y3 - tr.f) / tr.e - 0.5, (X3 - tr.c) / tr.a - 0.5], order=1, cval=0, prefilter=False)

    def _vectors(self):
        import pyproj
        from shapely import wkb
        tf = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32604', always_xy=True)
        E0, N0, E1, N1 = self.box
        def polys(g):
            for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
                if gg.geom_type == 'Polygon':
                    yield [np.stack(tf.transform(*np.array(gg.exterior.coords).T), 1)] + \
                          [np.stack(tf.transform(*np.array(r.coords).T), 1) for r in gg.interiors]
        def lines(g):
            for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
                if gg.geom_type == 'LineString':
                    yield np.stack(tf.transform(*np.array(gg.coords).T), 1)
        inbox = lambda P: P[:, 0].max() > E0 - 100 and P[:, 0].min() < E1 + 100 and P[:, 1].max() > N0 - 100 and P[:, 1].min() < N1 + 100
        self.golf, self.courses, self.landuse, self.ponds, self.pools, self.roads = [], [], [], [], [], []
        self.beaches, self.rocks = [], []
        if os.path.exists(f'{C}/ov_land.json'):
            for r in json.load(open(f'{C}/ov_land.json')):
                if r.get('class') not in ('beach', 'bare_rock'): continue
                for P in polys(wkb.loads(bytes.fromhex(r['geometry']))):
                    if inbox(P[0]): (self.beaches if r['class'] == 'beach' else self.rocks).append(P)
        for r in json.load(open(f'{C}/ov_land_use.json')):
            g = wkb.loads(bytes.fromhex(r['geometry']))
            for P in polys(g):
                if not inbox(P[0]): continue
                if r.get('subtype') == 'golf':
                    if r['class'] == 'golf_course': self.courses.append(P)
                    elif r['class'] == 'water_hazard': self.ponds.append(P)
                    else: self.golf.append((r['class'], P))
                elif r.get('class') in ('residential', 'grass', 'park', 'recreation_ground', 'resort', 'garden', 'pitch'):
                    self.landuse.append((r['class'], P))
        for r in json.load(open(f'{C}/ov_water.json')):
            if r.get('subtype') == 'ocean' or r.get('class') in ('cape', 'bay', 'waterfall', 'stream', 'spring', 'river'): continue
            g = wkb.loads(bytes.fromhex(r['geometry']))
            for P in polys(g):
                if not inbox(P[0]): continue
                (self.pools if r.get('class') == 'swimming_pool' else self.ponds).append(P)
        self._roads([r for r in json.load(open(f'{C}/ov_segment.json')) if r.get('subtype') == 'road'], lines, inbox)
        # buildings: world-feet footprints with eave height and roof colour (geodata/features.json)
        F = json.load(open(os.path.join(ROOT, 'geodata', 'features.json')))
        self.blds = []
        for b in F['buildings']:
            p = np.array(b['p']).reshape(-1, 2)
            E, N = world_to_utm(p[:, 0], p[:, 1])
            P = np.stack([E, N], 1)
            if inbox(P): self.blds.append((P, b['e'] * FT, np.array(b['r'], np.float32)))
        # the modelled Nā Hiku row (src/neighborhood.js keep): drawn as the lawns of its modelled lots
        k = keep_rect()
        kx, kz = [k[0], k[2], k[2], k[0]], [k[1], k[1], k[3], k[3]]
        self.keep = [np.stack(world_to_utm(np.array(kx, float), np.array(kz, float)), 1)]
        self._harbour()
        print(f'  beaches {len(self.beaches)} rock {len(self.rocks)}')
        print(f'  golf {len(self.golf)} courses {len(self.courses)} ponds {len(self.ponds)} pools {len(self.pools)} '
              f'roads {len(self.roads)} buildings {len(self.blds)}', flush=True)

    def _roads(self, segs, lines, inbox):
        """self.roads: (class, polyline, kind) for the drawn road segments. kind is 'road' (asphalt by class), 'drive'
        (a mapped driveway: pale concrete), 'cart' (a service road, track or path lying mostly inside a golf course
        outline: a narrow concrete cart path) or 'walk' (footways, paths, steps). Dead-end stubs are dropped: a chain
        of service, track or unknown segments (residential ones too, under 30 m) that ends in nothing and is shorter
        than 40 m in all, up to the first junction; driveways stay. Junctions are Overture's shared connectors."""
        from shapely import wkb
        from shapely.geometry import LineString, Polygon
        from shapely.ops import unary_union
        from collections import Counter, defaultdict
        n_at = Counter(c['connector_id'] for r in segs for c in r.get('connectors', []))
        S = {}
        for r in segs:
            g = wkb.loads(bytes.fromhex(r['geometry']))
            if g.geom_type != 'LineString' or r.get('class') not in ROAD_W: continue
            L = next(lines(g))
            cn = r.get('connectors') or []
            S[r['id']] = dict(cls=r['class'], sub=r.get('subclass'), L=L, len=float(np.hypot(*np.diff(L, axis=0).T).sum()),
                              a=cn[0]['connector_id'] if cn and cn[0]['at'] < 1e-6 else None,
                              b=cn[-1]['connector_id'] if cn and cn[-1]['at'] > 1 - 1e-6 else None)
        at = defaultdict(list)
        for k, s in S.items():
            for c in (s['a'], s['b']):
                if c: at[c].append(k)
        stub_ok = lambda s, tot: s['sub'] != 'driveway' and (s['cls'] in ('service', 'track', 'unknown', 'unclassified') or
                                                              (s['cls'] in ('residential', 'living_street') and tot < 30))
        drop = set()
        for k, s in S.items():
            for end, other in (('a', 'b'), ('b', 'a')):
                if s[end] is not None and n_at[s[end]] > 1: continue          # this end meets another segment
                chain, tot, cur, nxt = [k], s['len'], k, s[other]
                while nxt is not None and n_at[nxt] == 2 and tot < 40:       # on through plain joins, up to a junction
                    ks = [x for x in at[nxt] if x != cur]
                    if not ks: break
                    cur = ks[0]; chain.append(cur); tot += S[cur]['len']
                    nxt = S[cur]['b'] if S[cur]['a'] == nxt else S[cur]['a']
                if tot < 40 and all(stub_ok(S[x], tot) for x in chain): drop.update(chain)
        golf = unary_union([Polygon(P[0], P[1:]).buffer(0) for P in self.courses]) if self.courses else None
        kinds = Counter()
        for k, s in S.items():
            if k in drop or not inbox(s['L']): continue
            c = s['cls']
            if s['sub'] == 'driveway': kind = 'drive'
            elif c in ('footway', 'path', 'steps', 'pedestrian', 'track', 'service', 'unknown') and golf is not None and \
                    s['sub'] != 'parking_aisle' and len(s['L']) > 1 and \
                    LineString(s['L']).intersection(golf).length > 0.5 * max(s['len'], 1e-3):
                kind = 'cart'
            elif c in ('footway', 'path', 'steps', 'pedestrian'): kind = 'walk'
            else: kind = 'road'
            kinds[kind] += 1
            self.roads.append((c, s['L'], kind))
        n_drop = sum(1 for k in drop if inbox(S[k]['L']))
        print(f'  roads: {dict(kinds)}; {n_drop} dead-end stubs dropped '
              f'({sum(S[k]["len"] for k in drop if inbox(S[k]["L"])):.0f} m)', flush=True)

    def _harbour(self):
        """The water the Kukuiʻula Small Boat Harbor's breakwater shelters: no breaking surf drawn there. Sea within
        about 380 m of the harbour (OSM / Overture place, HARBOUR_UTM) whose line of sight toward the south swell
        (from 165-240 degrees, out to 400 m) runs into land, the breakwater; soft-edged. self.calm2: 0-1 on the 2 m
        grid; written into w_*.png G on sea pixels for the view's moving surf."""
        sea = self.sea2; E0, N0, E1, N1 = self.box; R = 2.0
        self.calm2 = np.zeros(sea.shape, np.float32)
        r0, c0 = int((N1 - HARBOUR_UTM[1]) / R), int((HARBOUR_UTM[0] - E0) / R)
        W = 250                                                                  # half window, cells (500 m)
        if not (W <= r0 < sea.shape[0] - W and W <= c0 < sea.shape[1] - W): return
        win = sea[r0 - W:r0 + W, c0 - W:c0 + W]; land = ~win
        rr, cc = np.mgrid[-W:W, -W:W].astype(np.float32)
        blocked = np.zeros(win.shape, np.float32); dirs = np.radians(np.linspace(165, 240, 11))
        for az in dirs:                                                          # compass direction the swell comes from
            dE, dN = np.sin(az), np.cos(az); hit = np.zeros(win.shape, bool)
            for s in np.arange(4, 400, R):
                r = np.clip(np.round(rr + W - dN * s / R).astype(int), 0, 2 * W - 1)
                c = np.clip(np.round(cc + W + dE * s / R).astype(int), 0, 2 * W - 1)
                hit |= land[r, c]
            blocked += hit
        blocked /= len(dirs)
        calm = blocked * win * np.clip((380 - np.hypot(rr, cc) * R) / 80, 0, 1)
        calm = ndi.gaussian_filter(np.clip((calm - 0.35) / 0.4, 0, 1), 3.0)
        self.calm2[r0 - W:r0 + W, c0 - W:c0 + W] = calm
        print(f'  harbour: {float((calm > 0.5).sum()) * 4:.0f} m2 of sheltered water', flush=True)


# ------------------------------------------------------------------ rasterising (2x supersampled)
class Canvas:
    def __init__(self, E0, N1, n, px, ny=None):
        self.E0, self.N1, self.n, self.px, self.ny = E0, N1, n, px, ny or n

    def xy(self, P, ss):
        return list(zip(((P[:, 0] - self.E0) / self.px) * ss, ((self.N1 - P[:, 1]) / self.px) * ss))

    def polys(self, items, ss=2, value=None):
        """items: list of rings-lists (outer, holes...) or (value, rings). Returns float mask (or value map)."""
        im = Image.new('L', (self.n * ss, self.ny * ss), 0); d = ImageDraw.Draw(im)
        for it in items:
            v, rings = (255, it) if value is None else (it[0], it[1])
            if len(rings[0]) < 3: continue
            d.polygon(self.xy(rings[0], ss), fill=v)
            for h in rings[1:]:
                if len(h) >= 3: d.polygon(self.xy(h, ss), fill=0)
        a = np.asarray(im, np.float32)
        if value is None:
            return a.reshape(self.ny, ss, self.n, ss).mean((1, 3)) / 255
        return a[ss // 2::ss, ss // 2::ss]

    def lines(self, items, ss=2):
        """items: (width m, polyline). Returns float coverage."""
        im = Image.new('L', (self.n * ss, self.ny * ss), 0); d = ImageDraw.Draw(im)
        for w, L in items:
            wpx = max(1, int(round(w / self.px * ss)))
            d.line(self.xy(L, ss), fill=255, width=wpx, joint='curve')
            r = wpx / 2
            for x, y in (self.xy(L[:1], ss) + self.xy(L[-1:], ss)):
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return np.asarray(im, np.float32).reshape(self.ny, ss, self.n, ss).mean((1, 3)) / 255


# drawn widths, m: the carriageway (a soft verge is added outside it), driveways and cart paths narrower (bake_tile)
ROAD_W = {'primary': 9.8, 'secondary': 9.0, 'tertiary': 8.0, 'residential': 6.8, 'living_street': 5.6, 'unclassified': 6.0,
          'unknown': 5.0, 'service': 4.0, 'pedestrian': 3.5, 'track': 3.0, 'footway': 1.6, 'path': 1.4, 'steps': 1.6}
DRIVE_W, CART_W = 3.2, 2.2
PAVED = ('primary', 'secondary', 'tertiary', 'residential', 'living_street', 'unclassified', 'unknown', 'service')
LINED = ('primary', 'secondary', 'tertiary')
HARBOUR_UTM = (449599, 2420102)   # Kukuiʻula Small Boat Harbor (OSM, via Overture places; geodata/community/places.json)
CALM_G = 80                       # w_*.png G on sea pixels: 80 x the harbour's calm (under the view's pond threshold, 0.4)
# w_*.png B on land, well inside it (LC_SHORE_M from the sea's edge) and off the ponds: 16 x the land-cover class + the
# dryness (0-15, from the 10 m NDVI: 0 at 0.62 and over, 15 at 0.22 and under); elsewhere B is the sea depth, as before
LC_NONE, LC_TURF, LC_GRASS, LC_SCRUB, LC_CANOPY, LC_SOIL, LC_ROCK, LC_SAND, LC_PAVED = range(9)
LC_NAMES = ['none', 'turf', 'grass', 'scrub', 'canopy', 'soil', 'rock', 'sand', 'paved']
LC_SHORE_M = 4.0


# ------------------------------------------------------------------ one tile
def blur(a, sigma):
    """Gaussian blur; wide ones on a reduced grid (same result to the eye, a fraction of the time)."""
    if sigma <= 8: return ndi.gaussian_filter(a, sigma)
    f = int(sigma // 4)
    h, w = a.shape
    small = a[:h - h % f, :w - w % f].reshape(h // f, f, w // f, f).mean((1, 3))
    small = ndi.gaussian_filter(small, sigma / f)
    big = ndi.zoom(small, f, order=1)
    out = np.empty_like(a); out[:big.shape[0], :big.shape[1]] = big[:h, :w]
    if big.shape[0] < h: out[big.shape[0]:] = out[big.shape[0] - 1]
    if big.shape[1] < w: out[:, big.shape[1]:] = out[:, big.shape[1] - 1:big.shape[1]]
    return out


def bake_tile(I, col, row, out):
    E0t = I.box[0] + col * TILE; N1t = I.box[3] - row * TILE
    n = TEX + 2 * MARGIN
    E0, N1 = E0t - MARGIN * PX, N1t + MARGIN * PX
    cv = Canvas(E0, N1, n, PX)
    e = E0 + (np.arange(n) + 0.5) * PX; nn = N1 - (np.arange(n) + 0.5) * PX
    E, N = np.meshgrid(e, nn)
    Eo = (E - I.box[0]).astype(np.float32); No = (N - I.box[1]).astype(np.float32)   # local metres: noise, stripes
    f32 = lambda a: np.asarray(a, np.float32)
    sl = (slice(MARGIN, MARGIN + TEX), slice(MARGIN, MARGIN + TEX))
    # land cover for w_*.png B (LANDCOVER): what each layer covers, in drawing order, reduced to the 512 px grid
    to_w = lambda m: np.asarray(Image.fromarray(np.ascontiguousarray(np.broadcast_to(f32(m), (n, n))[sl]), mode='F').resize((512, 512), Image.BOX))
    cover = []
    def over(a, c, m, cls=None):
        if cls is not None: cover.append((cls, to_w(m)))
        return a * (1 - m[..., None]) + c * m[..., None]

    # ---- measured layers
    dem = f32(I.grid_at(I.dem, 1.0, E, N))
    sdf = f32(I.grid_at(I.sdf2, 2.0, E, N, cval=-50.0))
    sea = np.clip(sdf / 1.2 + 0.5, 0, 1)                                    # soft sea coverage at the edge
    land = 1 - sea
    rf = I.s2_at(E, N, order=3)
    rf_s = np.stack([ndi.gaussian_filter(rf[..., k], 4) for k in range(4)], -1)   # the 10 m pixels, unblocked
    base = np.clip(rf_s[..., :3] * 1.18, 0, 1)
    ndvi = (rf_s[..., 3] - rf_s[..., 0]) / (rf_s[..., 3] + rf_s[..., 0] + 1e-6)          # bands: B04 B03 B02 B08
    redness = rf_s[..., 0] / (rf_s[..., 1] + 1e-4)
    lumS = lum(base)
    # canopy: the 1 m map rounded off over 0.5 m (no stair-stepped crown edges); thin lines of 'canopy' on bare ground
    # (under ~3 m across, over 6 m long, NDVI under 0.25: fences, walls, pad edges read as trees) are dropped
    chm = ndi.gaussian_filter(np.where(sdf > 0, 0, f32(I.chm_at(E, N))), 0.5 / PX).astype(np.float32)
    tall = chm > 1.6
    thin = tall & ~ndi.binary_opening(tall, iterations=int(round(1.5 / PX)))
    lab, nl = ndi.label(thin)
    if nl:
        objs = ndi.find_objects(lab)
        ext = np.array([0] + [max(s[0].stop - s[0].start, s[1].stop - s[1].start) * PX for s in objs])
        dry = np.asarray(ndi.mean(ndvi, lab, np.arange(1, nl + 1))) < 0.25
        line = np.zeros(nl + 1, bool); line[1:] = (ext[1:] > 6.0) & dry
        chm = np.where(ndi.binary_dilation(line[lab], iterations=2) & tall, 0, chm).astype(np.float32)
    del tall, thin, lab

    # ---- vector layers
    x1, y0 = E0 + n * PX, N1 - n * PX
    near = lambda P: P[:, 0].max() > E0 - 50 and P[:, 0].min() < x1 + 50 and P[:, 1].max() > y0 - 50 and P[:, 1].min() < N1 + 50
    ponds = cv.polys([P for P in I.ponds if near(P[0])])
    pools = cv.polys([P for P in I.pools if near(P[0])])
    courses = cv.polys([P for P in I.courses if near(P[0])])
    gl = [(c, P) for c, P in I.golf if near(P[0])]
    G = {k: cv.polys([P for c, P in gl if c == k]) for k in ('fairway', 'green', 'tee', 'bunker', 'driving_range')}
    manicured = cv.polys([P for c, P in I.landuse if near(P[0])])
    rd = [(c, L, k) for c, L, k in I.roads if near(L)]
    carriage = [(c, L) for c, L, k in rd if k == 'road' and c in PAVED]
    paved = ndi.gaussian_filter(cv.lines([(ROAD_W[c], L) for c, L in carriage]), 0.6)   # edge softened a little
    mains = cv.lines([(ROAD_W[c], L) for c, L in carriage if c in LINED])
    lanes = blur(cv.lines([(ROAD_W[c] * 0.55, L) for c, L in carriage if ROAD_W[c] >= 6]), 0.6 / PX)   # where the wheels run
    verge = np.clip(blur(cv.lines([(ROAD_W[c] + 2.4, L) for c, L in carriage]), 0.5 / PX) - paved, 0, 1)
    drives = np.clip(cv.lines([(DRIVE_W, L) for c, L, k in rd if k == 'drive']) - paved, 0, 1)
    carts = np.clip(cv.lines([(CART_W, L) for c, L, k in rd if k == 'cart']) - paved, 0, 1)
    walks = np.clip(cv.lines([(ROAD_W[c], L) for c, L, k in rd if k == 'walk' and c != 'path']) - paved - carts, 0, 1)
    trails = np.clip(cv.lines([(ROAD_W[c], L) for c, L, k in rd if k == 'walk' and c == 'path']) - paved - carts - walks, 0, 1)
    tracks = np.clip(cv.lines([(ROAD_W['track'], L) for c, L, k in rd if k == 'road' and c == 'track']) - paved, 0, 1)
    cline = cv.lines([(0.45, L) for c, L in carriage if c in LINED])
    bl = [(P, h, r) for P, h, r in I.blds if near(P)]
    bmask = cv.polys([[P] for P, h, r in bl])
    bh = cv.polys([(int(min(255, h * 10)), [P]) for P, h, r in bl], ss=1, value=True) / 10.0     # eave height, m
    broof = np.zeros((n, n, 3), np.float32)
    for k in range(3):
        if bl: broof[..., k] = cv.polys([(int(r[k] * 255), [P]) for P, h, r in bl], ss=1, value=True) / 255
    water = np.maximum(sea, ponds)
    chm = np.where(ponds > 0.5, 0, chm).astype(np.float32)                 # no crowns standing in the water (AO, normals, shadow)
    # the modelled row of lots: one lawn under the 3D homes, feathered into the ground around it over about 8 m with
    # an edge broken up at the metre scale (no rectangle, and no edge per lot)
    kin = cv.polys([I.keep]) > 0.5
    kd = (ndi.distance_transform_edt(~kin) - ndi.distance_transform_edt(kin)) * PX            # m, + outside
    keep = np.clip(0.5 - (kd + 6.0 * (fbm(Eo, No, 3.0, 3, 161) - 0.5)) / 8.0, 0, 1).astype(np.float32)
    del kin, kd

    # ---- golf. Where a course has (almost) no mapped fairways (Kukui'ula's), turf is inferred: bright, mown, tree-free
    # grass inside the course outline, lighter than the course around it in the 10 m colour
    turf_c = (chm < 1.2) & (ndvi > 0.42) & (bmask < 0.5) & (paved < 0.5) & (water < 0.5)
    turf_s = ndi.gaussian_filter(turf_c.astype(np.float32), 0.6)
    fair_inf = f32(I.grid_at(I.fair_inf2, 2.0, E, N, cval=0.0))             # inferred over the whole box (Inputs._golf_global)
    fair_inf = np.clip((fair_inf - 0.5) * 12 + 0.5, 0, 1) * turf_s          # a crisp, anti-aliased mown edge (about 0.8 m)
    others = np.clip(G['green'] + G['tee'] + G['bunker'], 0, 1)
    fairway = np.clip(np.maximum(G['fairway'] + G['driving_range'], fair_inf) - others, 0, 1)
    # first cut: a ring of slightly longer grass, about 2.5 m wide, around every fairway
    disk = np.hypot(*np.mgrid[-5:6, -5:6]) <= 2.5 / PX
    first_cut = np.clip(ndi.grey_dilation(fairway, footprint=disk) - fairway - others, 0, 1) * turf_s
    first_cut = ndi.gaussian_filter(first_cut, 0.7)
    rough = np.clip(((courses > 0.5) & turf_c).astype(np.float32) - fairway - first_cut - others, 0, 1)
    collar = np.clip(ndi.maximum_filter(G['green'], size=int(3 / PX)) - G['green'], 0, 1)
    lip = np.clip(ndi.maximum_filter(G['bunker'], size=int(1.6 / PX)) - G['bunker'], 0, 1)

    # ---- material masks
    trees = np.clip((chm - 1.6) / 2.0, 0, 1) * land * (1 - bmask)
    shrub = np.clip((chm - 0.5) / 1.0, 0, 1) * (1 - trees) * land * (ndvi > 0.3)
    near_sea = np.clip(1 - (-sdf) / 70, 0, 1) * land                       # within ~70 m of the sea
    # beaches: the mapped ones (OSM), widened to the bright, bare, low sand right beside them
    beach = cv.polys([P for P in I.beaches if near(P[0])])
    near_beach = blur(beach, 20 / PX) > 0.02
    sand = np.maximum(beach, near_sea * near_beach * (ndvi < 0.22) * (lumS > 0.11) * (dem < 5)) * (1 - trees) * land
    sand = blur(sand.astype(np.float32), 0.8 / PX)
    # the rest of the shore is the basalt bench (mapped bare rock, and the bare fringe within 30 m of the sea)
    rockp = cv.polys([P for P in I.rocks if near(P[0])])
    rock = np.maximum(rockp, near_sea * (ndvi < 0.35) * np.clip(1 - (-sdf) / 30, 0, 1)) * (1 - sand) * (1 - trees) * land
    # scrub (koa haole thickets and the like): dark, dense, untended; given a rough canopy surface for light and shade
    tended = np.clip(courses + manicured + paved + bmask + water, 0, 1)
    scrub = np.clip((0.075 - lumS) / 0.02, 0, 1) * np.clip((ndvi - 0.4) / 0.15, 0, 1) * (1 - tended) * (1 - trees) * land
    scrub = blur(scrub, 2.0 / PX)
    h_scrub = scrub * (0.5 * fbm(Eo, No, 2.2, 3, 141) + 0.5 * fbm(Eo, No, 0.9, 2, 143)) * 1.4

    g_fine = fbm(Eo, No, 1.1, 3, 11)[..., None]       # blades, clumps
    g_mid = fbm(Eo, No, 7.0, 3, 23)[..., None]        # patches
    g_big = fbm(Eo, No, 40.0, 2, 37)[..., None]       # broad unevenness

    # ---- compose, lowest first
    # Land is drawn as crisp patches of a few covers, not as the 10 m colour blown up: each cover's edge is the
    # satellite's own boundary, roughened at the metre scale, and each cover has its own surface. The colour of
    # each follows the measured colour around it (25 m), so dry, green and red country stay where they are.
    reg = np.stack([blur(base[..., k], 25 / PX) for k in range(3)], -1)
    def follow(c, ref, k=0.6):                            # a cover colour, tinted by how the place differs from it
        return c * np.clip(reg / np.maximum(ref, 1e-3), 0.7, 1.35) ** k
    edge_n = 0.7 * (fbm(Eo, No, 3.0, 3, 151) - 0.5) + 0.3 * (fbm(Eo, No, 0.8, 2, 153) - 0.5)
    crisp = lambda score, w=0.10: np.clip((score + 0.24 * edge_n) / w + 0.5, 0, 1)
    pasture = np.array([0.070, 0.112, 0.038], np.float32)
    lawn_c = np.array([0.066, 0.135, 0.040], np.float32)
    a = follow(pasture, pasture) * (0.84 + 0.30 * g_fine) * (0.90 + 0.20 * g_mid)
    lawn = (manicured > 0.5).astype(np.float32)
    a = over(a, follow(lawn_c, pasture) * (0.93 + 0.12 * g_fine), lawn, LC_TURF)
    # soil (Kaua'i red earth, graded pads): clods, tyre-track streaks, a dry crust; a weathered ochre-red, not rust
    soil_m = crisp(np.clip((0.36 - ndvi) / 0.1, -1, 1) * 0.5 + np.clip((redness - 1.05) / 0.15, -1, 1) * 0.5 - 0.35) * land * (1 - sand) * (1 - rock) * (1 - lawn)
    # softened by 2 m and broken up where it meets the grass (grass thinning into dirt), so a patch does not read as paint
    soil_m = blur(soil_m, 2.0 / PX)
    soil_m = np.clip(soil_m + 10.0 * (fbm(Eo, No, 0.9, 3, 57) - 0.5) * soil_m * (1 - soil_m), 0, 1)
    red = np.array([0.158, 0.100, 0.066], np.float32)
    clods = fbm(Eo, No, 0.6, 3, 51)[..., None]
    a = over(a, follow(red, red, 0.45) * (0.80 + 0.36 * clods) * (0.94 + 0.12 * g_mid), soil_m, LC_SOIL)
    # a band of dry grass where the dirt thins into the grass
    straw = follow(np.array([0.150, 0.125, 0.062], np.float32), pasture, 0.4) * (0.85 + 0.3 * g_fine)
    a = over(a, straw, 4 * soil_m * (1 - soil_m) * 0.4 * np.clip(fbm(Eo, No, 1.6, 2, 59) * 2 - 0.5, 0, 1))
    # scrub: a dark, lumpy thicket surface (lit live by the normals below)
    scrub_m = crisp(scrub - 0.45, 0.08)
    thicket = np.array([0.034, 0.052, 0.022], np.float32)
    a = over(a, follow(thicket, thicket) * (0.62 + 0.62 * fbm(Eo, No, 1.3, 3, 95)[..., None]), np.maximum(shrub * 0.8, scrub_m), LC_SCRUB)
    # golf turf: rough darker, a first cut, fairways with mower stripes (a natural green, not lime), greens finer with a
    # collar, white sand
    a = over(a, follow(np.array([0.058, 0.112, 0.034], np.float32), pasture) * (0.86 + 0.26 * g_fine), rough, LC_GRASS)
    fair_c = follow(np.array([0.074, 0.160, 0.050], np.float32), pasture)          # was lime (0.086, 0.170, 0.044) * (0.96 + 0.08 * g_fine) * (0.93 + 0.14 * g_mid)
    a = over(a, fair_c * np.array([0.90, 0.86, 0.88], np.float32) * (0.95 + 0.1 * g_fine), first_cut, LC_TURF)
    st = I.stripes_at(E, N, Eo, No, 6.0)
    a = over(a, fair_c * (1 + 0.10 * st[..., None]), fairway, LC_TURF)
    a = over(a, fair_c * 1.03 * (1 + 0.08 * st[..., None]), G['tee'], LC_TURF)
    green_diag = ndi.gaussian_filter(np.sign(np.sin((Eo + No) * np.pi / 3.0)).astype(np.float32), 0.7)   # diagonal passes, 3 m
    green_c = sat(np.array([0.105, 0.235, 0.060], np.float32), 0.9) * (1 + 0.035 * green_diag[..., None]) * (0.97 + 0.06 * g_fine)
    a = over(a, green_c * 0.86, collar, LC_TURF)
    a = over(a, green_c, G['green'], LC_TURF)
    bunker_c = np.array([0.72, 0.66, 0.53], np.float32) * (0.93 + 0.1 * fbm(Eo, No, 0.5, 2, 101)[..., None])
    a = over(a, bunker_c * 0.62, lip, LC_SAND)
    a = over(a, bunker_c, G['bunker'], LC_SAND)
    # sand: warm, bright, wind ripples, darker where wet at the water's edge
    rip = 0.5 + 0.5 * np.sin((Eo * 0.8 + No * 0.6) * 2.2 + 3 * fbm(Eo, No, 6, 2, 61))
    sand_c = np.array([0.52, 0.45, 0.33], np.float32) * (0.92 + 0.08 * rip[..., None]) * (0.94 + 0.12 * g_fine)
    sand_c = sand_c * (1 - 0.38 * np.clip(1 - (-sdf) / 5, 0, 1))[..., None]
    a = over(a, sand_c, sand, LC_SAND)
    # rock: dark basalt shelf, rough, wet near the sea
    rock_c = np.array([0.075, 0.068, 0.060], np.float32) * (0.7 + 0.6 * fbm(Eo, No, 0.9, 4, 71)[..., None])
    a = over(a, rock_c * (1 - 0.35 * np.clip(1 - (-sdf) / 6, 0, 1))[..., None], rock, LC_ROCK)
    # the modelled lots: one lawn (the homes, drives and pools are 3D in the view), tinted like the grass around it,
    # its mowing stripes fading out toward the feathered edge
    kst = np.sign(np.sin((Eo * 0.7 + No * 0.7) * np.pi / 4.0)) * keep ** 2
    a = over(a, follow(lawn_c, pasture, 0.3) * (0.94 + 0.10 * g_fine) * (1 + 0.04 * kst)[..., None], keep * land, LC_TURF)
    # roads, drives, cart paths and paths: a soft verge (worn grass and dust) instead of a kerb line, a light weathered
    # asphalt (patched, the main roads a little darker and fresher), pale concrete drives, narrow cart paths shaded
    # under the trees beside them, and paths that read as worn ground rather than white strokes
    vn = np.clip(fbm(Eo, No, 1.5, 2, 171) * 1.8 - 0.4, 0, 1)
    a = over(a, sat(a, 0.55) * 1.22 * (0.9 + 0.2 * g_fine), verge * 0.32 * vn)
    a = over(a, sat(base, 0.8) * 1.15 * (0.9 + 0.2 * g_fine), tracks * 0.7, LC_SOIL)
    a = over(a, sat(reg, 0.55) * 1.35 * (0.9 + 0.2 * g_fine), trails * 0.6, LC_SOIL)
    a = over(a, np.array([0.200, 0.192, 0.176], np.float32) * (0.92 + 0.12 * g_fine), walks * 0.75, LC_PAVED)
    shade = 1 - 0.45 * np.clip(blur(trees, 1.5 / PX) * 2, 0, 1)
    a = over(a, np.array([0.186, 0.176, 0.152], np.float32) * (0.92 + 0.12 * g_fine) * shade[..., None], carts * 0.8, LC_PAVED)
    a = over(a, np.array([0.235, 0.226, 0.206], np.float32) * (0.92 + 0.12 * g_fine), drives * 0.9, LC_PAVED)
    asphalt = np.array([0.105, 0.099, 0.092], np.float32) * (0.86 + 0.28 * fbm(Eo, No, 0.35, 2, 121)[..., None]) \
        * (0.90 + 0.20 * fbm(Eo, No, 6.0, 2, 125)[..., None]) * (0.95 + 0.1 * g_big) * (1 - 0.14 * mains - 0.07 * lanes)[..., None]
    a = over(a, asphalt, paved, LC_PAVED)
    a = over(a, np.array([0.42, 0.33, 0.10], np.float32), cline * paved * 0.5)
    # pools with their coping, roofs (the 3D buildings stand on these), crowns, ponds
    a = over(a, np.array([0.10, 0.42, 0.50], np.float32) * (0.85 + 0.3 * g_big), pools, LC_PAVED)
    a = over(a, np.array([0.62, 0.60, 0.55], np.float32), np.clip(ndi.maximum_filter(pools, size=int(1.0 / PX)) - pools, 0, 1), LC_PAVED)
    a = over(a, broof * (0.92 + 0.12 * g_fine), bmask, LC_PAVED)
    # crowns: a leaf palette (monkeypod and Java plum deep green, kiawe and koa haole olive, ironwood grey-green, a
    # fresher green), one blend per crown-sized cell with jitter and only a light pull toward the place's own tint, not
    # the 10 m ground colour under them (which drew pasture-green and soil-coloured crowns)
    pal = np.array([[0.032, 0.063, 0.021], [0.047, 0.066, 0.023], [0.042, 0.062, 0.027], [0.040, 0.080, 0.024],
                    [0.030, 0.056, 0.021]], np.float32)
    crown = pal[np.minimum((cells(Eo, No, 5.0, 97) * len(pal)).astype(np.int32), len(pal) - 1)]
    crown = np.stack([ndi.gaussian_filter(crown[..., k], 0.5 / PX) for k in range(3)], -1)     # soft where crowns meet
    crown = crown * np.clip(reg / pasture, 0.8, 1.25) ** 0.3 * (0.88 + 0.24 * vnoise(Eo, No, 3.5, 99))[..., None]
    crown = crown * (1 + (0.045 / np.maximum(crown[..., 1:2], 1e-4)) ** 4) ** 0.25   # floored at about 0.045 in green
    tint = (0.85 + 0.3 * fbm(Eo, No, 9, 2, 81))[..., None]
    leaf = fbm(Eo, No, 0.8, 3, 91)
    tree_c = crown * tint * (0.72 + 0.5 * leaf[..., None])
    tree_c[..., 0] *= (0.9 + 0.25 * vnoise(Eo, No, 11, 93))               # some crowns warmer (monkeypod, kiawe), some cooler
    a = over(a, tree_c, trees, LC_CANOPY)
    del tree_c, crown, sand_c, rock_c, asphalt, fair_c, straw
    a = over(a, np.array([0.028, 0.062, 0.058], np.float32) * (0.9 + 0.2 * g_big), ponds * land)

    # sea: coloured by its real depth (USACE 2013 topobathy). Light crosses the water to the bottom and back:
    # red is gone within a few metres, blue lasts. Bottom: sand where the seafloor is smooth, reef where rough.
    bat = f32(I.grid_at(I.bathy, 1.0, E, N))
    depth = np.where(np.isnan(bat), np.clip(sdf * 0.4, 0, 60), np.clip(-bat, 0, 80)).astype(np.float32)
    br = np.nan_to_num(bat, nan=-60.0)
    rough_b = np.sqrt(np.clip(blur(br * br, 1.5 / PX) - blur(br, 1.5 / PX) ** 2, 0, None))
    gapf = f32(I.grid_at(I.bfill, 1.0, E, N, order=0, cval=0))              # survey gaps filled in Inputs: the bottom
    if gapf.any():                                                          # there is as rough as the reef around it
        gapf = blur(gapf, 1.0 / PX); ok = 1 - gapf
        rough_b = rough_b * ok + blur(rough_b * ok, 8 / PX) / np.maximum(blur(ok, 8 / PX), 1e-3) * gapf
    sandy = blur(np.clip(1 - rough_b / 0.3, 0, 1), 2 / PX)[..., None]
    reef_c = np.array([0.12, 0.10, 0.065], np.float32) * (0.6 + 0.8 * fbm(Eo, No, 1.8, 4, 131))[..., None]
    sandb_c = np.array([0.55, 0.50, 0.38], np.float32) * (0.9 + 0.2 * fbm(Eo, No, 3, 2, 133))[..., None]
    T = np.exp(-2 * np.array([0.42, 0.075, 0.048], np.float32) * depth[..., None])
    sea_c = (reef_c * (1 - sandy) + sandb_c * sandy) * T + I.deep_rgb * (1 - T)
    # waves breaking on the reef crests, and the swash at the shore; none breaking inside the harbour's breakwater
    # (Inputs._harbour), only a little lapping at its shore
    calm = f32(I.grid_at(I.calm2, 2.0, E, N, cval=0.0)) if hasattr(I, 'calm2') else np.zeros_like(sdf)
    crest = np.clip((2.6 - depth) / 1.6, 0, 1) * np.clip(depth / 0.4, 0, 1) * (sdf > 3) * (1 - calm)
    foam = crest * np.clip(fbm(Eo, No, 4, 3, 113) * 2.2 - 0.9, 0, 1)
    foam = np.maximum(foam, np.clip(1 - sdf / 4, 0, 1) * (sdf > -0.5) * np.clip(fbm(Eo, No, 2.0, 3, 111) * 1.8 - 0.45, 0, 1) * (1 - 0.7 * calm))
    sea_c = sea_c * (1 - 0.85 * foam[..., None]) + 0.7 * 0.85 * foam[..., None]
    # land grade: the 10 m median mosaic is flatter than any one clear morning
    a = over(a, sat(a, 1.15) * 1.05, land)
    a = over(a, sea_c, sea)
    del sea_c

    # ---- static ambient occlusion from everything that stands up (ground, canopy, buildings)
    # under woody cover (crowns, thickets) the broad term is softened, so tree-filled gullies keep their shape but are
    # not crushed black under the live shadows; the crown-scale terms keep the gaps between crowns
    woody = np.clip(trees + np.maximum(shrub * 0.8, scrub_m) * (1 - trees), 0, 1) * land
    # lone crowns (canopy patches under 150 m2): the view stands a 3D tree on each (realsite trees), so the ground is
    # not also raised into a shaded mound under it: a fifth of their relief stays in the normals, 40% in the
    # occlusion; their traced shadow (cast height) stays. Woods keep their full rounded canopy.
    lab, nl = ndi.label(chm > 2.0)
    lone = np.zeros_like(chm)
    if nl:
        small = np.bincount(lab.ravel(), minlength=nl + 1) * PX * PX < 150; small[0] = False
        lone = blur(ndi.binary_dilation(small[lab], iterations=int(2.5 / PX)).astype(np.float32), 0.8 / PX)   # over the crown's whole edge
    del lab
    hs = np.where(sea > 0.5, 0, dem) + chm * 0.9 * (1 - 0.6 * lone) + bh * (bmask > 0.5) + h_scrub
    ao = np.ones_like(hs)
    for r, k in ((1.2, 0.20), (3.5, 0.10), (9.0, 0.045)):
        d = blur(hs, r / PX) - hs
        ao *= np.clip(1 - k * np.clip(d, 0, None), 0.45, 1) ** (1 - 0.6 * woody if r > 5 else 1)
    ao = np.where(bmask > 0.5, 1, ao)                                     # roofs are 3D, lit live
    a = a * (land * ao + (1 - land))[..., None]
    # and nothing woody ends darker than about 0.045 in green (a smooth floor that follows the leaf texture)
    floor = 0.045 * (0.86 + 0.28 * leaf)
    lift = np.minimum((1 + (floor / np.maximum(a[..., 1], 1e-4)) ** 4) ** 0.25, 3.0)
    a = a * (1 + (lift - 1) * woody)[..., None]
    del leaf, floor, lift

    # ---- the outer 150 m of the box hands over to the plain satellite colour (the view's other ground); over the sea
    # with the glint offset taken off as for the open-sea colour (eased in over the first 20 m, where 10 m pixels
    # still hold land)
    edge = np.minimum.reduce([E - I.box[0], I.box[2] - E, N - I.box[1], I.box[3] - N]).astype(np.float32)
    hand = np.clip(edge / 150, 0, 1)[..., None]
    rf_c = np.maximum(rf[..., :3] - np.clip(sdf / 20, 0, 1)[..., None] * rf[..., 3:4], 0.002)
    a = a * hand + np.clip(rf_c * 1.18, 0, 1) * (1 - hand)
    del rf_c

    # ---- crop and write
    img = Image.fromarray((lin2srgb(a[sl]) * 255 + 0.5).astype(np.uint8))
    tag = f'{col}_{row}'
    img.save(f'{out}/a_{tag}.webp', quality=84, method=5)
    img.resize((512, 512), Image.LANCZOS).save(f'{out}/s_{tag}.webp', quality=84, method=5)

    # normals of the lit surface (lidar ground + rounded crowns); cast height for live shadows
    # under thick vegetation the lidar found little ground and drew big flat facets: soften them there
    veg = np.clip(scrub + trees + shrub, 0, 1)
    dem_l = dem + (blur(dem, 2.0 / PX) - dem) * veg
    hl = np.where(sea > 0.5, 0, dem_l) + ndi.gaussian_filter(chm, 0.6 / PX) * (chm > 1.0) * (1 - 0.8 * lone) + h_scrub
    hl = ndi.gaussian_filter(hl, 0.5)
    dE = ndi.sobel(hl, 1) / (8 * PX); dN = -ndi.sobel(hl, 0) / (8 * PX)    # rows run south
    nz = 1 / np.sqrt(1 + dE ** 2 + dN ** 2)
    # water is flat; the modelled lots stand on their own levels, and their lawn's feathered edge eases into the lidar
    nE = np.where(water > 0.5, 0, -dE * nz) * (1 - keep); nN = np.where(water > 0.5, 0, -dN * nz) * (1 - keep)
    cast = np.clip(np.maximum.reduce([chm * (chm > 1.0), bh * (bmask > 0.5), h_scrub]) * 10, 0, 255)
    nrm = np.stack([128 + 127 * nE, 128 + 127 * nN, cast], -1)
    # halved with its margin, then cropped (border texels filtered from both sides, so neighbours meet); lossless:
    # lossy WebP's YUV 4:2:0 would bleed the cast height's sharp crown edges into the normals, blur the heights,
    # and break both at every tile border
    m2, t2 = MARGIN // 2, TEX // 2
    Image.fromarray(np.clip(nrm, 0, 255).astype(np.uint8)).resize((n // 2, n // 2), Image.BILINEAR).crop((m2, m2, m2 + t2, m2 + t2)) \
        .save(f'{out}/n_{tag}.webp', lossless=True, quality=100, method=6)
    # water data: R sea distance, G pond water (land) or the harbour's calm (sea), B sea depth; then, on land well away
    # from the sea and the ponds, B carries the land cover (LANDCOVER) for the view's close-range ground detail
    wimg = np.stack([np.clip(128 + SDF_PER_M * sdf, 0, 255), np.maximum(ponds * 255, calm * CALM_G * sea),
                     np.clip(depth * 10, 0, 255) * sea], -1)[sl]
    if os.environ.get('COMM_DEBUG'):
        dbg = np.stack([ponds, courses, manicured], -1)[sl]
        Image.fromarray((dbg * 255).astype(np.uint8)).resize((1024, 1024)).save(f'{out}/../dbg_{col}_{row}.png')
    w = np.array(Image.fromarray(wimg.astype(np.uint8)).resize((512, 512), Image.BILINEAR))
    wc = np.zeros((512, 512, 9), np.float32); wc[..., LC_GRASS] = 1                # the pasture everything is drawn over
    for cls, m in cover:
        wc *= (1 - m)[..., None]; wc[..., cls] += m
    dryness = np.clip(np.round((0.62 - to_w(ndvi)) / 0.4 * 15), 0, 15)
    code = (wc.argmax(-1) * 16 + dryness).astype(np.uint8)
    inland = ((w[..., 0].astype(np.float32) - 128) / SDF_PER_M < -LC_SHORE_M) & (w[..., 1] < 8)
    w[..., 2] = np.where(inland, code, w[..., 2])
    Image.fromarray(w).save(f'{out}/w_{tag}.png', optimize=True)
    return {'c': col, 'r': row, 'sea': round(float(sea[sl].mean()), 3)}


def heights(I, grade):
    """Ground heights for the tile meshes: 5 m, world feet; flat sea at sea level, each pond level at its lidar water
    surface (no higher than its bank)."""
    E0, N0, E1, N1 = I.box
    nr, nc = int((N1 - N0) / HRES), int((E1 - E0) / HRES)
    d = I.dem[:nr * 5, :nc * 5].reshape(nr, 5, nc, 5)
    with np.errstate(invalid='ignore'):
        h = np.nanmean(d, axis=(1, 3))
    sea = ndi.zoom(I.sea2.astype(np.float32), 0.4, order=1)[:nr, :nc] > 0.5
    h = np.where(sea | np.isnan(h), 0.0, h)
    # ponds, one polygon at a time (touching ponds of a cascade keep their own levels; cells more than half covered):
    # the median of the 1 m DEM inside it (3DEP flattens water surfaces), capped at the lower quarter of its bank
    pm = [Canvas(E0, N1, nc, HRES, nr).polys([P], ss=4) > 0.5 for P in I.ponds]
    anyp = np.logical_or.reduce(pm) if pm else np.zeros((nr, nc), bool)
    h0 = h.copy()
    for P, m in zip(I.ponds, pm):
        if not m.any(): continue
        x0 = int(max(0, P[0][:, 0].min() - E0)); x1 = int(min(I.dem.shape[1], P[0][:, 0].max() - E0 + 1))
        y0 = int(max(0, N1 - P[0][:, 1].max())); y1 = int(min(I.dem.shape[0], N1 - P[0][:, 1].min() + 1))
        if x1 <= x0 or y1 <= y0: continue
        m1 = Canvas(E0 + x0, N1 - y0, x1 - x0, 1.0, y1 - y0).polys([P]) > 0.5; m1e = ndi.binary_erosion(m1, iterations=2)
        if not m1.any(): continue
        lvl = float(np.median(I.dem[y0:y1, x0:x1][m1e if m1e.sum() >= 10 else m1]))
        rim = ndi.binary_dilation(m, iterations=1) & ~anyp & ~sea
        if rim.any(): lvl = min(lvl, float(np.percentile(h0[rim], 25)))
        h[m] = lvl - 0.1
    y = (h - LOT_GROUND_M) / FT + grade
    hmin, hmax = float(y.min()) - 1, float(y.max()) + 1
    q = np.round((y - hmin) / (hmax - hmin) * 65535).astype('<u2')
    q.tofile(f'{OUT}/h.bin')
    return {'file': 'h.bin', 'cols': nc, 'rows': nr, 'res_m': HRES, 'hmin': hmin, 'hmax': hmax}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    (_, _), plan = plan_lot_centre(); grade = plan.get('grade', -0.6)
    I = Inputs()
    cols = int((I.box[2] - I.box[0]) / TILE); rows = int((I.box[3] - I.box[1]) / TILE)
    todo = [(c, r) for r in range(rows) for c in range(cols)]
    if args.only:
        todo = [tuple(int(v) for v in t.split(',')) for t in args.only.split(';')]
    for c, r in todo:
        print(f'tile {c},{r}', flush=True)
        bake_tile(I, c, r, OUT)
    tiles = [{'c': c, 'r': r} for r in range(rows) for c in range(cols) if os.path.exists(f'{OUT}/a_{c}_{r}.webp')]
    hgrid = heights(I, grade)
    ex, ez = world_axes()
    (px, pz), _ = plan_lot_centre()
    meta = {
        'about': "Kukui'ula community map tiles: a map rendering of open data (not an aerial photograph). North-up UTM 4N tiles, 1 km, row 0 at the north edge.",
        'crs': 'EPSG:32604', 'box': list(I.box), 'tile_m': TILE, 'cols': cols, 'rows': rows, 'tex': TEX,
        # world feet (x, z) = origin + (E - lotE) / 0.3048 * east + (N - lotN) / 0.3048 * north
        'toWorld': {'lotUTM': list(LOT_UTM), 'origin': [px, pz], 'east': [float(ex[0]), float(ez[0])], 'north': [float(ex[1]), float(ez[1])], 'ft': FT},
        'heights': hgrid,
        'tiles': tiles,
        'encoding': {'n': 'R,G = 128 + 127 * normal (east, north); B = 10 * height of canopy or eave (m); lossless',
                     'w': 'R = 128 + sdfPerM * signed distance to the sea edge (m, sea positive; 1 per m, +-127 m); '
                          f'G = 255 in ponds drawn as water, and on the sea {CALM_G} * calm (0-1) inside the harbour breakwater (no breaking surf); '
                          f'B = 10 * sea depth (m), except on land more than {LC_SHORE_M:g} m from the sea and off the ponds (R < {128 - LC_SHORE_M * SDF_PER_M:g}, G < 8), '
                          'where B = 16 * landCover + dryness (0-15, from NDVI: 0 at 0.62 and over, 15 at 0.22 and under)',
                     'landCover': LC_NAMES},
        'sdfPerM': SDF_PER_M,                                   # w_*.png R steps per metre of sea distance
        'deepSea': [round(float(v), 4) for v in I.deep_rgb],   # linear albedo of the open sea in the tiles (glint taken off)
        # one line each, for the view's credits (with places.json's own attribution)
        'attribution': [
            'Ground: U.S. Geological Survey 3DEP 1 m lidar DEM (2019–21), public domain',
            'Seafloor: USACE NCMP 2013 Kauaʻi topobathy lidar, via NOAA Digital Coast, public domain',
            'Contains modified Copernicus Sentinel data 2023–2026 (colour)',
            'Trees: Meta and World Resources Institute, High Resolution Canopy Height Maps (Tolan et al. 2024), CC BY 4.0, modified (resampled and drawn as crowns, shading and shadows)',
            'Roads, paths, water, beaches, golf: © OpenStreetMap contributors, and some roads © TomTom (ODbL), via Overture Maps Foundation',
            'Buildings: © OpenStreetMap contributors, Microsoft ML Building Footprints (ODbL), via Overture Maps Foundation',
        ],
    }
    json.dump(meta, open(f'{OUT}/community.json', 'w'), indent=1)
    tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f'{len(tiles)} tiles, {tot / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
