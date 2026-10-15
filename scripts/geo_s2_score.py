#!/usr/bin/env python3
"""Score Sentinel-2 scenes by how clear they are over the area of interest, from the L2A scene
classification (SCL) read at a coarse overview with HTTP range requests.
    python3 scripts/geo_s2_score.py <cache_dir>
Reads <cache>/s2_scenes.json, writes <cache>/s2_scores.json.
SCL classes: 0 nodata, 1 saturated, 2 dark, 3 cloud shadow, 4 veg, 5 bare, 6 water, 7 unclassified,
8 cloud medium, 9 cloud high, 10 cirrus, 11 snow.
"""
import os, sys, json, numpy as np, concurrent.futures as cf
os.environ.setdefault('CURL_CA_BUNDLE', '/root/.ccr/ca-bundle.crt')
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
os.environ['GDAL_HTTP_MAX_RETRY'] = '4'
import rasterio
from rasterio.windows import from_bounds

BUCKET = 'https://sentinel-cogs.s3.us-west-2.amazonaws.com'
AOI = (430000, 2408000, 472000, 2446000)        # UTM 4N: south Kaua'i, Kalaheo to Mahaulepu, sea to Wai'ale'ale
CORE = (444000, 2414000, 460000, 2428000)       # Po'ipu / Kukui'ula / Koloa


def score(s):
    try:
        with rasterio.open(f"{BUCKET}/{s['prefix']}SCL.tif") as ds:
            w = from_bounds(*AOI, ds.transform)
            a = ds.read(1, window=w, out_shape=(int(w.height // 4), int(w.width // 4)))
            tr = ds.window_transform(w) * rasterio.Affine.scale(4)
        H, W = a.shape
        def frac(box):
            c0 = int((box[0] - AOI[0]) / 80); c1 = int((box[2] - AOI[0]) / 80)
            r0 = int((AOI[3] - box[3]) / 80); r1 = int((AOI[3] - box[1]) / 80)
            b = a[r0:r1, c0:c1]
            valid = b > 0
            cloud = np.isin(b, [3, 8, 9, 10]) & valid
            return float(valid.mean()), float(cloud.sum() / max(1, valid.sum()))
        v, c = frac(AOI); cv, cc = frac(CORE)
        return dict(s, aoi_valid=v, aoi_cloud=c, core_valid=cv, core_cloud=cc)
    except Exception as e:
        return dict(s, error=str(e))


if __name__ == '__main__':
    cache = sys.argv[1]
    scenes = [s for s in json.load(open(f'{cache}/s2_scenes.json')) if (s.get('nodata') or 0) < 60]
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(score, scenes))
    res = [r for r in res if 'error' not in r]
    res.sort(key=lambda r: r['core_cloud'] + 0.3 * r['aoi_cloud'] + (1 - r['core_valid']))
    json.dump(res, open(f'{cache}/s2_scores.json', 'w'), indent=1)
    for r in res[:40]:
        print(r['id'], r['date'][:10], 'aoi valid %.2f cloud %.2f | core valid %.2f cloud %.3f' % (r['aoi_valid'], r['aoi_cloud'], r['core_valid'], r['core_cloud']))
    print(len(res), 'scored')
