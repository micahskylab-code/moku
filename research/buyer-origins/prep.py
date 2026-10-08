import json, sys
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
d = json.load(open(f'{S}/an/dataset.json'))
mm = json.load(open(f'{S}/dl/appl2/macro_monthly.json'))['series']
def months(y0=2015, m0=1, y1=2026, m1=12):
    out = []; y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f'{y}-{m:02d}'); m += 1
        if m == 13: y, m = y + 1, 1
    return out
MON = months(2015, 1, 2026, 10)
isl = ['Oahu', 'Maui', 'Kauai', 'Hawaii Island']
def arr(series): return [series.get(k) for k in MON]
P = {'months': MON, 'mortgage': [round(x, 2) if x else None for x in arr(d['mortgage'])]}
P['islands'] = {}
for i in isl:
    m = d['monthly'][i]
    r = m['rdc']
    P['islands'][i] = dict(sf_sales=arr(m['sf_sales']), condo_sales=arr(m['condo_sales']), sf_median=arr(m['sf_median']), condo_median=arr(m['condo_median']),
        active=[(r.get(k) or {}).get('active') for k in MON], dom=[(r.get(k) or {}).get('dom') for k in MON], cuts=[(r.get(k) or {}).get('cuts') for k in MON])
def s(k): return {f"{x['year']}-{x['period'][1:]}": x['value'] for x in mm[k] if x['year'] >= 2015}
P['arr_dom'] = arr(s('DBEDT_ARRIVALS_DOM_STATEWIDE')); P['arr_intl'] = arr(s('DBEDT_ARRIVALS_INTL_STATEWIDE'))
P['tg'] = [{k: (int(v) if k not in ('county',) else v) for k, v in r.items()} for r in d['tg']]
P['maui_fy'] = [{k: (int(v) if k != 'category' else v) for k, v in r.items() if k != 'sum_tax_recorded'} for r in d['maui_fy'] if r['category'] in ('owner', 'nonowner')]
METROS = ['Los Angeles–Orange County','San Diego','SF Bay Area & San Jose','Seattle–Tacoma','Las Vegas','Phoenix','Portland','Inland Empire','Denver–Boulder','Sacramento','Salt Lake City','Anchorage','Texas metros (Dallas, Houston, Austin, San Antonio)','Washington DC area','Chicago','New York City']
irs = {}
for yr, by in d['irs'].items():
    irs[yr] = {}
    for i, v in by.items():
        t = v['diff_state']
        irs[yr][i] = dict(households=t[0], people=t[1], agi=t[2], metros={m: v['metros'].get(m, [0, 0, 0]) for m in METROS},
                          top=[x[:5] for x in v['top'][:12]], named=v['named_returns'])
P['irs'] = irs; P['metros'] = METROS
json.dump(P, open(f'{S}/an/page_data.json', 'w'), separators=(',', ':'))
print(len(json.dumps(P, separators=(',', ':'))) // 1024, 'KB')
# key derived stats for copy
tg = {(r['county'], int(r['year'])): r for r in d['tg']}
for y in range(2015, 2026):
    r = tg[('State', y)]; n = int(r['n_total'])
    print(y, n, 'mainland', r['n_mainland'], f"{100*int(r['n_mainland'])/n:.1f}%", 'foreign', r['n_foreign'], f"{100*int(r['n_foreign'])/n:.1f}%", 'avg main', r['avg_mainland'])
for c in ['Honolulu', 'Maui', 'Kauai', 'Hawaii']:
    print(c, [f"{y}:{100*int(tg[(c,y)]['n_mainland'])/int(tg[(c,y)]['n_total']):.0f}%" for y in range(2015, 2026)])
for r in d['maui_fy']:
    pass
mf = {}
for r in d['maui_fy']: mf.setdefault(r['fy'], {})[r['category']] = (int(r['count']), int(r['sum_price']))
for fy, v in sorted(mf.items()):
    o, n = v['owner'], v['nonowner']
    print('Maui FY', fy, f"nonowner {n[0]} of {o[0]+n[0]} = {100*n[0]/(o[0]+n[0]):.1f}% count; value {100*n[1]/(o[1]+n[1]):.1f}%")
