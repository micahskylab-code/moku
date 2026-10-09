import json, html, re
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
O = '<span class="tag o">Official</span>'; P = '<span class="tag p">Primary</span>'; R = '<span class="tag r">Reported</span>'
J = lambda p: json.load(open(f'{S}/{p}'))
rdc = J('an/mm/rdc_zip.json'); uh = J('an/new/uhero.json'); db = J('an/new/databook.json'); tg = J('an/new/tg.json')
hm = J('an/new/hmda.json'); hmt = J('an/who/hmda_tiers.json'); oj = J('an/who/oahu_join.json')['results']
mj = J('an/who/maui_join.json'); lux = J('an/mm/luxury.json'); own = J('an/owners/oahu_individual.json')
PD = J('an/page_data.json')

def pct(x, d=0): return f'{100*x:.{d}f}%'
def money(n):
    if n is None: return '—'
    return f'${n/1e6:.2f}M' if n >= 999500 else f'${round(n/1000):,}K'
def esc(s): return html.escape(str(s))

ISL = [('Oahu', 'Oʻahu', 'Honolulu', 'Oahu', '15003'), ('Maui County', 'Maui County', 'Maui', 'Maui County', '15009'),
       ('Kauai', 'Kauaʻi', 'Kauai', 'Kauai', '15007'), ('Hawaii Island', 'Hawaiʻi Island', 'Hawaii', 'Hawaii Island', '15001')]
TG = {(e['period'][:4] + ('H1' if 'Jun' in e['period'] else ''), e['geography'].split(' (')[0]): e for e in tg['editions']}
TGd = {(r['county'], r['year']): r for r in PD['tg']}
UC = {r['county']: r for r in uh['county_rows']}
UZ = {r['zip']: r for r in uh['zip_rows']}
HMC = hm['years']['2025']['counties']
HL = lux['hawaii_life']['by_period_island']
HLK = {'Oahu': 'Oahu', 'Maui County': 'Maui', 'Kauai': 'Kauai', 'Hawaii Island': 'Hawaii Island'}

# ---------- 1. island table
def sh3(x):
    return '<1%' if 0 < x < 0.005 else f'{100*x:.0f}%'
cols = []
for key, name, cty, tgk, fips in ISL:
    pub = rdc['rollups'][key]['latest']['REALTOR_PUBLISHED_aggregate']
    r = TGd[(cty, 2025)]; n = r['n_total']
    occ = HMC[fips]['occupancy_type']['shares']; u = UC[cty]; l25 = HL['2025'][HLK[key]]
    if key == 'Oahu':
        sh = own['residential_shares']; offv = pct(sh['us'] + sh['foreign_or_other'], 1)
    elif key == 'Maui County':
        stt = mj['results']['b_owner_origin_stock_and_inferred_acquirers']['stock_all_residential']['share']; offv = pct(stt['non_hawaii_total'], 1)
    else:
        offv = '<span class="why">county file not public</span>'
    cols.append(dict(name=name, rows=[
        f"{int(pub['active_listing_count']):,}", money(pub['median_listing_price']) + ('<sup>†</sup>' if pub.get('quality_flag') == 1 else ''), str(int(pub['median_days_on_market'])), ('15.2% (Aug)<sup>‡</sup>' if key == 'Kauai' else f"{int(pub['price_reduced_share']*1000+0.5+1e-9)/10:.1f}%"),
        f"{sh3(r['n_local']/n)} · {sh3(r['n_mainland']/n)} · {sh3(r['n_foreign']/n)}",
        f"{pct(u['out_of_state_share_sf'])} · {pct(u['out_of_state_share_condo'])}",
        pct(occ['second_residence'] + occ['investment_property']),
        f"{l25['all_3m']} · {l25['all_10m_plus']}", pct(u['str_share_of_housing'], 1), offv]))
LBL = ['Active listings, Sep 2026', 'Median list price', 'Median days on market', 'Listings with a price cut', 'Buyers 2025: local · mainland · foreign',
       'Out-of-state buyers 2025: houses · condos', 'Mortgaged buyers who won\'t live there (2025)', '$3M+ sales 2025 · of which $10M+', 'Vacation rentals, share of homes', 'Homes owned from outside Hawaiʻi (Oʻahu: off-island)']
