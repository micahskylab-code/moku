import json, html
S='/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
B=json.load(open(f'{S}/an/brief_data.json')); IRS=B['irs']; SEA=B['season']
P=json.load(open(f'{S}/an/page_data.json'))
TG={r['county']:r for r in P['tg'] if r['year']==2025}
def dollar_share(r,k): return 100*r['n_'+k]*r['avg_'+k]/(r['n_total']*r['avg_total'])
NAME={'Oahu':'Oʻahu','Maui':'Maui','Kauai':'Kauaʻi','Hawaii Island':'Hawaiʻi Island'}
CTY={'Oahu':'Honolulu','Maui':'Maui','Kauai':'Kauai','Hawaii Island':'Hawaii'}
SHORT={'Texas metros (Dallas, Houston, Austin, San Antonio)':'Texas (4 metros combined)','SF Bay Area & San Jose':'SF Bay Area & San Jose','Los Angeles–Orange County':'Los Angeles–Orange County','Washington DC area':'Washington DC area'}
def sh(m): return SHORT.get(m,m)
ISL=['Oahu','Maui','Kauai','Hawaii Island']

# ---- market tiles (Realtor.com Sep 2026 + DBEDT; from the report's "now" cards)
MK={
 'Oahu':dict(mos='5.2',verdict='Balanced',vcls='bal',sub='Houses ~3 months: a seller\'s market. Condos favor buyers.',act='3,483',yoy='+6.4%',cut='14.3%',
   play='Price houses to the market. Condos are where buyers can negotiate.'),
 'Maui':dict(mos='9.6',verdict="Buyer's market",vcls='buy',sub='The deepest buyer\'s market, but tightening: 11.1 months a year earlier, and January–August sales up 10% (condos up 17%).',act='1,367',yoy='+5.2%',cut='12.5%',
   play='Prospect out-of-state condo owners, but never in ZIPs 96761, 96767 or 96790 (Lahaina and Kula). Price to sell.'),
 'Kauai':dict(mos='8.4',verdict="Buyer's market",vcls='buy',sub='Sales down sharply, condos most.',act='385',yoy='+8.1%',cut='15.2% (Aug)',
   play='Mainland buyers bring half the purchase dollars. Work Southern California.'),
 'Hawaii Island':dict(mos='6.5',verdict="Buyer's market",vcls='buy',sub='Fastest-rising inventory, highest share of price cuts.',act='1,365',yoy='+24.9%',cut='16.7%',
   play='Mainland buyers bring over half the purchase dollars. The highest-income newcomers come from the Bay Area.'),
}
tiles=''
for i in ISL:
    m=MK[i]; r=TG[CTY[i]]
    tiles+=f'''<div class="tile"><div class="tn">{NAME[i]}{'*' if i=='Maui' else ''}</div><div class="pill {m['vcls']}">{m['verdict']}</div>
<div class="big">{m['mos']}<span> months of supply (Aug)</span></div><p class="tsub">{m['sub']}</p>
<dl><dt>Active listings, Sep</dt><dd>{m['act']}</dd><dt>vs a year earlier</dt><dd>{m['yoy']}</dd><dt>With a price cut</dt><dd>{m['cut']}</dd><dt>Mainland share of 2025 purchase $</dt><dd>{dollar_share(r,'mainland'):.0f}%</dd></dl>
<p class="play">{m['play']}</p></div>'''

# ---- origin / destination tables
def rows(d, n=4):
    out=''
    for k in range(n):
        out+='<tr><td class="rk">'+str(k+1)+'</td>'
        for i in ISL:
            m,per,agi,yrs=IRS[i][d][k]
            out+=f'<td><b>{html.escape(sh(m))}</b><span class="mn">{per:,} a year · ${agi}K avg income</span></td>'
        out+='</tr>'
    return out
head='<tr><th></th>'+''.join(f'<th>{NAME[i]}</th>' for i in ISL)+'</tr>'
INS=json.load(open(f'{S}/an/irs_instate.json'))
YR=['2019-20','2020-21','2021-22','2022-23']
def instate_row():
    out='<tr class="hl"><td class="rk">★</td>'
    for i in ISL:
        ss=[INS[y][i]['same state total'] for y in YR]; n=sum(x[0] for x in ss)/4; agi=sum(x[1] for x in ss)/sum(x[0] for x in ss)
        sub='mostly from Oʻahu' if i!='Oahu' else 'mostly the Big Island and Maui'
        out+=f'<td><b>Elsewhere in Hawaiʻi</b><span class="mn">{round(n):,} a year · ${round(agi)}K avg income · {sub}</span></td>'
    return out+'</tr>'
V=json.load(open(f'{S}/an/vis_cbsa.json'))['islands']
VJ_M=json.load(open(f'{S}/an/vis_cbsa.json'))['metros']
VK={'Oahu':'Oahu','Maui':'Maui','Kauai':'Kauai','Hawaii Island':'Hawaii'}
MN_={'Los Angeles-Long Beach-Anaheim CA':'Los Angeles–OC','San Francisco-Oakland-Hayward CA':'SF–Oakland','Seattle-Tacoma-Bellevue WA':'Seattle','San Diego-Carlsbad CA':'San Diego','Washington-Arlington-Alexandria DC-VA-MD-WV':'Washington DC','Baltimore-Columbia-Towson MD':'Baltimore','San Antonio-New Braunfels TX':'San Antonio','Minneapolis-St. Paul-Bloomington MN-WI':'Minneapolis–St. Paul','Chicago-Naperville-Elgin IL-IN-WI':'Chicago','Dallas-Fort Worth-Arlington TX':'Dallas–Fort Worth','Denver-Aurora-Lakewood CO':'Denver','Anchorage AK':'Anchorage','Portland-Vancouver-Hillsboro OR-WA':'Portland','New York-Newark-Jersey City NY-NJ-PA':'New York','Salt Lake City–Provo–Ogden UT':'Salt Lake City–Provo–Ogden'}
def mshort(m):
    return MN_.get(m, m.rsplit(' ',1)[0].split('-')[0])
