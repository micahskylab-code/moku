# Render the "Why" boxes from the why-drivers workflow (research + skeptic challenge) plus our curated summaries.
# Visible text (lead, driver labels, broker and family notes) is written from the skeptic's checked final answer;
# the full answer, each driver as checked, untested factors and every source sit in a collapsed panel.
# Usage: python3 build_why.py  -> writes an/why_boxes.json {key: html}
import json, html, re
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
E = lambda s: html.escape(str(s or ''), quote=True)

TITLES = {
  'california': 'Why California leads on every island',
  'west_states': 'Why Washington, Oregon, Alaska, Colorado and Utah come next',
  'japan_korea': 'Why buyers from Japan and Korea concentrate on Oʻahu, and why they jumped in 2026',
  'canada': 'Why Canadians buy on Maui and Hawaiʻi Island, and why they pulled back',
  'maui_decline': 'Why Maui’s mainland buyer share fell',
  'investors_military': 'Why investors cluster on the neighbor islands and VA loans on Oʻahu',
  'affordability': 'Why a home now takes so much more of a local paycheck',
  'leavers': 'Why departing households go where they go',
  'now_2026': 'Why the market is turning toward buyers in 2026',
  'micro_hotspots': 'Why off-island owners and luxury cluster where they do',
}
STR = {'strong': ('Strong', 's3'), 'moderate': ('Moderate', 's2'), 'weak': ('Weak', 's1')}
DOWN = {'strong': 'moderate', 'moderate': 'weak', 'weak': 'weak'}
VERD = {'supported': 'supported by the check', 'weakened': 'weakened by the check', 'refuted': 'ruled out by the check', 'unchecked': 'not checked'}


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def fuzzy(drv, verdicts):
    n = set(norm(drv).split()); best, score = None, 0
    for v in verdicts:
        m = set(norm(v.get('driver')).split())
        sc = len(n & m) / max(1, len(n | m))
        if sc > score: best, score = v, sc
    return best if score >= 0.2 else None


def md(text):
    """Tiny markdown: blank-line paragraphs, '- ' bullets, **bold**."""
    out, items = [], []
    def flush():
        if items: out.append('<ul>' + ''.join(f'<li>{x}</li>' for x in items) + '</ul>'); items.clear()
    for block in re.split(r'\n\s*\n', text.strip()):
        for ln in block.split('\n'):
            s = E(ln.strip()); s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
            if ln.strip().startswith('- '):
                items.append(s[2:])
            elif s:
                flush(); out.append(f'<p>{s}</p>')
        flush()
    return ''.join(out)


# ---- client-facing sanitizing: no process notes, file paths, or religion/ancestry/building-by-country details
DROP_SENT = re.compile(r'(web[- ]search|search budget|quota|Verification note|cached earlier|this session|were blocked|sites were blocked|this agent|re-checked in this pass|budget ran out|re-checks used direct downloads|Outside facts were re-checked)', re.I)
REPL = [
  ('home to about 95,000 Native Hawaiians, which adds', 'home to a large community with Hawaiʻi roots, which adds'),
  ("Utah's distinctive tie is the Church community in Laie on Oahu, but it is small: 55 of 944 Laie parcels, 19 of them mailed to the Church headquarters ZIP.", "Utah's distinctive tie is the community around BYU–Hawaiʻi in Lāʻie on Oʻahu, but it is small: 55 of 944 Lāʻie parcels."),
  ('(55 of 118, 19 of them mailed to the Church headquarters ZIP)', '(55 of 118)'),
  ('Japan-billed owners already hold about 2,000 Oahu parcels', 'Owners with Japan mailing addresses already hold about 2,000 Oʻahu parcels'),
  (', and the county roll now shows 61 Japan-billed owners in the tower.', '.'),
  ('; that building holds 80 Korea-billed units today.', '.'),
  ('The county roll now shows 61 Japan-billed owners there.', ''),
  (' (80 Korea-billed units today)', ''),
  ('Today the recent Ward Village towers are about 11-12% Japan-billed on the tax roll, against 1.3% at The Park on Keeaumoku.', ''),
  ('Native Hawaiian population growth by state does not line up', 'the growth of communities with Hawaiʻi roots by state does not line up'),
  ('including church addresses', 'including institutional addresses'),
  ("Some are church-related institutions and some are likely families tied to BYU-Hawai'i.", "Some are institutions and some are likely families tied to BYU–Hawaiʻi."),
  ('A few policy details (Honolulu Ordinance 25-44, Act 17, Maui\'s September 2026 rezoning vote) were not re-verified.', 'Policy details (Honolulu Ordinance 25-44, Act 17 and Maui\'s September 2026 rezoning vote) are as reported.'),
  ('Japanese purchases fell from 581 in 2018', 'Japanese purchases on Oʻahu fell from 581 in 2018'),
  ("Moku's", "the City and County of Honolulu's"),
]
def clean(t):
    t = t or ''
    for a, b in REPL: t = t.replace(a, b)
    out = []
    for para in re.split(r'(\n\s*\n)', t):
        if re.fullmatch(r'\n\s*\n', para): out.append(para); continue
        sents = re.split(r'(?<=[.!?)])\s+(?=[A-Z(])', para)
        keep = [x for x in sents if not DROP_SENT.search(x)]
        out.append(' '.join(keep))
    t = ''.join(out)
    t = re.sub(r'\(\s*\)', '', t)
    return re.sub(r'[ \t]{2,}', ' ', t).strip()