gl = '<div class="tw"><table class="gl"><thead><tr><th></th>' + ''.join(f"<th class=\"num\">{c['name']}</th>" for c in cols) + '</tr></thead><tbody>'
for i, lb in enumerate(LBL):
    gl += f'<tr><td>{lb}</td>' + ''.join(f"<td class=\"num\">{c['rows'][i]}</td>" for c in cols) + '</tr>'
gl += '</tbody></table></div>'
# ---------- 2. tiers
tiers = [('entry_lt_750k', 'Entry, under $750K', 'entry_lt_800k_proxy', 'entry'), ('mid_750k_1.5m', 'Mid, $750K–1.5M', 'mid_800k_1_5m', 'mid'),
         ('upper_1.5m_3m', 'Upper, $1.5M–3M', 'upper_1_5m_3m', 'upper'), ('luxury_3m_10m', 'Luxury, $3M–10M', 'luxury_3m_10m', 'luxury'),
         ('ultra_10m_plus', 'Ultra, $10M+', 'ultra_10m_plus', 'ultra')]
ts = oj['headline']['tier_share']
mt = mj['results']['a_nonowner_share_by_tier_and_fy']
# find pooled FY2024-26 structure
def maui_tier(k):
    pl = mt['pooled']['FY2024-FY2026 (post-Lahaina-fire, recent 3 yrs)']
    return pl.get(k)
HT = hmt['by_year']['2025']['all_four_counties']
HT19 = hmt['by_year']['2019']['all_four_counties']
def hm_tier(D, t):
    return D['tiers'].get(t)
trows = ''
for k, lab, mk, hk in tiers:
    o = ts[k]; flag = ' <span class="why">(n&lt;20)</span>' if o['n'] < 20 else ''
    mv = maui_tier(mk)
    mtxt = '—'
    if mv:
        sh = mv.get('nonowner_share_of_sales')
        nn = mv.get('residential_sales')
        if sh is not None: mtxt = f"{pct(sh)}<br><span class=\"why\">of {nn:,} sales</span>" if nn else pct(sh)
    h = hm_tier(HT, hk); h19 = hm_tier(HT19, hk)
    htxt = '—'
    if h and 'occupancy_share' in h:
        oc = h['occupancy_share']; oc19 = h19['occupancy_share'] if h19 else None
        inc = h['income_thousands_usd']['median']; incs = f"${inc/1000:.2f}M" if inc >= 1000 else f"${inc:.0f}K"
        small = ' (n&lt;20)' if h['n_loans'] < 20 else ''
        no = oc['second_home'] + oc['investment']
        htxt = (f"<b>{pct(no)}</b> won't live there ({pct(oc['second_home'])} second home, {pct(oc['investment'])} investor)<br><span class=\"why\">{h['n_loans']:,} loans{small}; median income {incs}"
                + (f"; 2019: {pct(oc19['second_home'] + oc19['investment'])} won't live there</span>" if oc19 else '</span>'))
    trows += f"<tr><td><b>{lab}</b></td><td class=\"num\">{100*o['hawaii_total']:.0f}% · {100*o['mainland_us']:.0f}% · {100*o['foreign']:.0f}%<br><span class=\"why\">{o['n']:,} sales{flag}</span></td><td class=\"num\">{mtxt}</td><td>{htxt}</td></tr>"

# ---------- 3. type
hv = oj['headline']['house_vs_condo_share']
st = mj['results']['b_owner_origin_stock_and_inferred_acquirers']
mtyp = st['stock_by_type']
yrows = ''
for key, name, cty, tgk, fips in ISL:
    r25 = TGd[(cty, 2025)]; r19 = TGd[(cty, 2019)]; u = UC[cty]
    yrows += (f"<tr><td><span class=\"geo\">{name}</span></td><td class=\"num\">{r25['n_sf']:,} · {money(r25['avg_sf'])}<br><span class=\"why\">2019: {r19['n_sf']:,} · {money(r19['avg_sf'])}</span></td>"
              f"<td class=\"num\">{r25['n_condo']:,} · {money(r25['avg_condo'])}<br><span class=\"why\">2019: {r19['n_condo']:,} · {money(r19['avg_condo'])}</span></td>"
              f"<td class=\"num\">{pct(u['out_of_state_share_sf'])}</td><td class=\"num\"><b>{pct(u['out_of_state_share_condo'])}</b></td></tr>")

