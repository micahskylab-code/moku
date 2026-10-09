"""Kauai and Hawaii County owner-occupancy proxy (key occupancy_kh).

Usage: python3 -I build.py SCRATCHPAD
Reads only files already on disk:
  raw/owners_neighbor/kauai/ty26/*.json          Kauai TY26 property-tax layer pages (fetched 2026-10-08)
  raw/owners_neighbor/hawaii/cohrpt2026/*.json   Hawaii County cohRPT2026 roll pages (fetched 2026-10-08)
  raw/up_occupancy_kh/...                        centroids, district polygons, Census places, official
                                                 State RPT summary text, Kauai 2020 building points
  an/new/owners_neighbor.json, an/new/owners_oahu.json   (comparison figures)
Writes an/up/occupancy_kh.json. Aggregates only: no owner names, addresses, TMKs or parcel IDs are written.
"""
import json, glob, os, sys, hashlib, datetime, collections as C, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import geo

S = sys.argv[1]
R0 = os.path.join(S, 'raw/owners_neighbor')
R = os.path.join(S, 'raw/up_occupancy_kh')
OUT = os.path.join(S, 'an/up/occupancy_kh_v2.json')
SMALL = 20

def pages(pat):
    feats = []
    for fn in sorted(glob.glob(os.path.join(pat))):
        d = json.load(open(fn))
        assert 'error' not in d, fn
        feats += d['features']
    return feats

def sha_concat(pat):
    h = hashlib.sha256()
    fs = sorted(glob.glob(pat))
    for fn in fs:
        h.update(open(fn, 'rb').read())
    return h.hexdigest(), len(fs)

def pct(a, b):
    return None if not b else round(a / b, 4)

def P(v):
    return '%d%%' % round(100 * v)

TIERS = [('entry_<750K', 0, 750_000), ('mid_750K-1.5M', 750_000, 1_500_000), ('upper_1.5M-3M', 1_500_000, 3_000_000),
         ('luxury_3M-10M', 3_000_000, 10_000_000), ('ultra_10M+', 10_000_000, float('inf'))]
def tier(v):
    for name, lo, hi in TIERS:
        if lo <= v < hi:
            return name
    return None

def cell(rows, vr_applicable=True):
    """rows: list of dicts with 'cat' in {'OO','VR','NOO'}."""
    c = C.Counter(r['cat'] for r in rows)
    n = c['OO'] + c['VR'] + c['NOO']
    out = {'units': n, 'owner_occupied': c['OO']}
    if vr_applicable:
        out['vacation_rental_class'] = c['VR']
    out['other_non_owner_occupied'] = c['NOO']
    out['share_owner_occupied'] = pct(c['OO'], n)
    if vr_applicable:
        out['share_vacation_rental_class'] = pct(c['VR'], n)
    out['share_other_non_owner_occupied'] = pct(c['NOO'], n)
    out['share_non_owner_occupied_total'] = pct(c['VR'] + c['NOO'], n)
    if n < SMALL:
        out['flag_fewer_than_20_units'] = True
    return out

def tier_table(rows, vr_applicable=True, valkey='value'):
    t = {}
    for name, lo, hi in TIERS:
        t[name] = cell([r for r in rows if lo <= r[valkey] < hi], vr_applicable)
    t['3M_plus_(luxury+ultra)'] = cell([r for r in rows if r[valkey] >= 3_000_000], vr_applicable)
    return t

# ------------------------------------------------------------------ Census place names
cdp = geo.load_polygons(os.path.join(R, 'census/tiger2020_cdp_hi.json'))
ccd = geo.load_polygons(os.path.join(R, 'census/tiger2020_cousub_hi_001_007.json'))
def cdp_name(a):
    n = a['NAME'].replace(' CDP', '')
    return 'Kailua (Kona)' if a['GEOID'] == '1523000' else n
def ccd_name(a): return a['NAME']

def label_groups(groups, xy_of):
    """groups: dict key -> list of point indices; xy_of: (M,2) array. Returns key -> label info."""
    allidx = sorted({i for v in groups.values() for i in v})
    sub = xy_of[allidx]
    a_cdp = geo.assign(cdp, sub, lambda a: a['GEOID'] + '|' + cdp_name(a))
    a_ccd = geo.assign(ccd, sub, lambda a: ccd_name(a))
    pos = {i: k for k, i in enumerate(allidx)}
    out = {}
    for key, idxs in groups.items():
        cc = C.Counter(a_cdp[pos[i]] for i in idxs)
        cs = C.Counter(a_ccd[pos[i]] for i in idxs)
        n = len(idxs)
        top, topn = cc.most_common(1)[0]
        named = [(k.split('|')[1], v) for k, v in cc.most_common() if k]
        ccd_top = cs.most_common(1)[0][0]
        if top and topn / n >= 0.5:
            lab = top.split('|')[1]
            if len(named) > 1 and named[1][1] / n >= 0.25:
                lab += ' / ' + named[1][0]
        elif named and named[0][1] / n >= 0.25:
            lab = named[0][0] + ' area (partly outside the CDP)'
        else:
            lab = (ccd_top or 'unlabelled') + (' (mostly outside Census-designated places)' if cc.get(None, 0) / n >= 0.5 else ' (spread across several places)')
        out[key] = {'label': lab,
                    'census2020_cdp_top': [{'cdp': k, 'share_of_units': round(v / n, 3)} for k, v in named[:3]],
                    'share_outside_any_cdp': round(cc.get(None, 0) / n, 3),
                    'census2020_ccd_top': ccd_top}
    return out

# ================================================================== KAUAI
kf = pages(os.path.join(R0, 'kauai/ty26/ty26_*.json'))
K = [f['attributes'] for f in kf]
kc = {f['attributes']['OBJECTID']: f for f in pages(os.path.join(R, 'k_centroids/k_centroids_*.json'))}
assert len(K) == 37655 and all(kc[r['OBJECTID']]['attributes']['PARID'] == r['PARID'] for r in K)
KXY = np.array([(kc[r['OBJECTID']]['centroid']['x'], kc[r['OBJECTID']]['centroid']['y']) for r in K])
# v2: drop exact duplicate records (same attributes apart from OBJECTID); the layer repeats 3 parcels
_seen = set(); _keep = []
for _i, _r in enumerate(K):
    _k = tuple(sorted((a, v) for a, v in _r.items() if a != 'OBJECTID'))
    if _k in _seen: continue
    _seen.add(_k); _keep.append(_i)
K_DUPES_DROPPED = len(K) - len(_keep)
K = [K[_i] for _i in _keep]; KXY = KXY[_keep]


K_RES = {'8:OWNER-OCCUPIED': 'OO', '10:OWNER-OCCUPIED MIXED-USE': 'OO', '2:VACATION RENTAL': 'VR',
         '1:NON-OWNER-OCCUPIED RESIDENTIAL': 'NOO', '11:LONG TERM AFFORDABLE RENTAL': 'NOO'}
def ktype(t):
    if t.startswith('CPRX Multi-Unit Complex'): return 'condo_unit (CPRX multi-unit complex)'
    if t.startswith('CPR Unit'): return 'land_cpr_unit (CPR unit)'
    if t.startswith('TMK Parcel'): return 'whole_lot (TMK parcel)'
    return 'other_cpr (lease/commercial/utility/HHL)'
def kowner(t):
    return 'state' if 'STATE' in t else 'county' if 'COUNTY' in t else 'federal' if 'FEDERAL' in t else 'private'
base = lambda r: (r['ZONE'], r['SECTION'], r['PLAT'], r['PARCEL'])
unit_bases = {base(r) for r in K if r['TYPE'].startswith('CPR')}
k_master = [i for i, r in enumerate(K) if r['TYPE'].startswith('TMK Parcel') and base(r) in unit_bases]

