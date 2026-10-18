#!/usr/bin/env python3
"""Seafloor and shore of the Kukui'ula coast -> <cache>/bathy_comm_1m.npy (+ .json).

USACE NCMP 2013 Kaua'i topobathy lidar, bare earth 1 m grid (NOAA Digital Coast dataset 9335, via the
NOAA coastal lidar bucket on AWS Open Data; public domain), metres relative to local mean sea level,
north-up on the community box (scripts/geo_dem1m.py), NaN where the survey has no return.
    python3 scripts/geo_bathy.py
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import cache_dir
from geo_dem1m import COMM_BOX

URL = 'https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/USACE_Kauai_HI_LMSL_DEM_2013_9335/2013_NCMP_HI_Kauai_4QDK{e:02d}{n:02d}_BareEarth_1mGrid.tif'


def main():
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    os.environ.setdefault('CURL_CA_BUNDLE', '/root/.ccr/ca-bundle.crt')
    os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
    E0, N0, E1, N1 = COMM_BOX
    out = np.full((N1 - N0, E1 - E0), np.nan, np.float32)
    dst_tr = from_origin(E0, N1, 1.0, 1.0)
    # USNG 1 km cells of 100 km square DK (zone 4Q): easting and northing kilometres within the square
    for e in range(E0 // 1000 - 400, (E1 - 1) // 1000 - 400 + 1):
        for n in range(N0 // 1000 - 2400, (N1 - 1) // 1000 - 2400 + 1):
            try:
                with rasterio.open(URL.format(e=e, n=n)) as ds:
                    a = ds.read(1).astype(np.float32)
                    nd = ds.nodata
                    if nd is not None: a[a == nd] = np.nan
                    a[a < -500] = np.nan
                    tmp = np.full_like(out, np.nan)
                    reproject(a, tmp, src_transform=ds.transform, src_crs=ds.crs, dst_transform=dst_tr, dst_crs='EPSG:26904',
                              src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
                    out = np.where(np.isnan(out), tmp, out)
                    print(f'4QDK{e:02d}{n:02d}: {ds.crs.to_string()[:40]} {np.nanmin(a):.1f}..{np.nanmax(a):.1f} m', flush=True)
            except rasterio.errors.RasterioIOError:
                pass
    c = cache_dir()
    np.save(f'{c}/bathy_comm_1m.npy', out)
    json.dump({'box': list(COMM_BOX), 'res': 1.0, 'crs': 'EPSG:26904', 'src': 'USACE NCMP 2013 Kauai topobathy, NOAA 9335'},
              open(f'{c}/bathy_comm_1m.json', 'w'))
    v = ~np.isnan(out)
    print('bathy', f'{v.mean():.0%} covered', float(np.nanmin(out)), float(np.nanmax(out)))


if __name__ == '__main__':
    main()
