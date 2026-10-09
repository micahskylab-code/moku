import csv, sys, json
D, OUT = sys.argv[1], sys.argv[2]
YEARS = ['1415','1516','1617','1718','1819','1920','2021','2122','2223']
HI = {'001':'Hawaii Island','003':'Oahu','007':'Kauai','009':'Maui'}
METRO = {
 'Los Angeles–Orange County': ['06037','06059'],
 'San Diego': ['06073'],
 'SF Bay Area & San Jose': ['06075','06001','06013','06081','06041','06085'],
 'Seattle–Tacoma': ['53033','53053','53061'],
 'Las Vegas': ['32003'],
 'Phoenix': ['04013','04021'],
 'Inland Empire': ['06065','06071'],
 'Portland': ['41051','41067','41005','53011'],
 'Sacramento': ['06067','06061','06113','06017'],
 'Denver–Boulder': ['08031','08005','08059','08001','08035','08014','08013'],
 'Salt Lake City': ['49035'],
 'Anchorage': ['02020'],
 'Washington DC area': ['11001','51059','51013','51153','51107','24031','24033','51510'],
 'Texas metros (Dallas, Houston, Austin, San Antonio)': ['48113','48085','48439','48201','48453','48491','48029'],
 'Chicago': ['17031'],
 'New York City': ['36061','36047','36081','36005','36085'],
}
MIL = {'53053':'Joint Base Lewis-McChord','48029':'JB San Antonio','08041':'Fort Carson','48141':'Fort Bliss','48027':'Fort Cavazos','37051':'Fort Liberty','24003':'Fort Meade','36045':'Fort Drum','12033':'NAS Pensacola','37133':'Camp Lejeune','06073':'Navy San Diego','51710':'Naval Station Norfolk','51810':'NAS Oceana','53035':'Naval Base Kitsap','13215':'Fort Moore','21047':'Fort Campbell'}
fmap = {v: k for k, vs in METRO.items() for v in vs}
res = {}
for yr in YEARS:
    rows = list(csv.DictReader(open(f'{D}/countyinflow{yr}.csv', encoding='latin-1')))
    yrkey = f'20{yr[:2]}-{yr[2:]}'
    res[yrkey] = {}
    for c, isl in HI.items():
        tot = None; other = None; named = []
        for r in rows:
            r = {k.lower().strip(): (v or '').strip() for k, v in r.items()}
            if r['y2_statefips'].zfill(2) != '15' or r['y2_countyfips'].zfill(3) != c: continue
            s = r['y1_statefips'].zfill(2); f = s + r['y1_countyfips'].zfill(3)
            n1, n2, agi = int(r['n1']), int(r['n2']), int(r['agi'])
            if 'Total Migration-Different State' in r['y1_countyname']: tot = (n1, n2, agi)
            elif 'Other flows - Different State' in r['y1_countyname']: other = (n1, n2, agi)
            elif s.isdigit() and int(s) <= 56 and s != '15' and n1 > 0:
                named.append(dict(fips=f, name=r['y1_countyname'], st=r['y1_state'], n1=n1, n2=n2, agi=agi))
        named.sort(key=lambda x: -x['n1'])
        met = {}
        for x in named:
            m = fmap.get(x['fips'])
            if m:
                a = met.setdefault(m, [0, 0, 0]); a[0] += x['n1']; a[1] += x['n2']; a[2] += x['agi']
        res[yrkey][isl] = dict(diff_state=tot, other_flows=other, named_returns=sum(x['n1'] for x in named),
            top=[[x['name'], x['st'], x['n1'], x['n2'], x['agi'], MIL.get(x['fips'], '')] for x in named[:25]],
            metros={k: v for k, v in sorted(met.items(), key=lambda kv: -kv[1][0])})
json.dump(res, open(OUT, 'w'), indent=1)
for yrkey, isl in res.items():
    print(f'\n##### {yrkey}')
    for name, d in isl.items():
        t = d['diff_state']
        print(f" {name}: from other states {t[0]:,} households / {t[1]:,} people / ${t[2]/1000:,.0f}M AGI (${t[2]/t[0]:.0f}K avg); named counties cover {100*d['named_returns']/t[0]:.0f}%")
        print('   top: ' + '; '.join(f"{x[0].replace(' County','')} {x[1]} {x[2]}" for x in d['top'][:8]))