def overrow(minn):
    out=''
    for k in range(3):
        out+='<tr><td class="rk">'+str(k+1)+'</td>'
        for i in ISL:
            lst=[d for d in V[VK[i]]['over'] if d['n']>=minn[i]]
            d=lst[k]
            out+=f'<td><b>{html.escape(mshort(d["metro"]))}</b><span class="mn">{d["idx"]:.2f}× the average · {round(d["n"]/1000):,}K visitors</span></td>'
        out+='</tr>'
    return out

# ---- calendar heat
MN=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
def cell(f):
    a=max(0,min(1,(f-0.85)/0.35)); pct=round(6+44*a)
    fr=round(f,2); strong=' s' if fr>=1.05 else (' w' if fr<0.95 else '')
    return f'<td class="hc{strong}" style="background:color-mix(in srgb,var(--accent) {pct}%,transparent)">{f:.2f}</td>'
cal=''
for lab,k in [('Closings · Oʻahu','Oahu'),('Closings · Maui','Maui'),('Closings · Kauaʻi','Kauai'),('Closings · Hawaiʻi Island','Hawaii Island'),('Arrivals · domestic flights','arr_dom'),('Arrivals · international flights','arr_intl')]:
    cal+=f'<tr><th class="rl">{lab}</th>'+''.join(cell(f) for f in SEA[k])+'</tr>'

st=TG['State']; ho=TG['Honolulu']
local_d=dollar_share(st,'local'); local_ho=dollar_share(ho,'local')
for_n=st['n_foreign']; for_pct=100*st['n_foreign']/st['n_total']

TGC={'Oahu':'Honolulu','Maui':'Maui','Kauai':'Kauai','Hawaii Island':'Hawaii'}
TGJ=json.load(open(f'{S}/an/new/tg.json'))
TGE={(e['period'][:4]+('H1' if 'Jun' in e['period'] else ''),e['geography'].split(' (')[0]):e for e in TGJ['editions']}
GEO={'Oahu':'Oahu','Maui':'Maui County','Kauai':'Kauai','Hawaii Island':'Hawaii Island'}
SNM={'CA':'California','WA':'Washington','TX':'Texas','FL':'Florida','CO':'Colorado','NV':'Nevada','OR':'Oregon','AK':'Alaska','UT':'Utah','NY':'New York','AZ':'Arizona','IL':'Illinois','WY':'Wyoming'}
def nxt(per,i,k,skip_ca=True):
    st=[x for x in TGE[(per,GEO[i])]['states'] if x['state']!='HI' and not (skip_ca and x['state']=='CA')][:k]
    return ', '.join(f"{SNM.get(x['state'],x['state'])} {x['count']}" for x in st)
def ca(per,i): return [x for x in TGE[(per,GEO[i])]['states'] if x['state']=='CA'][0]['count']
def pc(x):
    return '<1%' if 0<x<0.5 else f'{x:.0f}%'
def buyrows():
    out='<tr><td class="rk"></td>'
    for i in ISL:
        r=TG[TGC[i]]; n=r['n_total']
        out+=f"<td><b>{pc(100*r['n_local']/n)} local · {pc(100*r['n_mainland']/n)} mainland · {pc(100*r['n_foreign']/n)} foreign</b><span class=\"mn\">{n:,} buyers in 2025</span></td>"
    out+='</tr><tr><td class="rk"></td>'
    for i in ISL: out+=f'<td><b>California {ca("2025",i)}</b><span class="mn">#1 out-of-state buyer state, 2025</span></td>'
    out+='</tr><tr><td class="rk"></td>'
    for i in ISL: out+=f'<td><b>Next buyer states, 2025</b><span class="mn">{nxt("2025",i,4)}</span></td>'
    out+='</tr><tr><td class="rk"></td>'
    for i in ISL: out+=f'<td><b>2026 so far (Jan–Jun)</b><span class="mn">California {ca("2026H1",i)}, {nxt("2026H1",i,2)}</span></td>'
    out+='</tr><tr><td class="rk"></td>'
    for i in ISL:
        top=sorted(VJ_M,key=lambda r:-r[VK[i]])[:4]
        out+='<td><b>Biggest visitor metros</b><span class="mn">'+' · '.join(f'{html.escape(mshort(r["metro"]))} {round(r[VK[i]]/1000):,}K' for r in top)+'</span></td>'
    return out+'</tr>'
tpl=open(f'{S}/brief/brief.tpl.html').read()
out=(tpl.replace('{{TILES}}',tiles).replace('{{HEAD}}',head).replace('{{BUY}}',buyrows()).replace('{{OVER}}',overrow({'Oahu':20000,'Maui':20000,'Kauai':10000,'Hawaii Island':15000})).replace('{{OUT}}',rows('out'))
     .replace('{{CALHEAD}}',''.join(f'<th>{m}</th>' for m in MN)).replace('{{CAL}}',cal)
     .replace('{{LOCAL_D}}',f'{local_d:.0f}').replace('{{LOCAL_HO}}',f'{local_ho:.0f}').replace('{{FOR_N}}',f'{for_n:,}').replace('{{FOR_PCT}}',f'{for_pct:.1f}'))
assert '{{' not in out
open(f'{S}/broker-brief.html','w').write(out)
print('ok', len(out), local_d, local_ho, for_n, for_pct)
