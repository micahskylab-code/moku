# District scorecards, 2026 to date vs the same months of 2025.
# Oahu, Hawaii Island, Kauai: Fidelity National Title August 2026 summaries (pdftotext -layout), which republish
#   HiCentral MLS / HBR (Oahu), Hawaii Information Service MLS (Hawaii Island) and Kauai Board of REALTORS data.
# Maui County: REALTORS Association of Maui September 2026 report, already parsed into an/mm/district_stats.json.
import re, json, hashlib
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
T = f'{S}/pull/mm_district_stats-verify/txt'
RAW = f'{S}/raw/mm_district_stats-verify'
num = lambda t: None if t in ('-', '') else int(t.replace('$', '').replace(',', '').replace('%', ''))
TOK = r'(-|\$?-?[\d,]+%?)'


def fid_tables(path, districts):
    """Fidelity neighbor-island page 2: RESIDENTIAL / CONDOMINIUM / VACANT LAND blocks, 9 numbers per district row."""
    pg = open(path).read().split('\f')[1]
    out, sec = {}, None
    for ln in pg.splitlines():
        s = ln.strip()
        if re.match(r'^RESIDENTIAL\b', s): sec = 'house'
        elif re.match(r'^CONDOMINIUM\b', s): sec = 'condo'
        elif re.match(r'^VACANT LAND\b', s): sec = 'land'
        for dn in districts + ['TOTAL']:
            if sec and s.startswith(dn + ' '):
                toks = s[len(dn):].split()
                if len(toks) == 9 and all(re.fullmatch(TOK, t) for t in toks):
                    v = [num(t) for t in toks]
                    out.setdefault(sec, {})[dn] = dict(n26=v[0], n25=v[1], med26=v[3], med25=v[4], vol26=v[6], vol25=v[7])
    for sec, rows in out.items():  # district rows must sum to TOTAL
        tot = rows['TOTAL']; s26 = sum(r['n26'] or 0 for k, r in rows.items() if k != 'TOTAL')
        assert s26 == tot['n26'], (path, sec, s26, tot)
    return out


AREAS = ["Aina Haina - Kuliouou", "Ala Moana - Kakaako", "Downtown - Nuuanu", "Ewa Plain", "Hawaii Kai", "Kailua - Waimanalo",
         "Kalihi - Palama", "Kaneohe", "Kapahulu - Diamond Head", "Makaha - Nanakuli", "Makakilo", "Makiki - Moiliili", "Mililani",
         "Moanalua - Salt Lake", "North Shore", "Pearl City - Aiea", "Wahiawa", "Waialae - Kahala", "Waikiki", "Waipahu",
         "Windward Coast", "SUMMARY"]


def oahu_ytd(path):
    pages = open(path).read().split('\f')
    pat = r'\s+(-|[\d,]+)\s+(-|[\d,]+)\s+(-?\d+%|-)\s+(-|\$[\d,]+)\s+(-|\$[\d,]+)\s+(-?\d+%|-)'
    out = {}
    for typ, pg in (('house', pages[2]), ('condo', pages[3])):
        rows = {}
        for ln in pg.splitlines():
            for a in AREAS:
                m = re.search(re.escape(a) + pat, ln)
                if m and a not in rows:
                    g = [num(x) for x in m.groups()]
                    rows[a] = dict(n26=g[0], n25=g[1], med26=g[3], med25=g[4])
        assert len(rows) == 22, (typ, len(rows))
        s = sum(r['n26'] or 0 for k, r in rows.items() if k != 'SUMMARY')
        assert s == rows['SUMMARY']['n26'], (typ, s, rows['SUMMARY'])
        rows['TOTAL'] = rows.pop('SUMMARY')
        out[typ] = rows
    return out


BI = ['PUNA', 'SOUTH HILO', 'NORTH HILO', 'HAMAKUA', 'NORTH KOHALA', 'SOUTH KOHALA', 'NORTH KONA', 'SOUTH KONA', "KA'U"]
KA = ['WAIMEA', 'KOLOA', 'LIHUE', 'KAWAIHAU', 'HANALEI']
res = {
    'Oahu': {'period': 'Jan–Aug 2026 vs Jan–Aug 2025', 'source': 'Honolulu Board of REALTORS / HiCentral MLS, via Fidelity National Title August 2026 Oʻahu report',
             'file': 'FINAL-Oahu-Stats-AUGUST-2026_1.pdf', 'data': oahu_ytd(f'{T}/fntic_FINAL-Oahu-Stats-AUGUST-2026_1.txt')},
    'Hawaii Island': {'period': 'Jan–Aug 2026 vs Jan–Aug 2025', 'source': 'Hawaii Information Service MLS, via Fidelity National Title August 2026 Big Island report',
                      'file': 'FINAL-Big-Island-AUGUST-2026.pdf', 'data': fid_tables(f'{T}/fntic_FINAL-Big-Island-AUGUST-2026.txt', BI)},
    'Kauai': {'period': 'Jan–Aug 2026 vs Jan–Aug 2025', 'source': 'Kauai Board of REALTORS, via Fidelity National Title August 2026 Kauai report',
              'file': 'FINAL-Kauai-Stats-AUGUST-2026.pdf', 'data': fid_tables(f'{T}/fntic_FINAL-Kauai-Stats-AUGUST-2026.txt', KA)},
}
for k, v in res.items():
    v['url'] = 'https://hawaii.fntic.com/FNTRSHawaii/media/FNT-RS-Hawaii/PDF/' + v['file']
    v['sha256'] = hashlib.sha256(open(f'{RAW}/fntic_{v["file"]}', 'rb').read()).hexdigest()
ds = json.load(open(f'{S}/an/mm/district_stats.json'))['maui_county']['areas']
md = {}
for typ, key in (('house', 'single_family_ytd'), ('condo', 'condo_total_ytd')):
    md[typ] = {a: dict(n26=r['ytd_units_2026'], n25=r['ytd_units_2025'], med26=r['ytd_median_2026'], med25=r['ytd_median_2025'])
               for a, r in ds[key].items()}
    md[typ]['TOTAL'] = md[typ].pop('All MLS')
res['Maui County'] = {'period': 'Jan–Sep 2026 vs Jan–Sep 2025', 'source': 'REALTORS Association of Maui, September 2026 report (data as of Oct 1, 2026)',
                      'url': 'https://www.ramaui.com/housing-statistics', 'data': md}
json.dump(res, open(f'{S}/an/mm/district_ytd.json', 'w'), indent=1, ensure_ascii=False)
for k, v in res.items():
    print(k, {t: (v['data'][t]['TOTAL']['n26'], v['data'][t]['TOTAL']['n25'], v['data'][t]['TOTAL']['med26']) for t in ('house', 'condo')})