# 2020 assessor building points (County of Kauai Hazard Mitigation Plan layer)
hmp = [f['attributes'] for f in pages(os.path.join(R, 'k_hmp_bldg/k_hmp_bldg_0*.json'))]
hmp_parid = {int(a['Haz_PARID']) for a in hmp if a['Haz_PARID']}
hmp_parid_res = {int(a['Haz_PARID']) for a in hmp if a['Haz_PARID'] and a['GenHazOccupClass'] == 'RES'}

KZ = {1: 'Waimea', 2: 'Kōloa', 3: 'Līhuʻe', 4: 'Kawaihau', 5: 'Hanalei'}
krows, k_excluded = [], C.Counter()
mset = set(k_master)
for i, r in enumerate(K):
    cls = r['TAXCLASS']
    if cls not in K_RES:
        k_excluded['non_residential_class:' + str(cls)] += 1
        continue
    if i in mset:
        k_excluded['condo_master_record_(units_listed_separately)'] += 1
        continue
    cat = K_RES[cls]
    fully_exempt = (r['TAXABLE'] or 0) == 0
    if cat == 'NOO' and fully_exempt:
        cat = 'EXEMPT'
    krows.append({'i': i, 'cat': cat, 'cls': cls, 'zone': r['ZONE'], 'zs': '%d-%d' % (r['ZONE'], r['SECTION']),
                  'type': ktype(r['TYPE']), 'owner': kowner(r['TYPE']),
                  'value': (r['MODTOT'] if r['MODTOT'] is not None else (r['ASSDTOT'] or 0)), 'assd': r['ASSDTOT'] or 0,
                  'bldg2020': int(r['PARID']) in hmp_parid if r['PARID'] else False})
kmain = [x for x in krows if x['cat'] != 'EXEMPT']
kex = [x for x in krows if x['cat'] == 'EXEMPT']

kres = {}
kres['universe'] = {
    'records_in_layer': len(K) + K_DUPES_DROPPED, 'exact_duplicate_records_dropped': K_DUPES_DROPPED,
    'residential_class_records_considered': len(krows),
    'main_universe_units': len(kmain),
    'fully_exempt_non_owner_occupied_class_records_shown_separately': len(kex),
    'excluded': dict(k_excluded),
    'definition': 'Residential housing = tax classes 8 Owner-Occupied, 10 Owner-Occupied Mixed-Use, 2 Vacation Rental, 1 Non-Owner-Occupied Residential, 11 Long-Term Affordable Rental. Owner-occupied = classes 8+10; vacation-rental = class 2; other non-owner-occupied = classes 1+11 with taxable value > 0. Class-1 records with zero taxable value (mostly State-owned land incl. DHHL homestead leases, County-owned, nonprofit) are shown separately and excluded from shares. Condo master records whose units are listed separately are excluded. Hotel & Resort (class 7) and Agricultural (class 5) records are excluded (sensitivity below).',
}
kres['island'] = cell(kmain)
kres['island']['by_class_records'] = dict(C.Counter(x['cls'] for x in kmain))
kres['island_non_condo_(lots_and_land_CPRs;_closest_to_Hawaii_County_house-lot_basis)'] = cell([x for x in kmain if not x['type'].startswith('condo')])
kres['island_condo_units_only'] = cell([x for x in kmain if x['type'].startswith('condo')])
_oo = [K[x['i']] for x in kmain if x['cls'] == '8:OWNER-OCCUPIED']
_nv = [K[x['i']] for x in kmain if x['cls'] in ('1:NON-OWNER-OCCUPIED RESIDENTIAL', '2:VACATION RENTAL')]
_rat = [r['MODTOT'] / r['ASSDTOT'] for r in _oo if r['ASSDTOT'] and r['MODTOT'] and r['MODTOT'] > r['ASSDTOT']]
MODSTAT = {'class8_share_MODTOT_gt_ASSDTOT': pct(sum(1 for r in _oo if (r['MODTOT'] or 0) > (r['ASSDTOT'] or 0)), len(_oo)),
           'class8_median_ratio_when_greater': round(float(np.median(_rat)), 2),
           'class1_2_share_equal': pct(sum(1 for r in _nv if r['MODTOT'] == r['ASSDTOT']), len(_nv))}
kres['MODTOT_vs_ASSDTOT'] = MODSTAT
kres['by_district'] = {}
for z in range(1, 6):
    rows = [x for x in kmain if x['zone'] == z]
    d = cell(rows)
    d['district'] = KZ[z]
    d['fully_exempt_records_separate'] = sum(1 for x in kex if x['zone'] == z)
    d['condo_units_(CPRX)'] = cell([x for x in rows if x['type'].startswith('condo')])
    d['non_condo_(lots_and_land_CPRs)'] = cell([x for x in rows if not x['type'].startswith('condo')])
    kres['by_district']['zone_%d_%s' % (z, KZ[z])] = d
kres['by_unit_type'] = {t: cell([x for x in kmain if x['type'] == t]) for t in sorted({x['type'] for x in kmain})}
kres['by_tier_market_value_MODTOT'] = tier_table(kmain)
kres['by_tier_assessed_value_ASSDTOT'] = tier_table(kmain, valkey='assd')
kres['by_district_by_tier_market_value_MODTOT'] = {
    'zone_%d_%s' % (z, KZ[z]): tier_table([x for x in kmain if x['zone'] == z]) for z in range(1, 6)}
# value shares
def vshare(rows, key='value'):
    tot = sum(x[key] for x in rows)
    v = C.Counter()
    for x in rows: v[x['cat']] += x[key]
    return {'total_value_usd': tot, 'share_owner_occupied': pct(v['OO'], tot), 'share_vacation_rental_class': pct(v['VR'], tot),
            'share_other_non_owner_occupied': pct(v['NOO'], tot)}
kres['value_shares_market_value_MODTOT'] = vshare(kmain)
# neighborhoods: zone-section
zs_groups = C.defaultdict(list)
for x in kmain: zs_groups[x['zs']].append(x)
elig = {k: v for k, v in zs_groups.items() if len(v) >= 100}
labels = label_groups({k: [x['i'] for x in v] for k, v in elig.items()}, KXY)
nb = []
for k, v in elig.items():
    d = cell(v); d['zone_section'] = k; d['district'] = KZ[int(k.split('-')[0])]
    d['place'] = labels[k]
    d['condo_unit_share'] = pct(sum(1 for x in v if x['type'].startswith('condo')), len(v))
    d['owner_type_mix'] = dict(C.Counter(x['owner'] for x in v))
    if d['owner_type_mix'].get('state', 0) >= len(v) / 2:
        d['note'] = 'Mostly State-owned land held under lease (TYPE "- STATE"); leasehold, not a fee-simple market.'
    d['median_market_value_usd'] = int(np.median([x['value'] for x in v]))
    nb.append(d)
nb.sort(key=lambda d: (-d['share_non_owner_occupied_total'], -d['units']))
kres['neighborhoods_eligible_(zone-sections_with_100plus_units)'] = len(nb)
kres['top15_zone_sections_by_non_owner_occupied_share'] = nb[:15]
kres['bottom5_zone_sections_by_non_owner_occupied_share'] = nb[-5:]
kres['all_eligible_zone_sections_sorted'] = [{'zone_section': d['zone_section'], 'label': d['place']['label'], 'units': d['units'],
                                              'share_owner_occupied': d['share_owner_occupied'],
                                              'share_vacation_rental_class': d['share_vacation_rental_class'],
                                              'share_non_owner_occupied_total': d['share_non_owner_occupied_total']} for d in nb]
