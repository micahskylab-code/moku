#!/usr/bin/env python3
"""Elevation for the real site, from public USGS data (public domain):
  * USGS 3DEP 1 m DEM, project HI_FEMAR9Kauai_2019_D19 (FEMA Region 9 Kaua'i lidar, 2019-21), bare earth
  * USGS 3DEP 1/3 arc-second seamless DEM (n22w160, n23w160) where the lidar has no data
Both read as windows straight from s3://prd-tnm (HTTP range requests, no full downloads).
Heights are metres above local mean sea level; ocean = NaN.
Writes to the cache:
  dem_aoi_10m.npy  (+ .json grid)   whole AOI, 10 m, UTM 4N
  dem_near_2m.npy  (+ .json grid)   6 x 6 km around the site, 2 m
    python3 scripts/geo_dem.py
"""
import os, sys, json, math
import numpy as np
os.environ.setdefault('CURL_CA_BUNDLE', '/root/.ccr/ca-bundle.crt')
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
os.environ['GDAL_HTTP_MAX_RETRY'] = '5'
os.environ['GDAL_HTTP_RETRY_DELAY'] = '2'
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_origin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import AOI, LOT_UTM, cache_dir

LIDAR = 'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/HI_FEMAR9Kauai_2019_D19/TIFF/USGS_1M_4_{}_HI_FEMAR9Kauai_2019_D19.tif'
LIDAR_TILES = 'x41y244 x41y245 x42y243 x42y244 x42y245 x42y246 x43y243 x43y244 x43y245 x43y246 x44y242 x44y243 x44y244 x44y245 x44y246 x45y242 x45y243 x45y244 x45y245 x45y246 x46y243 x46y244 x46y245 x46y246'.split()
NED = 'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{0}/USGS_13_{0}.tif'
DST_CRS = 'EPSG:32604'


def grid(box, res):
    E0, N0, E1, N1 = box
    W, H = int(round((E1 - E0) / res)), int(round((N1 - N0) / res))
    return W, H, from_origin(E0, N1, res, res)


def from_ned(box, res):
    W, H, tr = grid(box, res)
    out = np.full((H, W), np.nan, np.float32)
    for t in ('n22w160', 'n23w160'):
        with rasterio.open(NED.format(t)) as ds:
            b = transform_bounds(DST_CRS, ds.crs, *box, densify_pts=21)
            b = (max(b[0], ds.bounds.left), max(b[1], ds.bounds.bottom), min(b[2], ds.bounds.right), min(b[3], ds.bounds.top))
            if b[0] >= b[2] or b[1] >= b[3]: continue
            w = from_bounds(*b, ds.transform).round_offsets().round_lengths()
            dec = max(1, int(res / 10 / 1.5))
            a = ds.read(1, window=w, out_shape=(max(1, int(w.height // dec)), max(1, int(w.width // dec))), resampling=Resampling.average)
            a[a < -1000] = np.nan
            wt = ds.window_transform(w) * rasterio.Affine.scale(w.width / a.shape[1], w.height / a.shape[0])
            tmp = np.full((H, W), np.nan, np.float32)
            reproject(a, tmp, src_transform=wt, src_crs=ds.crs, src_nodata=np.nan, dst_transform=tr, dst_crs=DST_CRS, dst_nodata=np.nan, resampling=Resampling.bilinear)
            out = np.where(np.isnan(out), tmp, out)
    return out


def from_lidar(box, res):
    W, H, tr = grid(box, res)
    out = np.full((H, W), np.nan, np.float32)
    for t in LIDAR_TILES:
        x0, y1 = int(t[1:3]) * 10000, int(t[4:7]) * 10000
        tb = (x0, y1 - 10000, x0 + 10000, y1)
        b = (max(box[0], tb[0]), max(box[1], tb[1]), min(box[2], tb[2]), min(box[3], tb[3]))
        if b[0] >= b[2] or b[1] >= b[3]: continue
        with rasterio.open(LIDAR.format(t)) as ds:
            w = from_bounds(*b, ds.transform).round_offsets().round_lengths()
            dec = max(1, int(res))
            a = ds.read(1, window=w, out_shape=(max(1, int(w.height // dec)), max(1, int(w.width // dec))), resampling=Resampling.average)
            a[a < -1000] = np.nan
            wt = ds.window_transform(w) * rasterio.Affine.scale(w.width / a.shape[1], w.height / a.shape[0])
            tmp = np.full((H, W), np.nan, np.float32)
            reproject(a, tmp, src_transform=wt, src_crs=ds.crs, src_nodata=np.nan, dst_transform=tr, dst_crs=DST_CRS, dst_nodata=np.nan, resampling=Resampling.bilinear)
            out = np.where(np.isnan(out), tmp, out)
        print('  lidar', t, flush=True)
    return out


def merge(lid, ned):
    """Lidar first; where the lidar has holes (water, voids) fall back to the 1/3" DEM, blended in
    over a few pixels so there is no step; open ocean stays NaN."""
    from scipy import ndimage as ndi
    have = ~np.isnan(lid)
    out = np.where(have, lid, ned)
    # feather: near hole edges, bias the NED fill towards the lidar level (removes datum/epoch steps)
    if have.any() and (~have).any():
        d = np.where(have, lid - np.where(np.isnan(ned), lid, ned), np.nan)
        dd = np.where(np.isnan(d), 0, d); ww = (~np.isnan(d)).astype(np.float32)
        k = 5
        num = ndi.uniform_filter(dd, 2 * k + 1); den = ndi.uniform_filter(ww, 2 * k + 1)
        corr = np.where(den > 0.05, num / np.maximum(den, 1e-6), 0)
        out = np.where(have, lid, ned + corr)
    return out.astype(np.float32)


def save(name, arr, box, res):
    c = cache_dir()
    np.save(f'{c}/{name}.npy', arr)
    json.dump({'box': box, 'res': res, 'crs': DST_CRS}, open(f'{c}/{name}.json', 'w'))
    print(name, arr.shape, 'min %.1f max %.1f nan %.2f' % (np.nanmin(arr), np.nanmax(arr), np.isnan(arr).mean()), flush=True)


if __name__ == '__main__':
    near = (LOT_UTM[0] - 3000, LOT_UTM[1] - 3000, LOT_UTM[0] + 3000, LOT_UTM[1] + 3000)
    near = tuple(float(round(v)) for v in near)
    print('near: lidar 2 m', flush=True)
    lid = from_lidar(near, 2.0); ned = from_ned(near, 2.0)
    save('dem_near_2m', merge(lid, ned), near, 2.0)
    print('aoi: lidar + ned 10 m', flush=True)
    lid = from_lidar(AOI, 10.0); ned = from_ned(AOI, 10.0)
    save('dem_aoi_10m', merge(lid, ned), AOI, 10.0)
