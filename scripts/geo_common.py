"""Shared constants and transforms for the real-site pipeline (scripts/geo_*.py).

World frame of the walkthrough: feet, y up; plan x -> world x (street side +x), plan y -> world z.
Registration (scripts/geo_register.py): our lot (Na Hiku lot 7 of 14 from the north-west end) is
anchored at its real place, read off Sentinel-2 imagery of the 2025-26 grading of the Na Hiku strip,
and world +x points along the real lot axis (fairway -> street), bearing ~46 deg.
UTM = WGS84 / UTM zone 4N (EPSG:32604). The USGS lidar DEM is NAD83 / UTM 4N (EPSG:26904); the
~1 m datum difference is ignored (below the registration error).
"""
import json, math, os, re
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
FT = 0.3048

# ---- registration (see geo_register.py for how these were measured) ----
# The Na Hiku strip graded in 2025-26 is bare soil in the Jun-Sep 2026 Sentinel-2 scenes: centre
# 450108 E 2420810 N, long axis at grid bearing 136.3 (135-138 in three scenes), ~340 m long. The row of
# fourteen lots (70 ft = 21.3 m apart, 298 m) is placed from 10 m inside the strip's north-west end, its
# lots-plus-road block centred across the strip; the lots stand back from the golf pond on the south-west.
LOT_UTM = (450089.0, 2420822.0)       # centre of our lot (7th from the north-west), metres E, N (WGS84 UTM 4N)
X_BEARING = 46.3                      # grid bearing of world +x (lot axis, fairway -> street), deg from grid north
CONVERGENCE = -0.180                  # pyproj meridian convergence at the lot (deg)
LOT_GROUND_M = 17.6                   # ground over our lot (m above local mean sea level), 2019 USGS lidar mean
REG_ERR_M = 25.0                      # 1-sigma position error of the anchor (m)

# Area of interest for the far field (UTM metres): Hanapepe to Lihu'e, 20 km of ocean to the Wai'ale'ale
# massif. It holds the far terrain square (34 km, turned 46 deg with the lot) with a margin.
AOI = (424000.0, 2397000.0, 476000.0, 2447000.0)
FAR_HALF_FT = 55000.0                 # far terrain square: +-16.8 km around the lot, world axes
NEAR_HALF_FT = 6000.0                 # near terrain square: +-1.83 km


def plan_lot_centre():
    plan = json.load(open(os.path.join(ROOT, 'plans', 'lot25.json')))
    lot = plan['site']['lot']
    return ((lot[0] + lot[2]) / 2, (lot[1] + lot[3]) / 2), plan


def world_axes():
    b = math.radians(X_BEARING)
    ex = np.array([math.sin(b), math.cos(b)])           # world +x as (dE, dN)
    ez = np.array([math.sin(b + math.pi / 2), math.cos(b + math.pi / 2)])   # world +z = +x turned clockwise
    return ex, ez


def world_to_utm(x, z):
    """world feet (x, z) -> UTM metres (E, N)."""
    (px, pz), _ = plan_lot_centre()
    ex, ez = world_axes()
    x = np.asarray(x, float) - px; z = np.asarray(z, float) - pz
    E = LOT_UTM[0] + FT * (x * ex[0] + z * ez[0])
    N = LOT_UTM[1] + FT * (x * ex[1] + z * ez[1])
    return E, N


def utm_to_world(E, N):
    (px, pz), _ = plan_lot_centre()
    ex, ez = world_axes()
    dE = (np.asarray(E, float) - LOT_UTM[0]) / FT; dN = (np.asarray(N, float) - LOT_UTM[1]) / FT
    return px + dE * ex[0] + dN * ex[1], pz + dE * ez[0] + dN * ez[1]


def true_north_world():
    """True north as a unit vector on the plan (x, z) — what siteLayout().north should be."""
    tb = math.radians(X_BEARING + CONVERGENCE)        # true bearing of +x
    return [math.cos(-tb), math.sin(-tb)]


# ---- site-plan geometry parsed from src/neighborhood.js (screen px of the site-plan view) ----
def siteplan():
    src = open(os.path.join(ROOT, 'src', 'neighborhood.js')).read()
    def arr(name):
        m = re.search(r'const ' + name + r' = (\[.*?\n\]);', src, re.S)
        s = re.sub(r'//[^\n]*', '', m.group(1))
        s = re.sub(r'(\w+):', r'"\1":', s)
        return json.loads(re.sub(r',\s*([\]}])', r'\1', s))
    out = {'ROADS': arr('ROADS'), 'HOLES': arr('HOLES'), 'PONDS': arr('PONDS'), 'HOMES': arr('HOMES')}
    out['FIELD'] = json.loads(re.search(r'const FIELD = (\[.*?\]);', src).group(1))
    out['LOTS'] = [[974 + (1419 - 974) * i / 13, 534 + (719 - 534) * i / 13] for i in range(14)]
    return out


def siteplan_to_world(K=1.66, our=6, back=(-0.42, 0.91)):
    """Replica of siteLayout() in src/neighborhood.js (before the real-site work): returns toPlan(p)."""
    sp = siteplan()
    (px, pz), plan = plan_lot_centre()
    S = plan['site']; lot = S['lot']
    ref = sp['LOTS'][our]
    th = -math.atan2(-back[1], -back[0]); c, s = math.cos(th), math.sin(th)
    def raw(p):
        dx, dy = (p[0] - ref[0]) * K, (p[1] - ref[1]) * K
        return [px + dx * c - dy * s, pz + dx * s + dy * c]
    road = [raw(p) for p in sp['ROADS'][0]]
    rx = None
    for a, b in zip(road, road[1:]):
        if (a[1] - pz) * (b[1] - pz) <= 0:
            rx = a[0] + (b[0] - a[0]) * (pz - a[1]) / ((b[1] - a[1]) or 1); break
    shift = S.get('roadX', lot[2] + 13) - (rx if rx is not None else lot[2] + 13)
    return lambda p: [raw(p)[0] + shift, raw(p)[1]]


LOT_PITCH_FT = 70.0                   # src/neighborhood.js LOT_PITCH
OUR_LOT = 6


def keep_rect():
    """World rect left to the modelled neighbourhood (= siteLayout(plan).keep in src/neighborhood.js)."""
    (px, pz), plan = plan_lot_centre()
    lot = plan['site']['lot']; roadX = plan['site'].get('roadX', lot[2] + 13); w = lot[3] - lot[1]
    z0 = pz - OUR_LOT * LOT_PITCH_FT - w / 2; z1 = pz + (13 - OUR_LOT) * LOT_PITCH_FT + w / 2
    return [lot[0] - 45, z0 - 45, roadX + 45, z1 + 45]


def cache_dir():
    d = os.environ.get('GEO_CACHE') or os.path.join(ROOT, '..', 'geo-test', 'cache')
    os.makedirs(d, exist_ok=True)
    return d
