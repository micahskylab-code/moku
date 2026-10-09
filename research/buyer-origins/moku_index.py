import json, numpy as np, datetime as dt
d=json.load(open('/home/user/moku/oahu-sales.json'))
Y0,Y1=2000,2025
def frac(s): t=dt.date.fromisoformat(s); return t.year
pairs=[]
for t,v in d.items():
    if len(v)!=2: continue
    (p2,d2),(p1,d1)=v
    y1,y2=frac(d1),frac(d2)
    if p1<50000 or p2<50000 or y1<Y0 or y2>Y1 or y2<=y1: continue
    r=p2/p1
    if not (0.25<r<8): continue
    pairs.append((t[1], t[-4:]!='0000', y1, y2, np.log(r)))
print('pairs',len(pairs))
yrs=list(range(Y0,Y1+1)); K=len(yrs)
def bmn(sel):
    rows=[p for p in pairs if sel(p)]
    if len(rows)<200: return None,len(rows)
    X=np.zeros((len(rows),K-1)); y=np.zeros(len(rows))
    for i,(z,c,a,b,lr) in enumerate(rows):
        if a>Y0: X[i,a-Y0-1]-=1
        X[i,b-Y0-1]+=1; y[i]=lr
    # first stage + Case-Shiller style weights (by holding period)
    beta=np.linalg.lstsq(X,y,rcond=None)[0]; e=y-X@beta
    hp=np.array([b-a for (_,_,a,b,_) in rows],float); g=np.polyfit(hp,e**2,1); w=1/np.clip(np.polyval(g,hp),1e-3,None)
    W=np.sqrt(w); beta=np.linalg.lstsq(X*W[:,None],y*W,rcond=None)[0]
    idx=np.exp(np.r_[0,beta]); idx=100*idx/idx[yrs.index(2015)]
    return [round(float(x),1) for x in idx],len(rows)
out={'years':yrs,'all':{},'zones':{}}
for name,sel in [('All homes',lambda p:True),('Houses',lambda p:not p[1]),('Condos',lambda p:p[1])]:
    ix,n=bmn(sel); out['all'][name]=dict(index=ix,n=n)
    print(name,n,dict(zip(yrs,ix)))
for z in '123456789':
    ix,n=bmn(lambda p,z=z:p[0]==z); out['zones'][z]=dict(index=ix,n=n)
    if ix: print('zone',z,n,'2006',ix[6],'2012',ix[12],'2019',ix[19],'2025',ix[25])
json.dump(out,open('/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad/an/moku_index.json','w'))
