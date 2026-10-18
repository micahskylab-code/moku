#!/usr/bin/env python3
"""USGS 3DEP 1 m lidar DEM over the Kukui'ula community box -> <cache>/dem_comm_1m.npy (+ .json).

Range-reads the four 10 km project tiles (HI_FEMAR9Kauai_2019_D19, lidar 2019-21, public domain) over
AWS S3, north-up UTM 4N, metres above local mean sea level, NaN where there is no ground (sea).
    python3 scripts/geo_dem1m.py
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_common import cache_dir

COMM_BOX = (447500, 2418000, 453500, 2423000)      # E0, N0, E1, N1 (m): Lawa'i Kai to Po'ipu, the coast to the Koloa bypass
URL = ('https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/HI_FEMAR9Kauai_2019_D19/TIFF/'
       'USGS_1M_4_x{x}y{y}_HI_FEMAR9Kauai_2019_D19.tif')


def main():
    import rasterio
    from rasterio.windows import from_bounds
    os.environ.setdefault('CURL_CA_BUNDLE', '/root/.ccr/ca-bundle.crt')
    os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
    E0, N0, E1, N1 = COMM_BOX
    out = np.full((N1 - N0, E1 - E0), np.nan, np.float32)
    for x in range(E0 // 10000, (E1 - 1) // 10000 + 1):
        for y in range(N0 // 10000 + 1, (N1 - 1) // 10000 + 2):        # tiles are named by their north edge
            te0, tn1 = x * 10000, y * 10000
            a0, a1, b0, b1 = max(E0, te0), min(E1, te0 + 10000), max(N0, tn1 - 10000), min(N1, tn1)
            if a0 >= a1 or b0 >= b1: continue
            with rasterio.open(URL.format(x=x, y=y)) as ds:
                a = ds.read(1, window=from_bounds(a0, b0, a1, b1, ds.transform)).astype(np.float32)
            a[a < -1000] = np.nan
            out[N1 - b1:N1 - b0, a0 - E0:a1 - E0] = a
            print(f'x{x}y{y}: {a.shape}, {np.isnan(a).mean():.0%} no data', flush=True)
    c = cache_dir()
    np.save(f'{c}/dem_comm_1m.npy', out)
    json.dump({'box': list(COMM_BOX), 'res': 1.0, 'crs': 'EPSG:26904'}, open(f'{c}/dem_comm_1m.json', 'w'))
    print('dem_comm_1m', out.shape, float(np.nanmin(out)), float(np.nanmax(out)))


if __name__ == '__main__':
    main()