# sensitivities
hr = [K[i] for i in range(len(K)) if K[i]['TAXCLASS'] == '7:HOTEL AND RESORT' and K[i]['TYPE'].startswith('CPRX Multi-Unit Complex')]
c = C.Counter(x['cat'] for x in kmain)
kres['sensitivity_include_hotel_resort_condo_units_as_non_owner_occupied'] = {
    'hotel_resort_class_condo_units': len(hr),
    'by_district': dict(C.Counter(KZ[r['ZONE']] for r in hr)),
    'share_owner_occupied_if_included': pct(c['OO'], len(kmain) + len(hr)),
    'note': 'Class 7 Hotel & Resort condo units (resort condos, condo-hotels, timeshare) are housing-like but taxed as hotel; including them lowers the owner-occupied share.'}
kres['sensitivity_fully_exempt_counted_as_non_owner_occupied'] = {
    'fully_exempt_records': len(kex), 'by_owner_type': dict(C.Counter(x['owner'] for x in kex)),
    'by_district': dict(C.Counter(KZ[x['zone']] for x in kex)),
    'top_zone_sections': dict(C.Counter(x['zs'] for x in kex).most_common(5)),
    'share_owner_occupied_if_included': pct(c['OO'], len(kmain) + len(kex))}
# vacant-lot sensitivity with 2020 building points (whole lots and land CPRs only; condo units match at master level)
def bmatch(rows):
    return {'records': len(rows), 'with_2020_assessor_building_record': sum(1 for x in rows if x['bldg2020']),
            'share_matched': pct(sum(1 for x in rows if x['bldg2020']), len(rows))}
lots = [x for x in kmain if not x['type'].startswith('condo')]
oo_m = bmatch([x for x in lots if x['cat'] == 'OO']); noo_m = bmatch([x for x in lots if x['cat'] == 'NOO']); vr_m = bmatch([x for x in lots if x['cat'] == 'VR'])
nob = [x for x in lots if x['cat'] == 'NOO' and not x['bldg2020']]
adj_n = len(kmain) - len(nob)
kres['sensitivity_possible_vacant_lots_in_class_1'] = {
    'note': 'Kauai\'s public layer has no building value, so vacant residential lots (taxed in class 1) cannot be removed directly. As a check, PARIDs were matched to the County of Kauai 2020 Hazard Mitigation Plan building points (assessor building records). Unmatched class-1 lots are an upper bound on vacant lots (they also include homes built after 2020 and match failures; owner-occupied lots, which must have a home, match at the rate shown).',
    'owner_occupied_lots_match_rate': oo_m, 'vacation_rental_lots_match_rate': vr_m, 'class_1_and_11_lots_match_rate': noo_m,
    'class_1_and_11_lots_without_2020_building_record': len(nob),
    'share_owner_occupied_if_all_unmatched_class1_lots_are_vacant': pct(c['OO'], adj_n),
    'share_vacation_rental_if_all_unmatched_class1_lots_are_vacant': pct(c['VR'], adj_n)}
ag = [r for r in K if r['TAXCLASS'] == '5:AGRICULTURAL']
kres['note_agricultural_class'] = {'agricultural_class_records': len(ag),
    'of_which_land_cpr_units': sum(1 for r in ag if r['TYPE'].startswith('CPR Unit')),
    'with_2020_assessor_residential_building_record': sum(1 for r in ag if r['PARID'] and int(r['PARID']) in hmp_parid_res),
    'note': 'Agricultural-class records are excluded from residential housing. Few carry a 2020 assessor residential building record, and every owner-occupied (class 8) record sits on a residential, vacation-rental or commercial base class (CLASS field), so the exclusion drops few homes.'}
kres['owner_type_of_main_universe'] = dict(C.Counter(x['owner'] for x in kmain))

# ================================================================== HAWAII COUNTY
hf = pages(os.path.join(R0, 'hawaii/cohrpt2026/cohrpt2026_*.json'))
H = [f['attributes'] for f in hf]
hc = {f['attributes']['OBJECTID']: f for f in pages(os.path.join(R, 'coh_centroids/coh_centroids_*.json'))}
assert len(H) == 135718 and all(hc[r['OBJECTID']]['attributes']['TMK'] == r['TMK'] for r in H)
seen, Hd = set(), []
for r in sorted(H, key=lambda r: r['OBJECTID']):
    if r['TMK'] in seen: continue
    seen.add(r['TMK']); Hd.append(r)
HXY = np.array([(hc[r['OBJECTID']]['centroid']['x'], hc[r['OBJECTID']]['centroid']['y']) for r in Hd])
HZ = {'1': 'Puna', '2': 'South Hilo', '3': 'North Hilo', '4': 'Hāmākua', '5': 'North Kohala', '6': 'South Kohala',
      '7': 'North Kona', '8': 'South Kona', '9': 'Kaʻū'}
PITT = {0: 'Unknown / Affordable Rental Housing (0)', 100: 'Residential (100)', 200: 'Apartment (200)', 300: 'Commercial (300)',
        400: 'Industrial (400)', 500: 'Agricultural or Native Forests (500)', 600: 'Conservation (600)', 700: 'Hotel and Resort (700)',
        900: 'Homeowner (900)', 999: 'Multiple codes for a single TMK (999)'}
tot = lambda r: (r['LandValue'] or 0) + (r['BldgValue'] or 0)
exm = lambda r: (r['LandExempt'] or 0) + (r['BldgExempt'] or 0)
suffix = lambda c: (c or '').strip().split('-', 1)[1] if '-' in (c or '') else ''
hrows, hmulti, h_excl = [], [], C.Counter()
for i, r in enumerate(Hd):
    p = r['PittCode']
    multi = p in (200, 999)
    if multi:
        hmulti.append({'i': i, 'r': r}); continue
    if p not in (100, 500):
        h_excl['class:' + PITT.get(p, str(p)) + (' (homeowner flag Y)' if r['Homeowner'] == 'Y' else '')] += 1
        continue
    if not (r['BldgValue'] or 0) > 0:
        h_excl['unimproved (building value 0):' + PITT[p]] += 1
        continue
    if r['Homeowner'] == 'Y':
        cat = 'OO'
    elif exm(r) >= tot(r):
        cat = 'EXEMPT'
    else:
        cat = 'NOO'
    hrows.append({'i': i, 'cat': cat, 'pitt': p, 'zone': str(r['TMK'])[1], 'nh': (r['NHoodCode'] or '').strip(),
                  'value': tot(r), 'exempt': exm(r), 'acres': r['TaxAcres'] or 0})
hmain = [x for x in hrows if x['cat'] != 'EXEMPT']
hex_ = [x for x in hrows if x['cat'] == 'EXEMPT']
hres = {}
hres['universe'] = {
    'records_in_layer': len(H), 'distinct_9digit_tmks': len(Hd), 'repeated_tmk_records_dropped': len(H) - len(Hd),
    'improved_single_tmk_housing_parcels_considered': len(hrows), 'main_universe_parcels': len(hmain),
    'fully_exempt_without_home_exemption_shown_separately': len(hex_),
    'probable_multi_unit_tmks_shown_separately': len(hmulti), 'excluded': dict(h_excl),
    'definition': 'Unit = 9-digit TMK parcel (the public layer has no CPR/condo-unit records). Housing parcel = PITT code 100 Residential or 500 Agricultural/Native Forests with building value > 0, excluding probable multi-unit TMKs (PITT 200 Apartment or PITT 999 multiple codes for one TMK). Owner-occupied = Homeowner exemption flag Y. Other non-owner-occupied = flag N/U with taxable value > 0. Parcels with no home exemption whose exemptions equal or exceed their value (mainly DHHL homestead leases, government and nonprofit property) are shown separately. Hawaii County has no vacation-rental tax class, so vacation rentals sit inside non-owner-occupied.'}
