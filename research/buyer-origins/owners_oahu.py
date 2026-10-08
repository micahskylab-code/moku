import json,glob,re,collections,sys
S=sys.argv[1]
# Approximate ZIP3 (USPS sectional center) -> metro. Coarse; CSA-like groupings. Unlisted -> "Other <state>".
Z3 = {}
def zr(a, b, name):
    for i in range(a, b + 1): Z3["%03d" % i] = name
zr(900, 918, "Los Angeles-Long Beach-Anaheim CA"); zr(926, 928, "Los Angeles-Long Beach-Anaheim CA")
zr(919, 921, "San Diego CA"); zr(922, 925, "Riverside-San Bernardino CA (Inland Empire)")
zr(930, 930, "Oxnard-Ventura CA"); zr(931, 931, "Santa Barbara CA"); zr(932, 933, "Bakersfield CA")
zr(934, 934, "Santa Barbara/San Luis Obispo CA"); zr(935, 935, "Lancaster-Mojave CA"); zr(936, 938, "Fresno CA")
zr(939, 939, "Salinas-Monterey CA"); zr(940, 941, "San Francisco Bay Area CA"); zr(943, 951, "San Francisco Bay Area CA")
zr(954, 954, "San Francisco Bay Area CA"); zr(942, 942, "Sacramento CA"); zr(956, 958, "Sacramento CA")
zr(952, 953, "Stockton-Modesto CA"); zr(955, 955, "Eureka CA"); zr(959, 959, "Chico-Marysville CA"); zr(960, 960, "Redding CA")
zr(961, 961, "Reno-Tahoe NV/CA"); zr(894, 895, "Reno-Tahoe NV/CA"); zr(897, 897, "Reno-Tahoe NV/CA")
zr(889, 891, "Las Vegas NV")
zr(980, 984, "Seattle-Tacoma WA"); zr(985, 985, "Olympia WA"); zr(986, 986, "Portland OR-WA"); zr(970, 972, "Portland OR-WA")
zr(990, 992, "Spokane WA"); zr(993, 993, "Kennewick-Richland WA"); zr(988, 989, "Central Washington WA")
zr(973, 973, "Salem OR"); zr(974, 974, "Eugene OR"); zr(975, 975, "Medford OR"); zr(977, 977, "Bend OR")
zr(850, 853, "Phoenix AZ"); zr(856, 857, "Tucson AZ"); zr(863, 863, "Prescott AZ"); zr(860, 860, "Flagstaff AZ")
zr(840, 841, "Salt Lake City UT"); zr(843, 844, "Ogden UT"); zr(846, 847, "Provo-Orem UT"); zr(837, 837, "Boise ID"); zr(836, 836, "Boise ID")
zr(800, 806, "Denver-Boulder CO"); zr(808, 809, "Colorado Springs CO"); zr(805, 805, "Denver-Boulder CO")
zr(750, 754, "Dallas-Fort Worth TX"); zr(760, 762, "Dallas-Fort Worth TX"); zr(770, 775, "Houston TX")
zr(780, 782, "San Antonio TX"); zr(786, 787, "Austin TX"); zr(765, 765, "Killeen-Temple TX"); zr(798, 799, "El Paso TX")
zr(100, 104, "New York City NY-NJ"); zr(105, 119, "New York City NY-NJ"); zr(70, 79, "New York City NY-NJ")
zr(87, 89, "New York City NY-NJ"); zr(68, 69, "New York City NY-NJ (CT suburbs)"); zr(64, 65, "New Haven CT"); zr(60, 61, "Hartford CT")
zr(80, 81, "Philadelphia PA-NJ"); zr(189, 191, "Philadelphia PA-NJ"); zr(193, 194, "Philadelphia PA-NJ")
zr(17, 24, "Boston MA"); zr(14, 16, "Worcester MA"); zr(28, 29, "Providence RI")
zr(200, 200, "Washington DC-MD-VA"); zr(202, 209, "Washington DC-MD-VA"); zr(220, 223, "Washington DC-MD-VA"); zr(569, 569, "Washington DC-MD-VA")
zr(210, 212, "Baltimore MD"); zr(214, 214, "Baltimore MD"); zr(217, 217, "Washington DC-MD-VA"); zr(224, 225, "Washington DC-MD-VA")
zr(230, 232, "Richmond VA"); zr(233, 237, "Virginia Beach-Norfolk VA")
zr(600, 608, "Chicago IL"); zr(300, 303, "Atlanta GA"); zr(311, 311, "Atlanta GA"); zr(399, 399, "Atlanta GA")
zr(330, 334, "Miami-Fort Lauderdale-West Palm Beach FL"); zr(335, 337, "Tampa-St. Petersburg FL"); zr(346, 346, "Tampa-St. Petersburg FL")
zr(327, 328, "Orlando FL"); zr(347, 347, "Orlando FL"); zr(320, 320, "Jacksonville FL"); zr(322, 322, "Jacksonville FL")
zr(339, 339, "Fort Myers FL"); zr(341, 341, "Naples FL"); zr(342, 342, "Sarasota FL"); zr(325, 325, "Pensacola FL")
zr(550, 551, "Minneapolis-St. Paul MN"); zr(553, 555, "Minneapolis-St. Paul MN")
zr(630, 631, "St. Louis MO-IL"); zr(620, 620, "St. Louis MO-IL"); zr(622, 622, "St. Louis MO-IL")
zr(640, 641, "Kansas City MO-KS"); zr(660, 662, "Kansas City MO-KS")
zr(480, 483, "Detroit MI"); zr(430, 432, "Columbus OH"); zr(440, 441, "Cleveland OH"); zr(450, 452, "Cincinnati OH")
zr(150, 152, "Pittsburgh PA"); zr(275, 277, "Raleigh-Durham NC"); zr(280, 282, "Charlotte NC"); zr(370, 372, "Nashville TN")
zr(380, 381, "Memphis TN"); zr(995, 996, "Anchorage AK"); zr(997, 997, "Fairbanks AK"); zr(998, 999, "Juneau/Southeast AK")
zr(870, 871, "Albuquerque NM"); zr(875, 875, "Santa Fe NM"); zr(730, 731, "Oklahoma City OK"); zr(740, 741, "Tulsa OK")
zr(460, 462, "Indianapolis IN"); zr(530, 532, "Milwaukee WI"); zr(680, 681, "Omaha NE"); zr(700, 701, "New Orleans LA")
zr(400, 402, "Louisville KY"); zr(232, 232, "Richmond VA")