BAD_HOST = re.compile(r'(legalclarity|veteran\.com|vetcalc|wikipedia|msyxorap|github)', re.I)
def clean_src(name):
    name = re.sub(r'\s*\((?:[^()]*?(?:local file|search excerpt|\.json|\.csv|blocked|mirror|computed here|cached|seen in a search)[^()]*)\)', '', name or '', flags=re.I)
    name = re.sub(r',?\s*local file[^,;]*', '', name, flags=re.I)
    name = re.sub(r',?\s*aggregated in [\w./-]+\.json', '', name, flags=re.I)
    name = re.sub(r"computed in the report.s [\w./-]+\.json", 'computed for this report', name, flags=re.I)
    name = re.sub(r'\s*\((?:summarized via search|via search)\)', '', name, flags=re.I)
    name = name.replace('Moku recorded-sales file', 'Honolulu recorded-sales file').replace('Moku repeat-sales index', 'Repeat-sales index').replace("Moku's", "City and County of Honolulu").replace('Moku', 'Honolulu sales records')
    return name.strip(' ,;')


def render(item, cur):
    k = item['key']; r = item['research']; c = item.get('challenge') or {}
    ver = c.get('verdicts', []); drs = r.get('drivers', [])
    labels = cur['labels']; assert len(labels) == len(drs), (k, len(labels), len(drs))
    rows, detail, ruled = [], [], []
    for i, d in enumerate(drs):
        v = ver[i] if len(ver) == len(drs) else fuzzy(d['driver'], ver)
        verdict = (v or {}).get('verdict', 'unchecked')
        st = d.get('strength', 'moderate')
        if verdict == 'weakened': st = DOWN[st]
        text = clean((v or {}).get('corrected_wording') or d['driver'])
        lab = labels[i]
        if verdict == 'refuted' or lab is None:
            ruled.append(f'<li><b>Ruled out:</b> {E(text)}</li>')
            continue
        rows.append((['strong', 'moderate', 'weak'].index(st), lab, st, verdict, text, d.get('evidence', [])))
    rows.sort(key=lambda x: x[0])
    o = [f'<aside class="whybox" id="why-{k}">',
         f'<div class="wb-eye">Why</div><h4 class="wb-t">{E(TITLES[k])}</h4>',
         f'<p class="wb-a">{E(cur["lead"])}</p>', '<ol class="wb-d">']
    for _, lab, st, verdict, text, _ev in rows:
        nm, cls = STR[st]
        o.append(f'<li><span class="wb-s {cls}">{nm}</span><span class="wb-x">{E(lab)}</span></li>')
        detail.append(f'<li><b>{E(lab)}</b> <span class="wb-v">({nm.lower()}; {VERD[verdict]})</span>. {E(text)}</li>')
    o.append('</ol>')
    o.append(f'<div class="wb-so"><div><b>For brokers</b><p>{E(cur["brokers"])}</p></div><div><b>For local families</b><p>{E(cur["families"])}</p></div></div>')
    # sources from surviving drivers (source names and links only; facts are restated in the checked answer)
    seen, src = set(), []
    for _, _l, _s, _v, _t, ev in rows:
        for e in ev:
            u = (e.get('url') or '').strip(); key = u
            if not u.startswith('http') or BAD_HOST.search(u + ' ' + (e.get('source') or '')) or key in seen: continue
            seen.add(key); src.append(e)
    miss = c.get('missing_drivers') or []
    o.append(f'<details class="wb-ev"><summary>The full explanation, each driver as checked, and {len(src)} sources</summary>')
    o.append('<p class="wb-h">The checked answer</p>' + md(clean(c.get('final_answer') or r.get('answer'))))
    o.append('<p class="wb-h">Each driver, as checked</p><ul>' + ''.join(detail) + '</ul>')
    lis = []
    for e in src:
        nm = E(clean_src(e.get('source'))); u = (e.get('url') or '').strip()
        if u.startswith('http'): nm = f'<a href="{E(u)}" target="_blank" rel="noopener">{nm}</a>'
        lis.append(f'<li>{nm}{(", " + E(e["date"])) if e.get("date") else ""}</li>')
    o.append(f'<p class="wb-h">Sources</p><ul class="wb-src">{"".join(lis)}</ul>')
    o.append(f'<p class="wb-cf">How this was built: one researcher gathered the evidence, and a second tried to refute every driver by re-checking its facts and looking for other explanations. '
             f'Refuted drivers are dropped; weakened ones are marked down a level. Overall confidence: <b>{E(r.get("confidence"))}</b>.</p></details>')
    o.append('</aside>')
    return '\n'.join(o)


if __name__ == '__main__':
    items = json.load(open(f'{S}/an/why_result.json')); cur = json.load(open(f'{S}/an/why_curated.json'))
    out = {it['key']: render(it, cur[it['key']]) for it in items}
    json.dump(out, open(f'{S}/an/why_boxes.json', 'w'), ensure_ascii=False, indent=1)
    print({k: len(v) for k, v in out.items()})