hres['island_residential_plus_agricultural_class'] = cell(hmain, False)
hres['island_residential_class_only_PITT100'] = cell([x for x in hmain if x['pitt'] == 100], False)
hres['island_agricultural_class_only_PITT500'] = cell([x for x in hmain if x['pitt'] == 500], False)
hres['by_district'] = {}
for z in '123456789':
    rows = [x for x in hmain if x['zone'] == z]
    d = cell(rows, False); d['district'] = HZ[z]
    d['residential_class_only_PITT100'] = cell([x for x in rows if x['pitt'] == 100], False)
    d['share_of_housing_parcels_in_agricultural_class'] = pct(sum(1 for x in rows if x['pitt'] == 500), len(rows))
    d['fully_exempt_without_home_exemption_separate'] = sum(1 for x in hex_ if x['zone'] == z)
    mz = [m for m in hmulti if str(m['r']['TMK'])[1] == z]
    d['probable_multi_unit_tmks_separate'] = {'tmks': len(mz), 'improved': sum(1 for m in mz if (m['r']['BldgValue'] or 0) > 0),
                                              'with_at_least_one_home_exemption': sum(1 for m in mz if m['r']['Homeowner'] == 'Y')}
    hres['by_district']['zone_%s_%s' % (z, HZ[z])] = d
hres['by_tier_assessed_land_plus_building'] = tier_table(hmain, False)
hres['by_district_by_tier'] = {'zone_%s_%s' % (z, HZ[z]): tier_table([x for x in hmain if x['zone'] == z], False) for z in '123456789'}
hres['value_shares'] = {k: v for k, v in vshare(hmain).items() if 'vacation' not in k}
# neighborhoods
nh_groups = C.defaultdict(list)
for x in hmain: nh_groups[x['nh'] or '(blank)'].append(x)
elig = {k: v for k, v in nh_groups.items() if len(v) >= 100}
labels = label_groups({k: [x['i'] for x in v] for k, v in elig.items()}, HXY)
nb = []
for k, v in elig.items():
    d = cell(v, False); d['nhood_code'] = k
    zc = C.Counter(x['zone'] for x in v).most_common(1)[0]
    d['district'] = HZ[zc[0]]; d['district_share'] = round(zc[1] / len(v), 3)
    d['place'] = labels[k]
    d['share_agricultural_class'] = pct(sum(1 for x in v if x['pitt'] == 500), len(v))
    d['median_assessed_value_usd'] = int(np.median([x['value'] for x in v]))
    nb.append(d)
nb.sort(key=lambda d: (-d['share_non_owner_occupied_total'], -d['units']))
hres['neighborhoods_eligible_(nhood_codes_with_100plus_parcels)'] = len(nb)
hres['top15_nhood_codes_by_non_owner_occupied_share'] = nb[:15]
hres['bottom5_nhood_codes_by_non_owner_occupied_share'] = nb[-5:]
hres['all_eligible_nhood_codes_sorted'] = [{'nhood_code': d['nhood_code'], 'label': d['place']['label'], 'district': d['district'],
                                           'units': d['units'], 'share_owner_occupied': d['share_owner_occupied'],
                                           'share_non_owner_occupied_total': d['share_non_owner_occupied_total']} for d in nb]
# multi-unit TMKs
hm_imp = [m for m in hmulti if (m['r']['BldgValue'] or 0) > 0]
hres['probable_multi_unit_tmks'] = {
    'tmks': len(hmulti), 'improved': len(hm_imp),
    'by_pitt': dict(C.Counter(PITT[m['r']['PittCode']] for m in hmulti)),
    'with_at_least_one_home_exemption': sum(1 for m in hmulti if m['r']['Homeowner'] == 'Y'),
    'total_assessed_value_usd': sum(tot(m['r']) for m in hmulti),
    'by_district_tmks': {HZ[z]: n for z, n in sorted(C.Counter(str(m['r']['TMK'])[1] for m in hmulti).items())},
    'note': 'Condominium and other multi-unit TMKs carry the summed values and exemptions of all their units, and the Homeowner flag is Y when any unit has a home exemption, so unit-level occupancy cannot be measured from this layer. The official State summary counts 8,727 Apartment-class records in Hawaii County for TY2026-27 against the layer\'s %d Apartment-coded TMKs.' % sum(1 for m in hmulti if m['r']['PittCode'] == 200)}
yex = [x for x in hmain if x['cat'] == 'OO' and x['exempt'] > 300_000 and x['exempt'] < x['value']]
hres['note_tmks_with_exemptions_above_300K'] = {'owner_occupied_parcels_with_partial_exemptions_above_300K': len(yex),
    'note': 'Above the largest single home-exemption amounts seen (about $275K); likely two or more home exemptions on one TMK (e.g. CPR\'d lots). Counted once.'}
hn_home = [x for x in hmain if x['cat'] == 'NOO' and x['exempt'] in (150000, 185000, 190000, 205000, 210000, 225000, 275000)]
_noo_by_d = C.Counter(x['zone'] for x in hn_home); _n_by_d = C.Counter(x['zone'] for x in hmain)
hres['note_flag_N_with_home_exemption_like_amounts'] = {'parcels': len(hn_home), 'share_of_universe': pct(len(hn_home), len(hmain)),
    'max_district_shift_points_if_reclassified': round(100 * max(_noo_by_d[z] / _n_by_d[z] for z in _n_by_d), 2),
    'note': 'Homeowner flag N but the exemption equals a common home-exemption amount ($150K, $185K, $190K, $205K, $210K, $225K or $275K); possibly a flag/exemption timing difference. Left as non-owner-occupied; reclassifying them would raise owner-occupied shares by the points shown at most.'}
hres['sensitivity_fully_exempt_counted_as_non_owner_occupied'] = {
    'fully_exempt_parcels': len(hex_), 'by_district': {HZ[z]: n for z, n in sorted(C.Counter(x['zone'] for x in hex_).items())},
    'top_nhood_codes': dict(C.Counter(x['nh'] for x in hex_).most_common(6)),
    'share_owner_occupied_if_included': pct(sum(1 for x in hmain if x['cat'] == 'OO'), len(hmain) + len(hex_))}
hres['homeowner_flag_in_excluded_classes'] = {k: v for k, v in h_excl.items() if 'flag Y' in k}

# ================================================================== District verification (spatial)
jd = geo.load_polygons(os.path.join(R, 'districts/hawaii_judicial_districts.json'))
a = geo.assign(jd, HXY, lambda at: at['NUMBER'])
agree = sum(1 for i, r in enumerate(Hd) if a[i] == str(r['TMK'])[1]); none_ = sum(1 for v in a if v is None)
kz = geo.load_polygons(os.path.join(R, 'districts/kauai_zones.json'))
b = geo.assign(kz, KXY, lambda at: at['ZONEPIT'])
kagree = sum(1 for i, r in enumerate(K) if b[i] == r['ZONE']); knone = sum(1 for v in b if v is None)
jd_names = sorted({(p['attrs']['NUMBER'], p['attrs']['NAME']) for p in jd})
kz_names = sorted({(p['attrs']['ZONEPIT'], p['attrs']['Name'], p['attrs']['ZONETEXT']) for p in kz})
verification = {
    'hawaii_county': {'official_layer': 'County of Hawaii Hawaii_Co_Judicial_Districts (NAME, NUMBER)',
                      'number_to_name': [{'number': n, 'name': nm} for n, nm in jd_names],
                      'parcels_whose_centroid_falls_in_district_of_same_number_as_TMK_zone': agree,
                      'parcels_with_centroid_outside_all_district_polygons': none_, 'parcels': len(Hd),
                      'agreement_share_of_located': pct(agree, len(Hd) - none_)},
    'kauai': {'official_layer': 'County of Kauai ZonesKauaiwm (ZONEPIT, Name, ZONETEXT)',
              'zone_to_name': [{'zone': z, 'name': nm, 'text': t} for z, nm, t in kz_names],
              'records_whose_centroid_falls_in_zone_polygon_matching_ZONE': kagree,
              'records_with_centroid_outside_all_zone_polygons': knone, 'records': len(K),
              'agreement_share_of_located': pct(kagree, len(K) - knone)}}

