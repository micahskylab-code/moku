import csv, json, xlrd, glob, os, sys
S='/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
HI={'001':'Hawaii Island','003':'Oahu','007':'Kauai','009':'Maui'}
exec(open(f'{S}/an/irs_decade.py').read().split("fmap = ")[0].split("METRO = ")[1].join(["METRO = ",""]) if False else '')
METRO = {
 'Los Angeles–Orange County': ['06037','06059'], 'San Diego': ['06073'], 'SF Bay Area & San Jose': ['06075','06001','06013','06081','06041','06085'],
 'Seattle–Tacoma': ['53033','53053','53061'], 'Las Vegas': ['32003'], 'Phoenix': ['04013','04021'], 'Portland': ['41051','41067','41005','53011'],
 'Inland Empire': ['06065','06071'], 'Sacramento': ['06067','06061','06113','06017'], 'Denver–Boulder': ['08031','08005','08059','08001','08035','08014','08013'],
 'Salt Lake City': ['49035'], 'Anchorage': ['02020'], 'Washington DC area': ['11001','51059','51013','51153','51107','24031','24033','51510'],
 'Texas metros (Dallas, Houston, Austin, San Antonio)': ['48113','48085','48439','48201','48453','48491','48029'], 'Chicago': ['17031'], 'New York City': ['36061','36047','36081','36005','36085']}
fmap={v:k for k,vs in METRO.items() for v in vs}
def blank(): return dict(tot=None, named=[])
res={}
def add(yr, isl, direction, st, cty, name, abbr, n1, n2, agi, label):
    d=res.setdefault(yr,{}).setdefault(isl,{}).setdefault(direction,blank())
    if st=='97' and cty=='003':
        d['tot']=(n1,n2,agi)
    elif st.isdigit() and int(st)<=56 and st!='15' and n1>0 and cty!='000':
        d['named'].append((st+cty,name,abbr,n1,n2,agi))
# old xls 2004-05 .. 2010-11
for f in sorted(glob.glob(f'{S}/irsold/co*.xls')):
    b=os.path.basename(f); yy=b[2:6]; yr=f'20{yy[:2]}-{yy[2:]}'; direction='in' if ('i' in b[6:8].lower() and b.lower().index('i',6)<b.lower().find('.xls')) else 'out'
    direction = 'in' if b.lower().replace('hi','',1).startswith(f'co{yy}i') or b.lower().endswith('hii.xls') or b.lower().endswith('hi i.xls') else direction
    low=b.lower()
    direction = 'in' if (low.endswith('ii.xls') or low[6]=='i') else 'out'
    sh=xlrd.open_workbook(f).sheet_by_index(0)
    for i in range(sh.nrows):
        r=[str(c.value).strip() for c in sh.row(i)]
        if len(r)<9 or r[0].split('.')[0]!='15': continue
        hc=r[1].split('.')[0].zfill(3)
        if hc not in HI: continue
        try: n1=int(float(r[6])); n2=int(float(r[7])); agi=int(float(r[8]))
        except: continue
        st=r[2].split('.')[0].zfill(2); cty=r[3].split('.')[0].zfill(3)
        add(yr,HI[hc],direction,st,cty,r[5],r[4],n1,n2,agi,r[5])
# national csv 2011-12 .. 2022-23
for f in sorted(glob.glob(f'{S}/irs2/county*flow*.csv')+glob.glob(f'{S}/irsdec/countyinflow*.csv')+glob.glob(f'{S}/irsout/countyoutflow*.csv')):
    b=os.path.basename(f); direction='in' if 'inflow' in b else 'out'; yy=b[-8:-4]; yr=f'20{yy[:2]}-{yy[2:]}'
    for r in csv.DictReader(open(f,encoding='latin-1')):
        r={k.lower().strip():(v or '').strip() for k,v in r.items()}
        if direction=='in':
            if r['y2_statefips'].zfill(2)!='15': continue
            hc=r['y2_countyfips'].zfill(3); st=r['y1_statefips'].zfill(2); cty=r['y1_countyfips'].zfill(3); name=r['y1_countyname']; ab=r['y1_state']
        else:
            if r['y1_statefips'].zfill(2)!='15': continue
            hc=r['y1_countyfips'].zfill(3); st=r['y2_statefips'].zfill(2); cty=r['y2_countyfips'].zfill(3); name=r['y2_countyname']; ab=r['y2_state']
        if hc not in HI: continue
        lab=name.replace('Total Migration-Different State','Tot Diff St') if 'Total Migration-Different State' in name else name
        add(yr,HI[hc],direction,st,cty,name,ab,int(r['n1']),int(r['n2']),int(r['agi']),lab)
out={}
for yr in sorted(res):
    out[yr]={}
    for isl,dd in res[yr].items():
        o={}
        for direction,d in dd.items():
            nm=sorted(d['named'],key=lambda x:-x[3]); met={}
            for x in nm:
                m=fmap.get(x[0])
                if m: a=met.setdefault(m,[0,0,0]); a[0]+=x[3]; a[1]+=x[4]; a[2]+=x[5]
            o[direction]=dict(tot=d['tot'], top=[[x[1],x[2],x[3],x[4],x[5]] for x in nm[:15]], metros=met, named=sum(x[3] for x in nm))
        out[yr][isl]=o
json.dump(out,open(f'{S}/an/irs_20yr.json','w'),indent=0)
for yr in out:
    print(yr, ' | '.join(f"{isl[:4]} in {v.get('in',{}).get('tot')} out {v.get('out',{}).get('tot')}" for isl,v in out[yr].items()))