# ---------- 4. luxury
lrows = ''
for key, name, cty, tgk, fips in ISL:
    a = HL['2025'][HLK[key]]; b = HL['H1_2026'][HLK[key]]
    lrows += (f"<tr><td><span class=\"geo\">{name}</span></td><td class=\"num\">{a['all_3m']}</td><td class=\"num\">{a['sf_3m']} · {a['condo_3m']} · {a['land_3m']}</td>"
              f"<td class=\"num\">{a['all_10m_plus']}</td><td class=\"num\">{money(a.get('sf_3m_median'))}</td><td class=\"num\">{b['all_3m']} · {b['all_10m_plus']}</td></tr>")
sw = lux['hawaii_life']['statewide_sums_our_arithmetic']
lrows += (f"<tr><td><b>All Hawaiʻi</b></td><td class=\"num\"><b>{sw['2025']['all_3m']}</b></td><td class=\"num\">{sw['2025']['sf_3m']} · {sw['2025']['condo_3m']} · {sw['2025']['land_3m']}</td>"
          f"<td class=\"num\"><b>{sw['2025']['all_10m_plus']}</b></td><td class=\"num\">—</td><td class=\"num\">{sw['H1_2026']['all_3m']} · {sw['H1_2026']['all_10m_plus']}</td></tr>")
lux3 = oj.get('by_price_tier', {})

# ---------- 4b. district buyer origin (Title Guaranty) and 4c. mortgaged buyers by county subdivision (HMDA)
TD = J('an/gap/tg_districts.json')['district_summary']
ISLN = {'Oahu': 'Oʻahu', 'Maui County': 'Maui County', 'Hawaii Island': 'Hawaiʻi Island', 'Kauai': 'Kauaʻi'}
TDN = {'Kau': 'Kaʻū', 'Lihue': 'Līhuʻe', 'Koloa': 'Kōloa', 'Hamakua': 'Hāmākua', 'Molokai': 'Molokaʻi', 'Lanai': 'Lānaʻi', 'Up Country': 'Upcountry'}
drows = ''
for isl in ['Oahu', 'Maui County', 'Hawaii Island', 'Kauai']:
    rr = sorted([r for r in TD if r['island'].split(' (')[0] == isl], key=lambda r: -r['2025FY']['other_us_pct'])
    drows += f'<tr class="grp"><td colspan="5"><b>{ISLN[isl]}</b></td></tr>'
    for r in rr:
        a = r['2025FY']; b = r.get('2026H1') or {}
        sm = ' <span class="why">(under 20 sales)</span>' if a['total_lt20'] else ''
        bar = f'<span class="mbar"><i style="width:{a["other_us_pct"]:.0f}%"></i></span>'
        drows += (f'<tr><td>{esc(TDN.get(r["district"], r["district"]))}{sm}</td><td class="num">{a["total_sales"]:,}</td>'
                  f'<td class="num">{a["hawaii_pct"]:.0f}% · <b>{a["other_us_pct"]:.0f}%</b> · {a["foreign_pct"]:.0f}%</td><td>{bar}</td>'
                  f'<td class="num">{(str(round(b["other_us_pct"])) + "%") if b.get("other_us_pct") is not None else "—"}<br><span class="why">{b.get("total_sales", 0):,} sales</span></td></tr>')
HC = J('an/gap/hmda_tract.json')['data']
C25 = HC['years']['2025']['by_ccd']; CCH = HC['ccd_change_2019_2025']
crows = ''
for isl in ['Oahu', 'Maui County', 'Hawaii Island', 'Kauai']:
    isk = {'Maui County': 'Maui'}.get(isl, isl)
    rr = [(k, v) for k, v in C25.items() if v['island'] in (isl, isk, 'Maui', 'Molokai', 'Lanai') and (v['island'] == isl or (isl == 'Maui County' and v['island'] in ('Maui', 'Maui County', 'Molokai', 'Lanai'))) and not v['low_n_flag']]
    rr.sort(key=lambda kv: -kv[1]['share_second_plus_investment'])
    if not rr: continue
    crows += f'<tr class="grp"><td colspan="6"><b>{ISLN[isl]}</b></td></tr>'
    for k, v in rr:
        c = CCH.get(k, {}); o19 = c.get('share_second_plus_investment_2019')
        inc = v.get('median_income_k'); incs = '—' if inc is None else (f'${inc/1000:.2f}M' if inc >= 1000 else f'${inc:.0f}K')
        crows += (f'<tr><td>{esc(v["ccd_name"].replace(" CCD", ""))}</td><td class="num">{v["n_loans"]:,}</td>'
                  f'<td class="num"><b>{pct(v["share_second_plus_investment"])}</b>' + (f' <span class="why">2019: {pct(o19)}</span>' if o19 is not None and not c.get('low_n_flag') else '') + '</td>'
                  f'<td class="num">{pct(v["share_va"])}</td><td class="num">{incs}</td><td class="num">{money(v.get("median_property_value"))}</td></tr>')
