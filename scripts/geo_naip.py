#!/usr/bin/env python3
"""USDA NAIP aerial photo over the Kukui'ula community box -> <cache>/naip_comm.npy (+ .json).

USDA Farm Service Agency, National Agriculture Imagery Program (NAIP), 2021-2023 Hawai'i, 4-band (red, green, blue,
near-infrared), 8 bit, 0.6 m; the community box was flown on 11 Feb 2022. Distributed by NOAA Digital Coast
(dataset 9668, InPort item 69406): "Use Constraints: None. The USDA-FSA Aerial Photography Field office asks to be
credited in derived products." Only the quarter-quad tiles that touch the box (with the bake's 100 m margin) are
fetched; the same tile listed twice under two dates (identical files) is fetched once.

The tiles (NAD83 / UTM 4N, EPSG:26904) are reprojected to WGS84 / UTM 4N (EPSG:32604), cubic, onto the community
bake's own texel grid: 1000 / 2048 m (0.488 m), the box E 447500-453500, N 2418000-2423000 plus MARGIN texels on
every side, so a tile of scripts/geo_community.py is an exact slice. Where two tiles overlap they are feathered
over 15 m toward the middle of the overlap. No data (outside every tile: open sea at the box's south-west corner)
stays 0 in all four bands.
    python3 scripts/geo_naip.py            # downloads into <cache>/../naip unless the files are there
"""
import os, sys, json, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import cache_dir
from geo_dem1m import COMM_BOX

BASE = 'https://coastalimagery.blob.core.windows.net/digitalcoast/HI_NAIP_2021_9668/'
ITEMS = BASE + 'stac/noaa_imagery_item_collection_m9668.json'
PX = 1000.0 / 2048
MARGIN = 200                     # texels, as scripts/geo_community.py
FEATHER_M = 15.0


def main():
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    from pyproj import Transformer
    from shapely.geometry import shape, box
    from shapely import transform as stransform
    from scipy import ndimage as ndi
    c = cache_dir()
    dl = os.path.normpath(os.path.join(c, '..', 'naip')); os.makedirs(dl, exist_ok=True)
    E0, N0, E1, N1 = COMM_BOX
    gE0, gN1 = E0 - MARGIN * PX, N1 + MARGIN * PX
    W, H = int(round((E1 - E0) / PX)) + 2 * MARGIN, int(round((N1 - N0) / PX)) + 2 * MARGIN
    dst_tr = from_origin(gE0, gN1, PX, PX)
    # the tiles that touch the grid
    ip = os.path.join(dl, 'items.json')
    if not os.path.exists(ip):
        subprocess.run(['curl', '-sS', '-f', '-o', ip, ITEMS], check=True)
    t = Transformer.from_crs(32604, 4326, always_xy=True)
    g = box(gE0, gN1 - H * PX, gE0 + W * PX, gN1)
    g = stransform(g, lambda xy: np.stack(t.transform(xy[:, 0], xy[:, 1]), -1))
    picked = {}
    for f in json.load(open(ip))['features']:
        if not shape(f['geometry']).intersects(g): continue
        qq = '_'.join(f['id'].split('_')[:3])                 # m_2115905_sw: one quarter quad
        if qq in picked and picked[qq]['id'] <= f['id']: continue
        picked[qq] = f
    srcs = []
    for qq, f in sorted(picked.items()):
        href = next(iter(f['assets'].values()))['href']
        p = os.path.join(dl, os.path.basename(href))
        if not os.path.exists(p):
            print('download', href, flush=True)
            subprocess.run(['curl', '-sS', '-f', '-C', '-', '-o', p, href], check=True)
        srcs.append((f['id'], f['properties']['datetime'][:10], p))
    print(len(srcs), 'tiles:', ', '.join(s[0] for s in srcs), flush=True)

    # in strips of rows (the whole grid in float would not fit in memory); each tile's weight is worked out on an
    # 8x coarser grid: its valid footprint, and the distance into it, feathered over FEATHER_M
    K = 8
    cH, cW = -(-H // K), -(-W // K)
    wks = []
    for sid, date, p in srcs:
        with rasterio.open(p) as ds:
            cv = np.zeros((cH, cW), np.float32)
            reproject(rasterio.band(ds, 1), cv, dst_transform=from_origin(gE0, gN1, PX * K, PX * K), dst_crs='EPSG:32604',
                      src_nodata=0, dst_nodata=0, resampling=Resampling.nearest)
        valid = ndi.binary_erosion(cv > 0, iterations=1)
        wks.append(np.clip(ndi.distance_transform_edt(valid) * PX * K / FEATHER_M, 0, 1).astype(np.float32))
        print(f'  {sid}: {valid.mean():.0%} of the grid', flush=True)
    q = np.lib.format.open_memmap(f'{c}/naip_comm.npy', mode='w+', dtype=np.uint8, shape=(H, W, 4))
    S = 1024
    dss = [rasterio.open(p) for _, _, p in srcs]
    for r0 in range(0, H, S):
        h = min(S, H - r0)
        rr, cc = np.meshgrid((np.arange(r0, r0 + h) + 0.5) / K - 0.5, (np.arange(W) + 0.5) / K - 0.5, indexing='ij')
        acc = np.zeros((h, W, 4), np.float32); wsum = np.zeros((h, W), np.float32)
        for ds, wc in zip(dss, wks):
            wk = ndi.map_coordinates(wc, [rr, cc], order=1, mode='nearest').astype(np.float32)
            if wk.max() <= 0: continue
            img = np.zeros((4, h, W), np.float32)
            for b in range(4):
                reproject(rasterio.band(ds, b + 1), img[b], dst_transform=from_origin(gE0, gN1 - r0 * PX, PX, PX),
                          dst_crs='EPSG:32604', src_nodata=0, dst_nodata=0, resampling=Resampling.cubic)
            wk *= (img[:3] > 0).any(0)
            acc += np.moveaxis(img, 0, -1) * wk[..., None]; wsum += wk
            del img
        ok = wsum > 1e-3
        acc[ok] /= wsum[ok][:, None]
        o = np.clip(np.round(acc), 0, 255).astype(np.uint8); o[~ok] = 0
        o[ok & (o[..., :3].max(-1) == 0)] = 1                     # 0 everywhere means no data
        q[r0:r0 + h] = o
        print(f'  rows {r0}-{r0 + h}: {ok.mean():.0%} covered', flush=True)
    q.flush()
    ok = q[::8, ::8, :3].max(-1) > 0
    meta = {'grid': [gE0, gN1 - H * PX, gE0 + W * PX, gN1], 'res': PX, 'shape': [H, W], 'margin_px': MARGIN,
            'box': list(COMM_BOX), 'crs': 'EPSG:32604', 'bands': ['red', 'green', 'blue', 'nir'],
            'tiles': [{'id': s, 'date': d} for s, d, _ in srcs],
            'source': 'USDA FSA NAIP 2021-2023 Hawaii 4-band, NOAA Digital Coast dataset 9668 (InPort 69406)'}
    json.dump(meta, open(f'{c}/naip_comm.json', 'w'), indent=1)
    print('naip_comm', q.shape, f'{ok.mean():.1%} covered', flush=True)


if __name__ == '__main__':
    main()
