import json, csv, sys, statistics as st
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
mm = json.load(open(f'{S}/dl/appl2/macro_monthly.json'))['series']
CO = {'HONOLULU':'Oahu','MAUI':'Maui','KAUAI':'Kauai','HAWAII':'Hawaii Island'}
def ser(k, y0=2015):
    return {f"{r['year']}-{r['period'][1:]}": r['value'] for r in mm.get(k, []) if r['year'] >= y0}
M = {}
for c, isl in CO.items():
    M[isl] = dict(sf_sales=ser(f'DBEDT_SF_SALES_{c}'), condo_sales=ser(f'DBEDT_CONDO_SALES_{c}'),
                  sf_median=ser(f'DBEDT_SF_MEDIAN_{c}'), condo_median=ser(f'DBEDT_CONDO_MEDIAN_{c}'),
                  visitors=ser(f'HTA_VISITORS_{c}'), arr_dom=ser(f'DBEDT_ARRIVALS_DOM_{c}'), arr_intl=ser(f'DBEDT_ARRIVALS_INTL_{c}'))
M['Statewide'] = dict(arr_dom=ser('DBEDT_ARRIVALS_DOM_STATEWIDE'), arr_intl=ser('DBEDT_ARRIVALS_INTL_STATEWIDE'), visitors=ser('HTA_VISITORS_STATEWIDE'),
                      sf_sales=ser('DBEDT_SF_SALES_STATEWIDE'), condo_sales=ser('DBEDT_CONDO_SALES_STATEWIDE'))
MORT = ser('MORTGAGE30US')
# Realtor.com primary
FIPS = {'15003':'Oahu','15009':'Maui','15007':'Kauai','15001':'Hawaii Island'}
R = {v: {} for v in FIPS.values()}
for r in csv.DictReader(open(f'{S}/dl/rdc/rdc_county.csv')):
    f = r['county_fips'].zfill(5)
    if f in FIPS:
        m = r['month_date_yyyymm']; k = f'{m[:4]}-{m[4:]}'
        def g(x):
            try: return float(r[x])
            except: return None
        R[FIPS[f]][k] = dict(active=g('active_listing_count'), list_price=g('median_listing_price'), dom=g('median_days_on_market'),
                             new=g('new_listing_count'), cuts=g('price_reduced_share'), pending=g('pending_listing_count'))
for isl in R: M[isl]['rdc'] = R[isl]
TG = [r for r in csv.DictReader(open(f'{S}/dl/appl2/county_home_sales_tg_2015_2025.csv'))]
MAUI = [r for r in csv.DictReader(open(f'{S}/dl/appl2/maui_sales_totals_fy2016_2026.csv'))]
IRS = json.load(open(f'{S}/an/irs_decade.json'))
json.dump(dict(monthly=M, mortgage=MORT, tg=TG, maui_fy=MAUI, irs=IRS), open(f'{S}/an/dataset.json', 'w'))
# annual summaries
def yr(d, y, agg):
    v = [d[k] for k in d if k.startswith(f'{y}-') and d[k] is not None]
    return (agg(v), len(v)) if v else (None, 0)
print('Mortgage 30y annual avg:', {y: round(yr(MORT, y, st.mean)[0], 2) for y in range(2015, 2027)})
print('Last mortgage months:', {k: MORT[k] for k in sorted(MORT)[-6:]})
for isl in ['Oahu','Maui','Kauai','Hawaii Island']:
    d = M[isl]; print(f'\n== {isl}')
    for y in range(2015, 2027):
        sf = yr(d['sf_sales'], y, sum); co = yr(d['condo_sales'], y, sum)
        sfm = yr(d['sf_median'], y, st.median); com = yr(d['condo_median'], y, st.median)
        vi = yr(d['visitors'], y, sum)
        rd = {k: v for k, v in d['rdc'].items() if k.startswith(f'{y}-')}
        act = round(st.mean([v['active'] for v in rd.values() if v['active']])) if rd else None
        print(f" {y}: SF sales {sf[0]} ({sf[1]}m) med-of-monthly-medians {sfm[0]} | condo {co[0]} med {com[0]} | visitors {round(vi[0]) if vi[0] else None} ({vi[1]}m) | avg active listings {act}")