lowc = sorted(v['ccd_name'].replace(' CCD', '') for v in C25.values() if v['low_n_flag'])

# ---------- 5. ZIP tables
OZ = own['situs_zip']
def ziptable(key):
    rows = []
    for z in rdc['zips']:
        if z['island'] != key and not (key == 'Maui County' and z['island'] == 'Maui County'): continue
        L = z['months'].get('latest'); Y = z['months'].get('yoy')
        if not L or L.get('thin_lt10_active') or (L.get('active_listing_count') or 0) < 10: continue
        u = UZ.get(z['zip'], {})
        ch = None
        if Y and Y.get('median_listing_price') and L.get('median_listing_price'):
            ch = L['median_listing_price'] / Y['median_listing_price'] - 1
        oos = u.get('out_of_state_share'); oz = OZ.get(z['zip'])
        fl = '<sup>†</sup>' if L.get('quality_flag') == 1 else ''
        fire = ' <span class="why">fire area: no unsolicited offers</span>' if z['zip'] in ('96761', '96767', '96790') else ''
        rows.append((L['active_listing_count'], f"<tr><td><span class=\"geo\">{z['zip']}</span> {esc(z['place'])}{fl}{fire}</td><td class=\"num\">{L['active_listing_count']:,}</td>"
            f"<td class=\"num\">{money(L.get('median_listing_price'))}</td><td class=\"num\">{'—' if ch is None else ('0%' if abs(ch) < 0.005 else (('+' if ch>=0 else '−')+f'{abs(100*ch):.0f}%'))}</td>"
            f"<td class=\"num\">{int(L['median_days_on_market']) if L.get('median_days_on_market') else '—'}</td><td class=\"num\">{pct(L['price_reduced_share']) if L.get('price_reduced_share') is not None and key != 'Kauai' else '—'}</td>"
            f"<td class=\"num\">{money(u.get('median_sf_price')) if u.get('median_sf_price') else '—'}</td>"
            f"<td class=\"num\">{pct(oos) if oos is not None else '—'}</td>"
            + (f"<td class=\"num\">{pct(oz['mainland']+oz['foreign'])}</td>" if key == 'Oahu' else '') + "</tr>"))
    rows.sort(key=lambda x: -x[0])
    head = ("<tr><th>ZIP</th><th class=\"num\">Listings Sep 2026</th><th class=\"num\">Median list price</th><th class=\"num\">vs Sep 2025</th><th class=\"num\">Days on market</th><th class=\"num\">Price cuts</th><th class=\"num\">House median sale 2025</th><th class=\"num\">Out-of-state buyers 2025</th>"
            + ("<th class=\"num\">Owned from off-island</th>" if key == 'Oahu' else '') + "</tr>")
    return f'<div class="tw"><table class="zt"><thead>{head}</thead><tbody>{"".join(r for _, r in rows)}</tbody></table></div>', len(rows)

DY = J('an/mm/district_ytd.json')
DNAME = {"PUNA": "Puna", "SOUTH HILO": "South Hilo (Hilo town)", "NORTH HILO": "North Hilo", "HAMAKUA": "Hāmākua", "NORTH KOHALA": "North Kohala (Hāwī)",
         "SOUTH KOHALA": "South Kohala (Waikoloa, Mauna Lani, Mauna Kea)", "NORTH KONA": "North Kona (Kailua-Kona)", "SOUTH KONA": "South Kona", "KA'U": "Kaʻū",
         "WAIMEA": "Waimea (West Side)", "KOLOA": "Kōloa (Poʻipū, South Shore)", "LIHUE": "Līhuʻe", "KAWAIHAU": "Kawaihau (Kapaʻa, East Side)",
         "HANALEI": "Hanalei (North Shore, Princeville)", "Lanai": "Lānaʻi", "Molokai": "Molokaʻi"}
def chg(a, b, minn=None):
    if a is None or b in (None, 0): return '—'
    c = a / b - 1
    return '0%' if abs(c) < 0.005 else ('+' if c >= 0 else '−') + f'{abs(100*c):.0f}%'