# ================================================================== Official State RPT summary (TY2026-27)
def pdftext(name):
    return subprocess.run(['pdftotext', '-layout', os.path.join(R, name), '-'], capture_output=True, text=True).stdout
rec = pdftext('state-report-fy27-final_records.pdf')
recs = {}
for line in rec.splitlines():
    m = re.match(r'\s*([A-Za-z][A-Za-z/ \-]+?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$', line)
    if m:
        recs[m.group(1).strip()] = dict(zip(['honolulu', 'maui', 'hawaii', 'kauai', 'statewide'], [int(g.replace(',', '')) for g in m.groups()[1:]]))
exm_t = pdftext('state-report-fy27-final_exemptions.pdf')
exs = {}
for line in exm_t.splitlines():
    m = re.match(r'\s*(Homes - [A-Za-z]+ - [A-Za-z]+)\s+(.*)$', line)
    if m:
        toks = re.findall(r'\$\s*([\d,]+|-)|([\d,]+)', m.group(2))
        nums, amts = [], []
        for a_, n_ in toks:
            if n_: nums.append(int(n_.replace(',', '')))
            else: amts.append(0 if a_ == '-' else int(a_.replace(',', '')))
        if len(nums) == 5 and len(amts) == 4:
            amts.insert(3, 0)  # Kauai amount printed blank for a zero row
        assert len(nums) == 5 and len(amts) == 5, (line, nums, amts)
        exs[m.group(1)] = {c: {'number': nums[j], 'amount_thousands': amts[j]} for j, c in enumerate(['honolulu', 'maui', 'hawaii', 'kauai', 'statewide'])}
home_ex = {c: sum(v[c]['number'] for v in exs.values()) for c in ['honolulu', 'maui', 'hawaii', 'kauai', 'statewide']}
def r_(name, county): return recs[name][county]
off = {}
k_oo = r_('Owner-Occupied', 'kauai') + r_('Owner-Occupied Mixed Use', 'kauai')
k_den = k_oo + r_('Non Owner-Occupied', 'kauai') + r_('Vacation Rental', 'kauai') + r_('Long-Term Affordable Rental', 'kauai')
off['kauai'] = {'owner_occupied_records_(OO+OO_mixed_use)': k_oo, 'non_owner_occupied': r_('Non Owner-Occupied', 'kauai'),
                'vacation_rental': r_('Vacation Rental', 'kauai'), 'long_term_affordable_rental': r_('Long-Term Affordable Rental', 'kauai'),
                'hotel_resort': r_('Hotel/Resort', 'kauai'), 'residential_records_denominator': k_den,
                'share_owner_occupied': pct(k_oo, k_den), 'share_vacation_rental': pct(r_('Vacation Rental', 'kauai'), k_den)}
h_den = r_('Homeowner', 'hawaii') + r_('Residential', 'hawaii') + r_('Apartment', 'hawaii') + r_('Long-Term Rental', 'hawaii') + r_('Affordable Rental', 'hawaii')
off['hawaii'] = {'homeowner': r_('Homeowner', 'hawaii'), 'residential': r_('Residential', 'hawaii'), 'apartment': r_('Apartment', 'hawaii'),
                 'long_term_rental': r_('Long-Term Rental', 'hawaii'), 'affordable_rental': r_('Affordable Rental', 'hawaii'),
                 'agricultural': r_('Agricultural', 'hawaii'), 'hotel_resort': r_('Hotel/Resort', 'hawaii'),
                 'residential_records_denominator_(homeowner+residential+apartment+LTR+affordable)': h_den,
                 'share_homeowner': pct(r_('Homeowner', 'hawaii'), h_den),
                 'caveat': 'Residential-class records include vacant residential lots; agricultural-class records (42,759, incl. many homes without a home exemption and vacant ag lots) are not in the denominator. Not directly comparable with the parcel-layer figures.'}
m_oo = r_('Owner-Occupied', 'maui')
m_den = m_oo + r_('Non Owner-Occupied', 'maui') + r_('Short-Term Rental/TVR', 'maui') + r_('Long-Term Rental', 'maui') + r_('Apartment', 'maui') + r_('Commercialized Res', 'maui')
off['maui'] = {'owner_occupied': m_oo, 'non_owner_occupied': r_('Non Owner-Occupied', 'maui'), 'short_term_rental_tvr': r_('Short-Term Rental/TVR', 'maui'),
               'long_term_rental': r_('Long-Term Rental', 'maui'), 'apartment': r_('Apartment', 'maui'), 'commercialized_res': r_('Commercialized Res', 'maui'),
               'time_share_excluded': r_('Time Share', 'maui'), 'residential_records_denominator': m_den,
               'share_owner_occupied': pct(m_oo, m_den), 'share_short_term_rental': pct(r_('Short-Term Rental/TVR', 'maui'), m_den)}
off['raw_rows_parsed'] = recs
off['home_exemptions_by_type'] = exs
off['home_exemptions_total_number'] = home_ex

# ================================================================== Comparisons with report figures
on = json.load(open(os.path.join(S, 'an/new/owners_neighbor.json')))['counties']['maui']['results']
oa = json.load(open(os.path.join(S, 'an/new/owners_oahu.json')))['results']
cls = {k.split(' ')[0]: v['parcels'] for k, v in on['by_tax_class_code'].items()}
m_res = sum(cls[c] for c in ['1', '2', '9', '10', '11', '12'])
assert m_res == on['residential_classes_1_2_9_10_11_12']['parcels']
noo_m = on['non_owner_occupied_residential_classes_1_2_11_12']
ex_o = oa['residential_class1_any_exemption_by_owner_location']
o_all = sum(v['parcels'] for v in ex_o.values()); o_ex = sum(v['with_any_exemption'] for v in ex_o.values())
o_noex_hi = ex_o['hawaii']['parcels'] - ex_o['hawaii']['with_any_exemption']
o_noex = o_all - o_ex
comparison = {
    'maui_county_from_owners_neighbor_json': {
        'residential_parcels_classes_1_2_9_10_11_12': m_res,
        'owned_from_outside_hawaii_share_(report_30.6%)': on['residential_classes_1_2_9_10_11_12']['share_of_classified']['non_hawaii_total'],
        'owner_occupied_class_9_share': pct(cls['9'], m_res),
        'owner_occupied_class_9_plus_10_share': pct(cls['9'] + cls['10'], m_res),
        'short_term_rental_class_11_share': pct(cls['11'], m_res),
        'other_non_owner_occupied_classes_1_2_12_share': pct(cls['1'] + cls['2'] + cls['12'], m_res),
        'non_owner_occupied_residential_parcels_classes_1_2_11_12': noo_m['parcels'],
        'of_which_mailing_outside_hawaii_share': noo_m['share_of_classified']['non_hawaii_total'],
        'of_which_mailing_in_hawaii_share': noo_m['share_of_classified']['hawaii'],
        'homeowner_flag_Y_parcels_certified_roll': on['homeowner_flag_certified_roll']['Y']['parcels'],
        'homeowner_flag_Y_mailing_outside_hawaii_share': on['homeowner_flag_certified_roll']['Y']['share_of_classified']['non_hawaii_total']},
    'oahu_from_owners_oahu_json': {
        'hawaii_addressed_residential_parcels_with_any_exemption_share_(report_62%)': ex_o['hawaii']['share_with_any_exemption'],
        'all_addressed_residential_class1_parcels': o_all,
        'all_addressed_residential_class1_with_any_exemption_share': pct(o_ex, o_all),
        'residential_parcels_without_any_exemption': o_noex,
        'of_which_hawaii_addressed_share': pct(o_noex_hi, o_noex),
        'caveat': 'Oahu measure is any land/building exemption on residential tax-class parcels (home exemptions dominate but are not separated); not the same as an owner-occupied tax class.'},
    'plain_english': 'Non-owner-occupied means the parcel has no home exemption / owner-occupied class. That includes local landlords, long-term rentals, homes held by relatives or trusts, vacation rentals and second homes. It is NOT the same as off-island ownership: on Maui, where mailing addresses are public, %s of non-owner-occupied residential parcels have a Hawaii mailing address; on Oahu %s of residential parcels without any exemption do. Kauai and Hawaii County owner mailing addresses are not public, so their non-owner-occupied shares must not be read as out-of-state shares.' % (P(noo_m['share_of_classified']['hawaii']), P(o_noex_hi / o_noex))}

