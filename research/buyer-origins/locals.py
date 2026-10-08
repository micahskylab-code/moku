import pandas as pd, numpy as np, json, csv
S='/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
D=S+'/dl/appl3/'
h=pd.read_parquet(D+'psam_h15.parquet'); p=pd.read_parquet(D+'psam_p15.parquet')
AREA={100:'Maui + Kauaʻi',200:'Hawaiʻi Island'}; 
def area(x): return AREA.get(int(x),'Oʻahu')
h['area']=h.PUMA.map(area); p['area']=p.PUMA.map(area)
ST={1:'AL',2:'AK',4:'AZ',5:'AR',6:'CA',8:'CO',9:'CT',10:'DE',11:'DC',12:'FL',13:'GA',15:'HI',16:'ID',17:'IL',18:'IN',19:'IA',20:'KS',21:'KY',22:'LA',23:'ME',24:'MD',25:'MA',26:'MI',27:'MN',28:'MS',29:'MO',30:'MT',31:'NE',32:'NV',33:'NH',34:'NJ',35:'NM',36:'NY',37:'NC',38:'ND',39:'OH',40:'OK',41:'OR',42:'PA',44:'RI',45:'SC',46:'SD',47:'TN',48:'TX',49:'UT',50:'VT',51:'VA',53:'WA',54:'WV',55:'WI',56:'WY',72:'PR'}
out={}
# --- movers
p['MIGSP']=pd.to_numeric(p.MIGSP,errors='coerce'); p['MIG']=pd.to_numeric(p.MIG,errors='coerce')
dom=p[(p.MIG==3)&(p.MIGSP.notna())&(p.MIGSP!=15)&(p.MIGSP<=72)]
abroad=p[p.MIG==2]
tot=p.PWGTP.sum()
out['movers']=dict(total_pop=int(tot), from_states=int(dom.PWGTP.sum()), from_abroad=int(abroad.PWGTP.sum()),
   by_area={a:dict(from_states=int(g.PWGTP.sum()), pop=int(p[p.area==a].PWGTP.sum())) for a,g in dom.groupby('area')},
   top_states=[(ST.get(int(k),str(k)),int(v)) for k,v in dom.groupby('MIGSP').PWGTP.sum().sort_values(ascending=False).head(12).items()],
   sample_n=int(len(dom)))
mil=pd.to_numeric(dom.MIL,errors='coerce')
out['movers']['active_duty_share']=float(dom.PWGTP[mil==1].sum()/dom.PWGTP.sum())
age=pd.to_numeric(dom.AGEP); out['movers']['age_share']={'under 25':float(dom.PWGTP[age<25].sum()/dom.PWGTP.sum()),'25-44':float(dom.PWGTP[(age>=25)&(age<45)].sum()/dom.PWGTP.sum()),'45-64':float(dom.PWGTP[(age>=45)&(age<65)].sum()/dom.PWGTP.sum()),'65+':float(dom.PWGTP[age>=65].sum()/dom.PWGTP.sum())}
# households headed by a mover from another state
hh=h[(h.TYPEHUGQ==1)&(pd.to_numeric(h.NP)>0)].copy()
heads=p[pd.to_numeric(p.RELSHIPP)==20][['SERIALNO','MIG','MIGSP','MIL','AGEP']]
hh=hh.merge(heads,on='SERIALNO',how='left')
hh['inc']=pd.to_numeric(hh.HINCP,errors='coerce')*pd.to_numeric(hh.ADJINC)/1e6
hh['ten']=pd.to_numeric(hh.TEN)
def wmed(v,w):
    m=v.notna(); v=v[m].values; w=w[m].values; o=np.argsort(v); v=v[o]; w=w[o]; c=np.cumsum(w); return float(v[np.searchsorted(c,c[-1]/2)])
newhh=hh[(hh.MIG==3)&(hh.MIGSP!=15)&(hh.MIGSP<=72)]
oldhh=hh[(hh.MIG==1)]
out['households']=dict(
  new_from_states=int(newhh.WGTP.sum()), new_sample=int(len(newhh)),
  new_owner_share=float(newhh.WGTP[newhh.ten.isin([1,2])].sum()/newhh.WGTP.sum()),
  new_median_income=wmed(newhh.inc,newhh.WGTP), stayer_median_income=wmed(oldhh.inc,oldhh.WGTP), all_median_income=wmed(hh.inc,hh.WGTP),
  by_area={a:dict(n=int(g.WGTP.sum()), owner=float(g.WGTP[g.ten.isin([1,2])].sum()/g.WGTP.sum()), med_inc=wmed(g.inc,g.WGTP), sample=int(len(g))) for a,g in newhh.groupby('area')})