SAY = {}
def dytd(key):
    D = DY[key]; h = D['data']['house']; c = D['data'].get('condo', {})
    names = [a for a in h if a != 'TOTAL']
    for a in c:
        if a != 'TOTAL' and a not in names: names.append(a)
    rows = []
    for a in names:
        H = h.get(a, {}); C = c.get(a, {})
        tot = (H.get('n26') or 0) + (C.get('n26') or 0) + (H.get('n25') or 0) + (C.get('n25') or 0)
        if tot == 0: continue
        def cell(X):
            n26, n25, m26, m25 = X.get('n26'), X.get('n25'), X.get('med26'), X.get('med25')
            if not n26 and not n25: return '<td class="num">—</td><td class="num">—</td>'
            small = (n26 or 0) < 10 or (n25 or 0) < 10
            nc = chg(n26 or 0, n25) if n25 else 'new'
            mc = '' if small or not m26 or not m25 else f' <span class="why">{chg(m26, m25)}</span>'
            return (f'<td class="num">{n26 or 0:,} <span class="why">{nc}</span></td>'
                    f'<td class="num">{money(m26) if m26 else "—"}{mc}{" <span class=\"why\">(few sales)</span>" if small and m26 else ""}</td>')
        rows.append(((H.get('n26') or 0) + (C.get('n26') or 0), f'<tr><td>{esc(DNAME.get(a, a))}</td>{cell(H)}{cell(C)}</tr>'))
    rows.sort(key=lambda x: -x[0])
    T = lambda X: (f'<td class="num"><b>{X["n26"]:,}</b> <span class="why">{chg(X["n26"], X["n25"])}</span></td>'
                   f'<td class="num"><b>{money(X["med26"])}</b> <span class="why">{chg(X["med26"], X["med25"])}</span></td>')
    tot = f'<tr><td><b>Whole island</b></td>{T(h["TOTAL"])}{T(c["TOTAL"])}</tr>'
    head = ('<tr><th>District</th><th class="num">Houses sold</th><th class="num">House median</th>'
            '<th class="num">Condos sold</th><th class="num">Condo median</th></tr>')
    Hh, Cc = h['TOTAL'], c['TOTAL']
    g = lambda X, a: X[a]['med26'] / X[a]['med25'] - 1
    pc = lambda x: ('+' if x >= 0 else '−') + f'{abs(100*x):.0f}%'
    pa = lambda x: f'{abs(100*x):.0f}%'
    if key == 'Oahu':
        say = (f"House sales are up {pa(Hh['n26']/Hh['n25']-1)} and the median is up {pa(g(h,'TOTAL'))} to {money(Hh['med26'])}. "
               f"Condos are flat: sales {pc(Cc['n26']/Cc['n25']-1)}, median {money(Cc['med26'])}.")
    elif key == 'Maui County':
        say = (f"Buyers are back for condos, but at lower prices: condo sales are up {pa(Cc['n26']/Cc['n25']-1)} while the median fell {pa(g(c,'TOTAL'))} to {money(Cc['med26'])}. "
               f"Resort condos fell most: Wailea/Mākena {pc(g(c,'Wailea/Makena'))}, Kapalua {pc(g(c,'Kapalua'))}, Kīhei {pc(g(c,'Kihei'))}, Nāpili/Kahana {pc(g(c,'Napili/Kahana/Honokowai'))}.")
    elif key == 'Kauai':
        say = (f"Fewer sales (houses {pc(Hh['n26']/Hh['n25']-1)}, condos {pc(Cc['n26']/Cc['n25']-1)}), but the house median rose {pa(g(h,'TOTAL'))} to {money(Hh['med26'])}, "
               f"pulled up by Kōloa and Poʻipū ({pc(g(h,'KOLOA'))}). The mix shifted toward expensive homes.")
    else:
        say = (f"Sales are flat island-wide (houses {pc(Hh['n26']/Hh['n25']-1)}, median {money(Hh['med26'])}), but house dollar volume is up {pa(Hh['vol26']/Hh['vol25']-1)} "
               f"because the top end grew: South Kohala {pc(h['SOUTH KOHALA']['vol26']/h['SOUTH KOHALA']['vol25']-1)} and North Kona {pc(h['NORTH KONA']['vol26']/h['NORTH KONA']['vol25']-1)}.")
    SAY[key] = dict(period=D['period'].split(' vs ')[0], text=say)
    return (f'<h3 style="margin-top:28px">District scorecard, {D["period"].split(" vs ")[0]}</h3><p class="col" style="margin:0 0 12px">{say}</p>'
            f'<div class="tw"><table class="dy"><thead>{head}</thead><tbody>{"".join(r for _, r in rows)}{tot}</tbody></table></div>'
            f'<p class="src">{esc(D["source"])} {O}; district rows sum to the island totals. Grey figures are the change from the same months of 2025; median changes are left out where either year had fewer than 10 sales. MLS resales only, so totals differ from recorded-deed counts.</p>')

