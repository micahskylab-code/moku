import json, math, statistics as st
S='/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
mm=json.load(open(f'{S}/dl/appl2/macro_monthly.json'))['series']
mo={}
for r in mm['MORTGAGE30US']: mo.setdefault(r['year'],[]).append(r['value'])
P=json.load(open(f'{S}/an/page_data.json'))
TG={r['year']:r for r in P['tg'] if r['county']=='State'}
def tcrit(df):
    T={7:2.365,8:2.306,9:2.262,10:2.228,11:2.201,12:2.179,13:2.160,14:2.145,15:2.131,16:2.120}
    return T[df]
def fit(Y,k):
    x=[st.mean(mo[y]) for y in Y]; yv=[math.log(TG[y][k]) for y in Y]
    n=len(x);mx=sum(x)/n;my=sum(yv)/n
    sxx=sum((a-mx)**2 for a in x);b=sum((a-mx)*(c-my) for a,c in zip(x,yv))/sxx;a=my-b*mx
    sse=sum((c-a-b*xx)**2 for xx,c in zip(x,yv));sst=sum((c-my)**2 for c in yv);s=math.sqrt(sse/(n-2))
    seb=s/math.sqrt(sxx); t=tcrit(n-2)
    pct=lambda v:100*(math.exp(v)-1)
    def pred(r):
        se=s*math.sqrt(1+1/n+(r-mx)**2/sxx); m=a+b*r
        return round(math.exp(m)),round(math.exp(m-t*se)),round(math.exp(m+t*se))
    return dict(eff=pct(b),lo=pct(b-t*seb),hi=pct(b+t*seb),r2=1-sse/sst,n=n,pred=pred)
for lab,Y in [('2015-2025 as published',list(range(2015,2026))),('2008-2025 as published',list(range(2008,2026))),('2012-2025',list(range(2012,2026)))]:
    print('==',lab, 'rates', [round(st.mean(mo[y]),2) for y in Y][:3])
    for k in ['n_total','n_local','n_mainland']:
        f=fit(Y,k); print(f"  {k:10s} {f['eff']:+.1f}% ({f['lo']:+.1f} to {f['hi']:+.1f}) R2={f['r2']:.2f}")
    f=fit(Y,'n_total'); print('  total pred', {r:f['pred'](r) for r in (6.0,6.5,6.7,7.0,7.5,8.0)})