# --- vacancy
hu=h[h.TYPEHUGQ==1].copy(); hu['VACS']=pd.to_numeric(hu.VACS,errors='coerce')
VL={1:'For rent',2:'Rented, not yet occupied',3:'For sale',4:'Sold, not yet occupied',5:'Seasonal, recreational or occasional use',6:'Migrant workers',7:'Other vacant'}
vac={}
for a,g in list(hu.groupby('area'))+[('Statewide',hu)]:
    T=g.WGTP.sum(); v=g[g.VACS.notna()]
    vac[a]=dict(units=int(T), vacant=int(v.WGTP.sum()), seasonal=int(v.WGTP[v.VACS==5].sum()), by={VL[int(k)]:int(x) for k,x in v.groupby('VACS').WGTP.sum().items()})
out['vacancy']=vac
# --- cost burden
occ=hh.copy(); occ['grpip']=pd.to_numeric(occ.GRPIP,errors='coerce'); occ['ocpip']=pd.to_numeric(occ.OCPIP,errors='coerce')
cb={}
for a,g in list(occ.groupby('area'))+[('Statewide',occ)]:
    r=g[g.ten==3]; o=g[g.ten==1]
    cb[a]=dict(renter_burden=float(r.WGTP[r.grpip>=30].sum()/r.WGTP[r.grpip.notna()].sum()), renter_severe=float(r.WGTP[r.grpip>=50].sum()/r.WGTP[r.grpip.notna()].sum()),
               owner_mortgage_burden=float(o.WGTP[o.ocpip>=30].sum()/o.WGTP[o.ocpip.notna()].sum()), renters=int(r.WGTP.sum()), owners=int(g.WGTP[g.ten.isin([1,2])].sum()))
out['burden']=cb
# --- IRS outflows decade
HI={'001':'Hawaiʻi Island','003':'Oʻahu','007':'Kauaʻi','009':'Maui'}
irs_out={}
for yr in ['1415','1516','1617','1718','1819','1920','2021','2122','2223']:
    rows=list(csv.DictReader(open(f'{S}/irsout/countyoutflow{yr}.csv',encoding='latin-1')))
    k=f'20{yr[:2]}-{yr[2:]}'; irs_out[k]={}
    for c,isl in HI.items():
        tot=None; dest=[]
        for r in rows:
            r={a.lower().strip():(b or '').strip() for a,b in r.items()}
            if r['y1_statefips'].zfill(2)!='15' or r['y1_countyfips'].zfill(3)!=c: continue
            s=r['y2_statefips'].zfill(2); n1,n2,agi=int(r['n1']),int(r['n2']),int(r['agi'])
            if 'Total Migration-Different State' in r['y2_countyname']: tot=(n1,n2,agi)
            elif s.isdigit() and int(s)<=56 and s!='15' and n1>0: dest.append((r['y2_countyname'],r['y2_state'],n1,n2,agi))
        dest.sort(key=lambda x:-x[2]); irs_out[k][isl]=dict(diff_state=tot,top=dest[:12])
out['irs_out']=irs_out
json.dump(out,open(f'{S}/an/locals.json','w'),indent=1,ensure_ascii=False)
m=out['movers']; print('movers from states',m['from_states'],'of',m['total_pop'],f"({100*m['from_states']/m['total_pop']:.1f}%) abroad",m['from_abroad'],'sample',m['sample_n'])
print('by area',m['by_area']); print('top states',m['top_states']); print('active duty share',round(m['active_duty_share'],3),'ages',{k:round(v,3) for k,v in m['age_share'].items()})
print('households',{k:(round(v,3) if isinstance(v,float) else v) for k,v in out['households'].items() if k!='by_area'}); print(out['households']['by_area'])
for a,v in vac.items(): print('VAC',a,v['units'],'vacant',v['vacant'],f"{100*v['vacant']/v['units']:.1f}%",'seasonal',v['seasonal'],f"{100*v['seasonal']/v['units']:.1f}% of all units")
for a,v in cb.items(): print('BURDEN',a,{k:(round(x,3) if isinstance(x,float) else x) for k,x in v.items()})