isl_secs = ''
NOTES = {
 'Oahu': ('Oʻahu by ZIP', 'Town condos sell to locals; Waikīkī, the North Shore and Turtle Bay sell to the mainland.'),
 'Maui County': ('Maui County by ZIP and district', 'West Maui and Wailea are owned from away; Upcountry and Central Maui are local.'),
 'Kauai': ('Kauaʻi by ZIP', 'The North Shore and Poʻipū are second-home markets; Līhuʻe and the West Side are local.'),
 'Hawaii Island': ('Hawaiʻi Island by ZIP', 'Kohala and Kona draw the mainland; Hilo and Puna are local and affordable.'),
}
for key, name, cty, tgk, fips in ISL:
    t, n = ziptable(key)
    extra = ''
    if key == 'Maui County':
        sd = st['stock_by_district']; ac = st['acquirers_by_district']; mv = st['median_assessed_value_by_district_residential']
        mrows = ''
        for dname, v in sd.items():
            a = ac.get(dname, {}); sh = v['share']
            ash = a.get('share', {}); an = a.get('classified', 0)
            mrows += (f"<tr><td>{esc(dname.split(' (')[0])}</td><td class=\"num\">{v['parcels']:,}</td><td class=\"num\">{pct(sh['us_mainland_and_dc'])}</td><td class=\"num\">{pct(sh['foreign'],1)}</td>"
                      f"<td class=\"num\"><b>{pct(sh['non_hawaii_total'])}</b></td><td class=\"num\">{(pct(ash.get('non_hawaii_total',0))+(' <span class=\"why\">(n&lt;20)</span>' if an<20 else '')) if an else '—'}</td><td class=\"num\">{money(mv.get(dname))}</td></tr>")
        extra = f'''<h3 style="margin-top:24px">Maui County districts: who owns, and who bought most recently</h3>
    <div class="tw"><table><thead><tr><th>District</th><th class="num">Residential parcels</th><th class="num">Owner on the mainland</th><th class="num">Owner abroad</th><th class="num">Owned from outside Hawaiʻi</th><th class="num">Recent buyers from outside Hawaiʻi</th><th class="num">Median assessed value</th></tr></thead><tbody>{mrows}</tbody></table></div>
    <p class="src">Maui County parcel fabric owner mailing addresses (Oct 4, 2026) and 2026 certified roll, computed here {P}. "Recent buyers" are parcels whose owner changed between the April 2026 roll and October 2026: an estimate of who is buying now, not recorded sales.</p>'''
    isl_secs += f'''
  <section id="mm-{key.split()[0].lower()}">
    <div class="head col"><span class="sec-n">{NOTES[key][0]}</span><h2>{NOTES[key][1]}</h2></div>
    {t}
    <p class="src">Listings: Realtor.com ZIP inventory, September 2026 vs September 2025, ZIPs with 10 or more active listings ({n} shown) {P}. † Realtor.com flags this ZIP's figures as lower quality for September 2026; treat the year-over-year change as rough.{' Price cuts are left blank for Kauaʻi because Realtor.com’s field is nearly empty there.' if key == 'Kauai' else ''} House median sale and out-of-state buyers: UHERO Hawaiʻi Housing Factbook 2026 (2025 sales; out-of-state = the buyer's deed address is outside Hawaiʻi) {O}.{(' Owned from off-island: Honolulu owner roll, residential parcels, October 2026 '+P+'.') if key=='Oahu' else ''}</p>
    {dytd(key)}
    {extra}
    <!--WHY:mm-{key.split()[0].lower()}-->
  </section>'''