def zip3_metro(z, st):
    return Z3.get(z[:3], "Other %s (not mapped)" % st)
def load(d):
    out=[]
    for f in sorted(glob.glob(f'{S}/raw/owners_oahu/{d}/*.json')):
        out+= [x['attributes'] for x in json.load(open(f))['features']]
    return out
own=load('owninfo'); pit=load('asmtpitt'); leg=load('legdat_address')
cls={}
for r in pit:
    p=r['parid']
    if p not in cls or (r.get('seq') or 0)<cls[p][0]: cls[p]=(r.get('seq') or 0, str(r.get('taxratecode')))
situs={r['parid']:r.get('zip1') for r in leg}
prim={}
for r in own:
    p=r['parid']; s=r.get('ownseq') or 0
    if p not in prim or s<prim[p].get('ownseq',0): prim[p]=r
US=re.compile(r'\b([A-Z]{2})\s+(\d{5})(?:-?\d{4})?\s*$')
def parse(r):
    ls=[(r.get(k) or '').strip().upper() for k in ('address1','address2','address3')]
    ls=[l for l in ls if l and l!='NONE']
    if not ls: return None
    full=' | '.join(ls)
    m=US.search(ls[-1]) or (US.search(ls[-2]) if len(ls)>1 else None)
    if m:
        st,z=m.group(1),m.group(2)
        cat='hawaii' if st=='HI' else ('military' if st in ('AP','AE','AA') else ('territory' if st in ('GU','MP','AS','PR','VI','FM','MH','PW') else 'us'))
        return dict(full=re.sub(r'\s+',' ',full),cat=cat,st=st,zip=z)
    return dict(full=re.sub(r'\s+',' ',full),cat='foreign_or_other',st=None,zip=None)
rows=[]
for p,r in prim.items():
    if p.endswith('0000') and r.get('has_cpr')=='Y': continue   # condo master record
    a=parse(r)
    if a: a['parid']=p; a['res']=cls.get(p,(0,None))[1]=='1'; a['situs']=situs.get(p); rows.append(a)
addr_n=collections.Counter(a['full'] for a in rows)
for a in rows: a['inst']=addr_n[a['full']]>=10
res=[a for a in rows if a['res']]
def share(lst):
    c=collections.Counter(a['cat'] for a in lst); n=len(lst); return {k:round(v/n,4) for k,v in c.items()}, n
oos=[a for a in res if a['cat']=='us']
oos_ind=[a for a in oos if not a['inst']]
out=dict(residential_parcels_with_address=len(res), residential_shares=share(res)[0],
 residential_oos=len(oos), residential_oos_institutional=sum(a['inst'] for a in oos),
 residential_foreign=sum(a['cat']=='foreign_or_other' for a in res),
 inst_threshold='a mailing address shared by 10 or more Oahu parcels',
 top_inst_addresses_count=[n for _,n in addr_n.most_common(15)],
 metro_individual=collections.Counter(zip3_metro(a['zip'],a['st']) for a in oos_ind).most_common(25),
 metro_all=collections.Counter(zip3_metro(a['zip'],a['st']) for a in oos).most_common(25),
 states_individual=collections.Counter(a['st'] for a in oos_ind).most_common(15),
 top_zips_individual=[(z,n,zip3_metro(z,'')) for z,n in collections.Counter(a['zip'] for a in oos_ind).most_common(30)],
 inst_share_by_metro={m: round(sum(1 for a in oos if zip3_metro(a['zip'],a['st'])==m and a['inst'])/max(1,sum(1 for a in oos if zip3_metro(a['zip'],a['st'])==m)),3) for m,_ in collections.Counter(zip3_metro(a['zip'],a['st']) for a in oos).most_common(12)})
# situs ZIP shares (residential, individual-or-not)
bz=collections.defaultdict(lambda: collections.Counter())
for a in res:
    if a['situs']: bz[a['situs']][a['cat']]+=1; bz[a['situs']]['n']+=1
out['situs_zip']= {z:{'n':c['n'],'mainland':round(c['us']/c['n'],4),'foreign':round(c['foreign_or_other']/c['n'],4),'hawaii':round(c['hawaii']/c['n'],4)} for z,c in bz.items() if c['n']>=300}
json.dump(out,open(f'{S}/an/owners/oahu_individual.json','w'),indent=1)
print(json.dumps({k:v for k,v in out.items() if k!='situs_zip'},indent=0)[:5000])
