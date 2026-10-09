import xlrd, openpyxl, json, glob, os
S='/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad/irsold/'
files=sorted(glob.glob(S+'[12][0-9][0-9][0-9]hi.xls*'))
out={}
def rows(f,sheet_kw):
    if f.endswith('.xlsx'):
        wb=openpyxl.load_workbook(f,read_only=True,data_only=True)
        for sn in wb.sheetnames:
            if sheet_kw in sn.lower(): return [[('' if c is None else str(c)).strip() for c in r] for r in wb[sn].iter_rows(values_only=True)]
    else:
        b=xlrd.open_workbook(f)
        for sh in b.sheets():
            if sheet_kw in sh.name.lower(): return [[str(c.value).strip() for c in sh.row(i)] for i in range(sh.nrows)]
    return None
for f in files:
    yy=os.path.basename(f)[:4]; yr=f'20{yy[:2]}-{yy[2:]}'; out[yr]={}
    for kw,key in [('state outflow','out'),('state inflow','in')]:
        R=rows(f,kw)
        if R is None: print(yr,'no sheet',kw, [s for s in (xlrd.open_workbook(f).sheet_names() if f.endswith('.xls') else openpyxl.load_workbook(f,read_only=True).sheetnames)]); continue
        d={}
        for r in R:
            if len(r)<7: continue
            a=r[0].split('.')[0]; b=r[1].split('.')[0]
            if a!='15' or not b.isdigit(): continue
            st=int(b)
            if st>56 or st==15: continue
            try: n1=int(float(r[4])); n2=int(float(r[5])); agi=int(float(r[6]))
            except: continue
            if n1<0: continue
            d[r[2]]=(n1,n2,agi)
        out[yr][key]=d
json.dump(out,open('/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad/an/irs_states.json','w'))
for yr in out:
    o=out[yr].get('out',{}); i=out[yr].get('in',{})
    to=sorted(o.items(),key=lambda kv:-kv[1][0])[:8]; ti=sorted(i.items(),key=lambda kv:-kv[1][0])[:8]
    print(yr,'OUT sum',sum(v[0] for v in o.values()),' '.join(f'{k}{v[0]}' for k,v in to),'| IN sum',sum(v[0] for v in i.values()),' '.join(f'{k}{v[0]}' for k,v in ti))