chapter = f'''
  <div class="chapter" id="micro">
    <div class="ch"><span class="num">Chapter 3</span><h2 class="t">Micro-markets</h2><p>Every island by property type, price tier, district and ZIP: what sells, at what price, and who buys it.</p></div>
  <section id="mm-glance">
    <div class="head col"><span class="sec-n">All Hawaiʻi, island by island</span><h2>Four islands, four different markets</h2>
      <p class="muted">The latest listings (September 2026), who bought in 2025, and how much of each island is owned or bought from away.</p></div>
    {gl}
    <p class="src">Listings: Realtor.com county data, September 2026 {P}. † Realtor.com has flagged Maui County's data as lower quality every month since December 2025, so read its listing price with care. ‡ Kauaʻi's September price-cut share (4.8%) looks like a data gap in Realtor.com's file, so August's figure is shown. Buyers: DBEDT/Title Guaranty 2025 {O}. Out-of-state buyers by type and vacation-rental share: UHERO Hawaiʻi Housing Factbook 2026 {O}. Mortgaged buyers not living there: HMDA 2025 home-purchase loans, second-home plus investment occupancy {P}. $3M+ sales: Hawaiʻi Life luxury report 2025 {R}. Owner shares: county owner rolls, October 2026 {P}.</p>
    <!--WHY:mm-glance-->
  </section>
  <section id="mm-tiers">
    <div class="head col"><span class="sec-n">Who buys at each price</span><h2>Oʻahu buyers are mostly local up to $10 million. On Maui, buyers who won't live in the home take half or more at every price.</h2></div>
    <div class="tw"><table><thead><tr><th>Price tier</th><th class="num">Oʻahu buyers 2023–25<br>local · mainland · foreign</th><th class="num">Maui County: buyers without a homeowner exemption, FY2024–26</th><th>Statewide mortgaged buyers, 2025: second homes and investors</th></tr></thead><tbody>{trows}</tbody></table></div>
    <p class="src">Oʻahu: 2023–2025 sales matched to the October 2026 owner roll by the buyer's mailing address; excludes addresses shared by 10+ parcels; within about 1–4 points of Title Guaranty's island totals {P}. Maui: conveyance-tax schedule (homeowner vs non-homeowner rate), sales by price band; the entry cut is $800K in this source {O}. Statewide: HMDA first-lien purchase loans by property value {P}.</p>
    <!--WHY:mm-tiers-->
  </section>
  <section id="mm-type">
    <div class="head col"><span class="sec-n">Houses vs condos</span><h2>Condos are the outsiders' market: half of neighbor-island condo buyers are from out of state</h2></div>
    <div class="tw"><table><thead><tr><th>Island</th><th class="num">Houses sold 2025 · avg price</th><th class="num">Condos sold 2025 · avg price</th><th class="num">Out-of-state buyers: houses</th><th class="num">Out-of-state buyers: condos</th></tr></thead><tbody>{yrows}</tbody></table></div>
    <div class="col"><ul class="tight" style="margin-top:16px">
      <li><b>Oʻahu:</b> condo buyers in 2023–25 were {100*hv['condo_cpr_unit']['mainland_us']:.0f}% mainland and {100*hv['condo_cpr_unit']['foreign']:.0f}% foreign; house buyers {100*hv['house_non_cpr']['mainland_us']:.1f}% mainland {P}.</li>
      <li><b>Maui County:</b> {pct(mtyp.get('condo_cpr_unit',{}).get('share',{}).get('non_hawaii_total',0.598))} of condo units are owned from outside Hawaiʻi, against {pct(mtyp.get('house_non_cpr',{}).get('share',{}).get('non_hawaii_total',0.107))} of houses; 72% of condo sales in FY2024–26 went to buyers without a homeowner exemption, against 39% of house sales {P}.</li>
    </ul></div>
    <p class="src">Sales and average prices: DBEDT quarterly report Tables G-49 to G-52 (Title Guaranty data) {O}. Out-of-state shares: UHERO 2026 (2025 sales) {O}.</p>
    <!--WHY:mm-type-->
  </section>
  <section id="mm-luxury">
    <div class="head col"><span class="sec-n">Luxury and ultra-luxury</span><h2>519 sales at $3M+ in 2025. The Big Island now leads at $10M+.</h2></div>
    <div class="tw"><table><thead><tr><th>Island</th><th class="num">$3M+ sales, 2025</th><th class="num">Homes · condos · land</th><th class="num">$10M+ sales, 2025</th><th class="num">Median $3M+ home, 2025</th><th class="num">Jan–Jun 2026: $3M+ · $10M+</th></tr></thead><tbody>{lrows}</tbody></table></div>
    <div class="col"><ul class="tight" style="margin-top:16px">
      <li><b>Who buys it:</b> on Oʻahu, $3M+ buyers in 2023–25 were 67% local, 27% mainland (led by the Bay Area, Los Angeles and Seattle) and 6% foreign, almost all from Japan {P}. On Maui, 81% of $3–10M sales and 89% of $10M+ sales went to buyers without a homeowner exemption {O}. In January–June 2026, 15 of the state's 22 single-family sales at $10M+ were on Hawaiʻi Island {R}.</li>
      <li><b>Resort enclaves:</b> Mauna Kea Resort recorded 30 sales worth $159M in 2025 (average $6.8M); South Kohala had 42 sales at $3M+ {R}. On Oʻahu, $5M+ condo sales in Q2 2026 clustered in Park Lane (4) and Waiea (3) {R}.</li>
      <li><b>Financed luxury is rare and changing:</b> only 150 mortgaged purchases statewide were $3–10M in 2025; the share bought as a second home or investment fell from {pct(hm_tier(HT19,'luxury')['occupancy_share']['second_home']+hm_tier(HT19,'luxury')['occupancy_share']['investment'])} in 2019 to {pct(hm_tier(HT,'luxury')['occupancy_share']['second_home']+hm_tier(HT,'luxury')['occupancy_share']['investment'])} {P}. HMDA coded second homes differently in the two years, so only the combined share is compared.</li>
    </ul></div>
    <p class="src">Hawaiʻi Life luxury reports (2025 year-end, 2026 midyear), island figures summed here {R}. List Sotheby's Oʻahu Q2 2026 {R}. Oʻahu buyer origin: owner-roll match {P}. Maui: conveyance-tax schedule {O}. HMDA 2025 {P}.</p>
    <!--WHY:mm-luxury-->
  </section>
  <section id="mm-districts">
    <div class="head col"><span class="sec-n">Who buys in each district</span><h2>Mainland buyers range from 5% of sales in Central Oʻahu to two-thirds in Hanalei</h2>
      <p class="muted">Every Title Guaranty district on every island: where the 2025 buyers lived, and the mainland share in the first half of 2026.</p></div>
    <div class="tw"><table class="td"><thead><tr><th>District</th><th class="num">Sales 2025</th><th class="num">Buyers 2025: Hawaiʻi · <b>mainland</b> · foreign</th><th>Mainland share</th><th class="num">Mainland, Jan–Jun 2026</th></tr></thead><tbody>{drows}</tbody></table></div>
    <p class="src">Title Guaranty buyer statistics, district pages of the Q4 2025 and Q2 2026 editions. Each district's total is its US TOTAL plus FOREIGN TOTAL; mainland = US TOTAL minus Hawaiʻi-resident buyers. District rows sum exactly to the island totals {O}. Districts are Title Guaranty's own and are not ZIPs or tax districts. Foreign shares outside Honolulu rest on fewer than 20 sales.</p>
    <!--WHY:mm-districts-->
  </section>
  <section id="mm-loans">
    <div class="head col"><span class="sec-n">Mortgaged buyers, area by area</span><h2>In Poʻipū, Hanalei and Lahaina, 7 in 10 mortgaged buyers won't live in the home. In ʻEwa, 44% use a VA loan.</h2>
      <p class="muted">2025 home-purchase loans by census county subdivision: the share bought as a second home or investment, the VA share, and buyers' incomes.</p></div>
    <div class="tw"><table class="td"><thead><tr><th>Area</th><th class="num">Loans 2025</th><th class="num">Won't live there</th><th class="num">VA loans</th><th class="num">Median income</th><th class="num">Median value</th></tr></thead><tbody>{crows}</tbody></table></div>
    <p class="src">HMDA 2025 (and 2019) originated home-purchase loans on 1–4 unit site-built homes, mapped from census tract to county subdivision by housing units; tracts sit inside one subdivision almost everywhere {P}. "Won't live there" = second home plus investment; the two were coded differently in 2019, so only the combined share is compared. HMDA has no cash purchases. Areas with fewer than 20 loans are left out: {', '.join(lowc)}.</p>
    <!--WHY:mm-loans-->
  </section>
{isl_secs}
  </div>
'''
open(f'{S}/an/micro_chapter.html', 'w').write(chapter)
json.dump(SAY, open(f'{S}/an/mm/district_say.json', 'w'), ensure_ascii=False, indent=1)
print('chapter chars', len(chapter))
print('tier rows sample', trows[:600])