# ================================================================== Assemble
kmeta = json.load(open(os.path.join(R0, 'kauai_meta/TY26_PropertyTaxData_0.json')))
hmeta = json.load(open(os.path.join(R0, 'hawaii_meta/cohRPT_0.json')))
ksha, kn = sha_concat(os.path.join(R0, 'kauai/ty26/ty26_*.json'))
hsha, hn = sha_concat(os.path.join(R0, 'hawaii/cohrpt2026/cohrpt2026_*.json'))
ts = lambda ms: datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
ki, hi = kres['island'], hres['island_residential_plus_agricultural_class']
kd, hd = kres['by_district'], hres['by_district']
def kfig(fid, label, value, how): return {'id': fid, 'label': label, 'value': value, 'how_to_rederive': how}
k3m = kres['by_tier_market_value_MODTOT']['3M_plus_(luxury+ultra)']
h3m = hres['by_tier_assessed_land_plus_building']['3M_plus_(luxury+ultra)']
ktop = kres['top15_zone_sections_by_non_owner_occupied_share'][0]
htop = hres['top15_nhood_codes_by_non_owner_occupied_share'][0]
kres['reconciliation_with_official_TY2026_27_records'] = {
    'layer_main_universe': {'owner_occupied_8_10': ki['owner_occupied'], 'vacation_rental_2': ki['vacation_rental_class'],
                            'non_owner_occupied_1_taxable': kres['island']['by_class_records'].get('1:NON-OWNER-OCCUPIED RESIDENTIAL'),
                            'long_term_affordable_rental_11': kres['island']['by_class_records'].get('11:LONG TERM AFFORDABLE RENTAL')},
    'official_records': {k_: off['kauai'][k_] for k_ in ['owner_occupied_records_(OO+OO_mixed_use)', 'vacation_rental', 'non_owner_occupied', 'long_term_affordable_rental']},
    'official_home_exemptions': home_ex['kauai'],
    'note': 'Class counts in the layer differ slightly from the State summary; the cause of the small differences is unknown. Shares agree within half a point.'}
hres['reconciliation_with_official_TY2026_27'] = {
    'layer_tmks_with_homeowner_flag_Y_all_classes': sum(1 for r in Hd if r['Homeowner'] == 'Y'),
    'official_homeowner_class_records': off['hawaii']['homeowner'], 'official_home_exemptions': home_ex['hawaii'],
    'note': 'The official counts are per tax record (condo units counted individually); the layer is per 9-digit TMK, so the layer has fewer homeowner TMKs than official homeowner records.'}
