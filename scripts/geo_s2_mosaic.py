#!/usr/bin/env python3
"""Cloud-free Sentinel-2 L2A mosaic of south Kaua'i (MGRS 04QDK), 10 m, surface reflectance.

Source: Copernicus Sentinel-2 L2A COGs on AWS (s3://sentinel-cogs, open data; "Contains modified
Copernicus Sentinel data 2023-2026"). Windows are read with HTTP range requests.
Per pixel: median of the clear observations (scene classification SCL 2, 4, 5, 6, 7) of the recent
scenes (Jul 2025 - Oct 2026, so the 2026 grading of Na Hiku shows), and where clouds never clear
(the Wai'ale'ale massif) the median of the clearest older scenes, then the least cloudy scene.
Writes <cache>/s2_aoi.npz: refl (H, W, 4) float16 reflectance B04 B03 B02 B08, nclear, box, res.
    python3 scripts/geo_s2_mosaic.py
"""
import os, sys, json
import numpy as np, concurrent.futures as cf
os.environ.setdefault('CURL_CA_BUNDLE', '/root/.ccr/ca-bundle.crt')
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
os.environ['GDAL_HTTP_MAX_RETRY'] = '5'
os.environ['GDAL_HTTP_RETRY_DELAY'] = '2'
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import AOI, cache_dir

BUCKET = 'https://sentinel-cogs.s3.us-west-2.amazonaws.com'
BANDS = ['B04', 'B03', 'B02', 'B08']
CLEAR = [2, 4, 5, 6, 7]


def read_scene(s, box=AOI, res=10):
    W, H = int((box[2] - box[0]) / res), int((box[3] - box[1]) / res)
    out = {}
    for b in BANDS + ['SCL']:
        for attempt in range(4):
            try:
                with rasterio.open(f"{BUCKET}/{s['prefix']}{b}.tif") as ds:
                    w = from_bounds(*box, ds.transform)
                    out[b] = ds.read(1, window=w, out_shape=(H, W), boundless=True, fill_value=0,
                                     resampling=Resampling.nearest)
                break
            except Exception as e:
                if attempt == 3: raise
    # Element 84 has already removed the +1000 DN offset of processing baseline >= 04.00
    # (earthsearch:boa_offset_applied), whatever raster:bands says: reflectance = DN / 10000
    refl = np.stack([out[b].astype(np.float32) for b in BANDS], -1) / 10000.0
    clear = np.isin(out['SCL'], CLEAR) & (out['B02'] > 0)
    # thin cloud / haze the classifier missed: very bright blue over land
    clear &= ~((refl[..., 2] > 0.18) & (refl[..., 3] > 0.25))
    return refl.astype(np.float16), clear


def median_stack(scenes, box, label):
    acc_r, acc_c = [], []
    with cf.ThreadPoolExecutor(4) as ex:
        for s, (r, c) in zip(scenes, ex.map(lambda s: read_scene(s, box), scenes)):
            acc_r.append(r); acc_c.append(c)
    print(f'  {label}: clear fraction per scene', ' '.join(f'{c.mean():.2f}' for c in acc_c), flush=True)
    Cl = np.stack(acc_c); n = Cl.sum(0)
    med = np.empty(acc_r[0].shape, np.float32)
    for i in range(0, med.shape[0], 128):                     # nanmedian in strips (memory)
        R = np.stack([r[i:i + 128] for r in acc_r]).astype(np.float32)
        R[~Cl[:, i:i + 128]] = np.nan
        med[i:i + 128] = np.nanmedian(R, axis=0)
    return med, n, acc_r[0]


if __name__ == '__main__':
    C = cache_dir()
    scores = json.load(open(f'{C}/s2_scores.json'))
    recent = sorted([s for s in scores if '2025-07' <= s['date'][:7] and s['aoi_cloud'] < 0.32 and s['aoi_valid'] > 0.99], key=lambda s: s['aoi_cloud'])[:14]
    older = sorted([s for s in scores if s['date'][:7] < '2025-07' and s['aoi_cloud'] < 0.16 and s['aoi_valid'] > 0.99], key=lambda s: s['aoi_cloud'])[:8]
    print('recent', [s['id'][9:17] for s in recent]); print('older', [s['id'][9:17] for s in older], flush=True)
    import warnings; warnings.filterwarnings('ignore', category=RuntimeWarning)
    if '--before' in sys.argv:
        # the strip before the 2025-26 grading (older scenes only), for the ground under the modelled lots
        from geo_common import LOT_UTM
        box = (LOT_UTM[0] - 1000, LOT_UTM[1] - 1000, LOT_UTM[0] + 1000, LOT_UTM[1] + 1000)
        m2, n2, least = median_stack(older, box, 'older')
        np.savez_compressed(f'{C}/s2_before.npz', refl=m2.astype(np.float16), box=np.array(box), res=10.0)
        print('before mosaic', m2.shape); sys.exit()
    E0, N0, E1, N1 = AOI; res = 10.0
    W, H = int((E1 - E0) / res), int((N1 - N0) / res)
    out = np.zeros((H, W, 4), np.float16); n_rec = np.zeros((H, W), np.uint8); n_old = np.zeros((H, W), np.uint8)
    CH = 1000
    for r0 in range(0, H, CH):
        r1 = min(H, r0 + CH)
        box = (E0, N1 - r1 * res, E1, N1 - r0 * res)
        print(f'rows {r0}-{r1}', flush=True)
        m1, n1, _ = median_stack(recent, box, 'recent')
        m2, n2, least = median_stack(older, box, 'older')
        o = np.where((n1 >= 2)[..., None], m1, np.where((n2 >= 1)[..., None], m2, m1))
        hole = np.isnan(o[..., 0])
        o[hole] = least.astype(np.float32)[hole]
        out[r0:r1] = o.astype(np.float16); n_rec[r0:r1] = n1; n_old[r0:r1] = n2
    np.savez_compressed(f'{C}/s2_aoi.npz', refl=out, n_recent=n_rec, n_older=n_old,
                        box=np.array(AOI), res=res, scenes=np.array([s['id'] for s in recent + older]))
    print('done', out.shape, 'pixels from recent %.2f older %.2f' % ((n_rec >= 2).mean(), ((n_rec < 2) & (n_old >= 1)).mean()))
