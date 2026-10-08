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
  'japan_korea': 'Why Japanese and Korean buyers concentrate on Oʻahu, and why they jumped in 2026',
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
        text = (v or {}).get('corrected_wording') or d['driver']
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
            u = (e.get('url') or '').strip(); key = u or e.get('source')
            if not key or key in seen: continue
            seen.add(key); src.append(e)
    miss = c.get('missing_drivers') or []
    o.append(f'<details class="wb-ev"><summary>Full explanation, every driver as checked, and {len(src)} sources</summary>')
    o.append('<p class="wb-h">The checked answer</p>' + md(c.get('final_answer') or r.get('answer')))
    o.append('<p class="wb-h">Each driver, as checked</p><ul>' + ''.join(detail) + '</ul>')
    if miss:
        o.append('<p class="wb-h">Other factors the check raised (not fully tested)</p><ul>' + ''.join(f'<li>{E(m)}</li>' for m in miss) + '</ul>')
    lis = []
    for e in src:
        nm = E(e.get('source')); u = (e.get('url') or '').strip()
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