mn = comparison['maui_county_from_owners_neighbor_json']
k_poipu = next(d for d in kres['top15_zone_sections_by_non_owner_occupied_share'] if d['zone_section'] == '2-8')
hu = hres['by_tier_assessed_land_plus_building']['ultra_10M+']
k_condo = kres['island_condo_units_only']
key_figures = [
    kfig('kauai_oo_share', 'Kauai: residential units in an owner-occupied tax class (TY2026-27)', ki['share_owner_occupied'],
         'TY26_PropertyTaxData: TAXCLASS 8 or 10 / TAXCLASS 1,2,8,10,11, dropping %d condo master records and %d class-1 records with TAXABLE=0 (%d / %d). Official State summary gives %s.' % (k_excluded['condo_master_record_(units_listed_separately)'], len(kex), ki['owner_occupied'], ki['units'], off['kauai']['share_owner_occupied'])),
    kfig('kauai_vr_share', 'Kauai: residential units in the Vacation Rental class', ki['share_vacation_rental_class'],
         'Same universe; TAXCLASS 2 (%d / %d).' % (ki['vacation_rental_class'], ki['units'])),
    kfig('kauai_condo', 'Kauai condo units (TYPE CPRX Multi-Unit Complex): owner-occupied / vacation-rental shares', {'owner_occupied': k_condo['share_owner_occupied'], 'vacation_rental': k_condo['share_vacation_rental_class'], 'units': k_condo['units']},
         'Universe records whose TYPE starts "CPRX Multi-Unit Complex"; class 8+10 and class 2 shares.'),
    kfig('kauai_hanalei', 'Kauai Hanalei district (zone 5): not owner-occupied (of which vacation-rental class)', {'non_owner_occupied': kd['zone_5_Hanalei']['share_non_owner_occupied_total'], 'vacation_rental': kd['zone_5_Hanalei']['share_vacation_rental_class'], 'units': kd['zone_5_Hanalei']['units']},
         'Zone 5 records in the Kauai universe: (class 2 + class 1/11) / all.'),
    kfig('kauai_poipu', 'Kauai zone-section 2-8 (Poipu CDP): not owner-occupied (of which vacation-rental class)', {'non_owner_occupied': k_poipu['share_non_owner_occupied_total'], 'vacation_rental': k_poipu['share_vacation_rental_class'], 'units': k_poipu['units']},
         'Universe records with ZONE=2, SECTION=8; label from Census 2020 CDP containing %s of record centroids.' % P(k_poipu['place']['census2020_cdp_top'][0]['share_of_units'])),
    kfig('kauai_3m', 'Kauai residential units with county market value $3M+: not owner-occupied', {'share': k3m['share_non_owner_occupied_total'], 'units': k3m['units']},
         'Universe records with MODTOT >= 3,000,000: (class 2 + class 1/11) / all = %d / %d.' % (k3m['vacation_rental_class'] + k3m['other_non_owner_occupied'], k3m['units'])),
    kfig('hawaii_oo_share', 'Hawaii County: improved house parcels (Residential + Agricultural class, condos excluded) with a home exemption', hi['share_owner_occupied'],
         'cohRPT2026, one record per TMK, PittCode 100 or 500, BldgValue > 0, PittCode 200/999 excluded, parcels with no home exemption and exemptions >= value excluded: Homeowner=Y / all (%d / %d). Residential class only: %s.' % (hi['owner_occupied'], hi['units'], hres['island_residential_class_only_PITT100']['share_owner_occupied'])),
    kfig('hawaii_lowest_districts', 'Hawaii County: lowest owner-occupied districts (house parcels)', {'Kaʻū': hd['zone_9_Kaʻū']['share_owner_occupied'], 'South Kona': hd['zone_8_South Kona']['share_owner_occupied'], 'Puna': hd['zone_1_Puna']['share_owner_occupied'], 'Puna_residential_class_only': hd['zone_1_Puna']['residential_class_only_PITT100']['share_owner_occupied']},
         'Universe split by TMK zone digit (9 Kaʻū, 8 South Kona, 1 Puna); Homeowner=Y / all.'),
    kfig('hawaii_3m', 'Hawaii County house parcels assessed $3M+ / $10M+ without a home exemption', {'3M_plus': h3m['share_non_owner_occupied_total'], '3M_plus_parcels': h3m['units'], '10M_plus': hu['share_non_owner_occupied_total'], '10M_plus_parcels': hu['units']},
         'Universe parcels with LandValue+BldgValue >= 3,000,000 (>= 10,000,000): Homeowner<>Y / all.'),
    kfig('hawaii_multi_unit', 'Hawaii County multi-unit TMKs (condo projects, apartments, multi-class) left out because units are not separate records', hres['probable_multi_unit_tmks']['tmks'],
         'cohRPT2026 distinct TMKs with PittCode 200 or 999; official State summary counts %d Apartment-class records.' % off['hawaii']['apartment']),
    kfig('official_oo_records', 'Official TY2026-27 State summary: owner-occupied share of residential-type records', {'Kauai': off['kauai']['share_owner_occupied'], 'Maui': off['maui']['share_owner_occupied'], 'Hawaii_County_homeowner': off['hawaii']['share_homeowner']},
         'state-report-fy27-final_records.pdf: Kauai (Owner-Occupied + OO Mixed Use)/(+Non Owner-Occupied, Vacation Rental, LT Affordable Rental); Maui Owner-Occupied/(+Non Owner-Occupied, STR/TVR, Long-Term Rental, Apartment, Commercialized Res); Hawaii Homeowner/(+Residential, Apartment, Long-Term Rental, Affordable Rental; includes vacant residential lots).'),
    kfig('maui_comparison', 'Maui comparison: owner-occupied class share of residential parcels; share of non-owner-occupied parcels mailing to Hawaii', {'maui_owner_occupied_class9': mn['owner_occupied_class_9_share'], 'maui_owned_from_outside_hawaii': mn['owned_from_outside_hawaii_share_(report_30.6%)'], 'maui_non_owner_occupied_with_hawaii_mailing': mn['of_which_mailing_in_hawaii_share'], 'oahu_hawaii_owned_with_exemption': comparison['oahu_from_owners_oahu_json']['hawaii_addressed_residential_parcels_with_any_exemption_share_(report_62%)']},
         'owners_neighbor.json counties.maui.results: by_tax_class_code 9 / residential_classes_1_2_9_10_11_12; non_owner_occupied_residential_classes_1_2_11_12.share_of_classified.hawaii; owners_oahu.json residential_class1_any_exemption_by_owner_location.hawaii.'),
]
result = {
    'key': 'occupancy_kh',
    'title': 'Kauai and Hawaii County owner-occupancy proxy from 2026 county tax rolls (tax class / home-exemption based; not owner origin)',
    'generated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'source': {
        'kauai_roll': {'name': 'County of Kauai GIS - TY26_PropertyTaxData ("Tax Classes and Assessment data for 2026 tax year")',
                       'url': 'https://services1.arcgis.com/0DaVqrPt2eyXUS9g/arcgis/rest/services/TY26_PropertyTaxData/FeatureServer/0',
                       'item': 'https://www.arcgis.com/home/item.html?id=fe46d9ae37e6471e84bd14baf1df42e1',
                       'edition': 'Tax year 2026 (TAXYR=2026); class counts match the official TY July 1 2026-June 30 2027 State summary (e.g. Owner-Occupied Mixed Use 2,073 = 2,073; gross value $2,204,808K = $2,204,808K)',
                       'data_last_edit_utc': ts(kmeta['editingInfo']['dataLastEditDate']), 'records': len(K), 'pages': kn,
                       'sha256_concat_pages': ksha, 'fetched': '2026-10-08 (raw/owners_neighbor/MANIFEST.txt)',
                       'fields_used': 'ZONE, SECTION, PLAT, PARCEL, CPR_UNIT, PARID (join only), TYPE, TAXCLASS, CLASS, OVRCLASS, MODTOT, ASSDTOT, TOTEXEMPT, TAXABLE, CDOMSTR; owner name field never pulled'},
        'hawaii_roll': {'name': 'County of Hawaii - cohRPT2026 ("County of Hawaii Properties as of April 2026": certified assessments)',
                        'url': 'https://services1.arcgis.com/C2LPusZs5OXNGFDn/arcgis/rest/services/cohRPT/FeatureServer/0',
                        'item': 'https://www.arcgis.com/home/item.html?id=77b943e9e75f44f891b52eddfeaa9cf6',
                        'edition': 'Certified roll April 2026 (tax year July 1 2026-June 30 2027)', 'data_last_edit_utc': ts(hmeta['editingInfo']['dataLastEditDate']),
                        'records': len(H), 'pages': hn, 'sha256_concat_pages': hsha, 'fetched': '2026-10-08 (raw/owners_neighbor/MANIFEST.txt)',
                        'fields_used': 'TMK (zone digit, dedupe, join only), LandValue, BldgValue, LandExempt, BldgExempt, PittCode, Homeowner, NHoodCode, TaxAcres; owner fields never pulled'},
        'class_definitions': {
            'hawaii_county': {'url': 'https://www.arcgis.com/home/item.html?id=77b943e9e75f44f891b52eddfeaa9cf6 (item description by County of Hawaii, raw/up_occupancy_kh/item_77b943e9e75f44f891b52eddfeaa9cf6.json)',
                              'text': 'PittCode: Residential (100), Apartment (200), Commercial (300), Industrial (400), Agricultural or Native Forests (500), Conservation (600), Hotel and Resort (700), Homeowner (900), Multiple codes for a single TMK (999), Unknown (0); code 0 is used for Affordable Rental Housing for tax-rate purposes. Homeowner: homeowner exemption applied (Yes/No/Unknown).',
                              'observed': 'PittCode values present: %s (no 900). Homeowner-exempt parcels keep code 100/500 etc. with Homeowner=Y. Code-0 TMKs: %d, of which %d have zero land and building value and %d have a blank neighborhood code, so Affordable Rental and the new Long-Term Rental class are not identifiable in the layer.' % (sorted(C.Counter(r['PittCode'] for r in Hd).items()), sum(1 for r in Hd if r['PittCode'] == 0), sum(1 for r in Hd if r['PittCode'] == 0 and tot(r) == 0), sum(1 for r in Hd if r['PittCode'] == 0 and not (r['NHoodCode'] or '').strip()))},
            'kauai': {'url': 'Class labels are embedded in the County layer (TAXCLASS e.g. "8:OWNER-OCCUPIED"); official class list and FY2026-27 counts: https://realproperty.honolulu.gov/media/3txnaost/state-report-fy27-final_kauai.pdf and https://realproperty.honolulu.gov/media/jvmlb03w/state-report-fy27-final_records.pdf; rates by class: https://files.hawaii.gov/dbedt/economic/databook/2024-individual/09/094924.pdf (State Data Book 2024 Table 9.49)',
                      'observed': 'CLASS = base (use) class; OVRCLASS = owner-occupancy/affordable-rental override; TAXCLASS = final. Base classes under TAXCLASS 8: %s.' % dict(C.Counter(r['CLASS'] for r in K if r['TAXCLASS'] == '8:OWNER-OCCUPIED'))}},
        'official_totals': {'name': 'State of Hawaii real property tax valuation / records / exemption summaries, TY July 1 2026-June 30 2027 (Technical Branch, Real Property Assessment Division, City and County of Honolulu)',
                            'index': 'https://realproperty.honolulu.gov/statewide-reports/2026-27/', 'date': 'July 2026'},
        'district_names': {'hawaii': 'https://services1.arcgis.com/C2LPusZs5OXNGFDn/arcgis/rest/services/Hawaii_Co_Judicial_Districts/FeatureServer/0',
                           'kauai': 'https://services1.arcgis.com/0DaVqrPt2eyXUS9g/arcgis/rest/services/ZonesKauaiwm/FeatureServer/0'},
        'place_names': 'US Census Bureau TIGERweb, Census 2020 Census Designated Places (layer 26) and County Subdivisions (layer 22): https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer',
        'parcel_centroids': 'returnCentroid queries on the same two county layers (OBJECTID join, TMK/PARID verified 100%)',
        'kauai_buildings_2020': 'County of Kauai KauaiHMP_gdb layer 16 AllBldg_RPA_pts (assessor building points, data 2020-09): https://services1.arcgis.com/0DaVqrPt2eyXUS9g/arcgis/rest/services/KauaiHMP_gdb/FeatureServer/16',
        'comparison_inputs': ['an/new/owners_neighbor.json (Maui)', 'an/new/owners_oahu.json (Oahu)'],
        'manifest': os.path.join(R, 'MANIFEST.txt'), 'build_script': os.path.abspath(__file__)},
    'method': [
        'Counts are tax-roll records (Kauai: parcels plus CPR/condo units; Hawaii County: 9-digit TMK parcels). No sampling; every record is classified.',
        'Kauai: owner-occupied = TAXCLASS 8 Owner-Occupied or 10 Owner-Occupied Mixed-Use (these classes require the owner to live there and carry the home exemption); vacation rental = class 2; other non-owner-occupied = class 1 Non-Owner-Occupied Residential + class 11 Long-Term Affordable Rental with taxable value > 0. Condo master records whose units are listed separately (CDOMSTR=2) are dropped to avoid double counting.',
        'Kauai unit types from the layer TYPE field: "CPRX Multi-Unit Complex" = condominium unit; "CPR Unit" = land CPR (house-lot) unit; "TMK Parcel" = whole lot.',
        'Kauai value tiers use MODTOT (taken to be the county market value: it equals ASSDTOT except where an owner-occupied assessment limit or agricultural-use value appears to apply; %s of class-8 records have MODTOT > ASSDTOT, median ratio %.2f, while %s of class 1/2 records are equal; the field is not documented in the layer). An ASSDTOT-based tier table is also given.' % (P(MODSTAT['class8_share_MODTOT_gt_ASSDTOT']), MODSTAT['class8_median_ratio_when_greater'], P(MODSTAT['class1_2_share_equal'])),
        'Hawaii County: one record per distinct 9-digit TMK (76 repeated polygon records for 52 multipart TMKs dropped, all attribute-identical). Housing parcel = PittCode 100 or 500 with BldgValue > 0. Owner-occupied = Homeowner flag Y. Parcels with no home exemption and exemptions >= assessed value are shown separately (DHHL homestead leases, government, nonprofit). Probable multi-unit TMKs (PittCode 200 Apartment or 999 Multiple codes) are shown separately because their values and exemptions are summed across units.',
        'Hawaii County value = LandValue + BldgValue (gross assessed value).',
        'Tiers: entry < $750K; mid $750K to < $1.5M; upper $1.5M to < $3M; luxury $3M to < $10M; ultra >= $10M (assessed/market value, not sale price).',
        'Neighborhoods: Kauai zone-section (TMK zone + section) and Hawaii County NHoodCode (County RPT neighborhood code), each limited to groups with >= 100 units in the main universe, ranked by non-owner-occupied share. Labels = the Census 2020 CDP containing at least half of the group\'s parcel centroids (point-in-polygon on TIGERweb polygons); otherwise "<CDP> area" if >= 25% fall in one CDP, else the Census County Subdivision.',
        'District names verified two ways: the counties\' own district layers map number to name, and parcel centroids were tested against the district polygons (agreement rates in results.district_verification).',
        'Cells with fewer than 20 units carry flag_fewer_than_20_units.'],
    'notes': [
        'This is an OCCUPANCY proxy, not an origin measure. Kauai and Hawaii County owner mailing addresses are not published, so nothing here says where owners live.',
        comparison['plain_english'],
        'Hawaii County has no vacation-rental tax class (none in the County PITT list or the TY2026-27 State summary); vacation rentals are inside non-owner-occupied. On Kauai, condo units taxed as Hotel & Resort (%d) are outside the residential universe unless the sensitivity is used.' % len(hr),
        'Hawaii County figures are per TMK parcel. Condominium units are not separate records in the public layer, so island figures describe houses and house-lots (incl. homes on agricultural land) and exclude %d probable multi-unit TMKs (Apartment or multiple-class codes), which include the condominium projects. On Kauai only %s of condo units are owner-occupied versus %s of lots, so leaving condos out likely overstates Hawaii County\'s unit-level owner-occupied share.' % (len(hmulti), P(kres['island_condo_units_only']['share_owner_occupied']), P(kres['island_non_condo_(lots_and_land_CPRs;_closest_to_Hawaii_County_house-lot_basis)']['share_owner_occupied'])),
        'Kauai\'s class 1 includes vacant residential lots (no building field in the public layer), which inflates other non-owner-occupied; see sensitivity_possible_vacant_lots_in_class_1.',
        'Hawaii County agricultural-class improved parcels include some farm buildings without a dwelling; the Residential-class-only figure is given for comparison.',
        'Owner-occupied counts follow the counties\' 2026 certification; homes sold or re-occupied since then may have changed status.'],
    'gaps': [
        'kauai.gov (e.g. the Bill 2944 Long-Term Affordable Rental public-hearing PDF, https://kauai.gov/files/assets/public/v/1/county-council/documents/public-hearings/2025-03-25-ph-re-bn-2944.pdf) returned HTTP 403 on 2026-10-09; Kauai class definitions were taken from the County layer labels and the official State RPT summary instead.',
        'Official neighborhood names for Hawaii County NHoodCode values and Kauai zone-sections are not published in the layers (the County RPT sites are blocked); labels are Census 2020 CDP / County Subdivision names assigned by parcel-centroid location.',
        'hawaiicounty.gov and hawaiipropertytax.com were blocked earlier in this project (Akamai 403 / Cloudflare challenge; see owners_neighbor.json attempts); Hawaii County definitions come from the County\'s own ArcGIS item description.',
        'Hawaii County condo/CPR unit records are not in any public County layer found; unit-level occupancy for condos cannot be computed. The County ArcGIS RPT folder requires a token (not attempted).',
        'County of Kauai BUILDINGS_public layer (building cards) is marked "internal and partner official use only" and was not used.',
        'Kauai and Hawaii County owner mailing addresses: not public (see owners_neighbor.json).',
        'Hawaii County Affordable Rental Housing (2,048 records) and the new Long-Term Rental class (880 records) are not identifiable in the GIS layer; they sit inside non-owner-occupied or the multi-unit group.'],
    'key_figures': key_figures,
    'results': {'kauai': kres, 'hawaii_county': hres, 'district_verification': verification,
                'official_state_rpt_summary_TY2026_27': off, 'comparison_with_report_figures': comparison}}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(result, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('wrote', OUT)
