# Render the "Why" boxes from the why-drivers workflow (research + skeptic challenge) into the report template.
# Usage: python3 build_why.py why_result.json  -> writes an/why_boxes.json {key: html}
import json, sys, html, re
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
E = lambda s: html.escape(str(s or ''), quote=True)

TITLES = {
  'california': 'Why California leads on every island',
  'west_states': 'Why Washington, Oregon, Alaska, Colorado and Utah come next',
  'japan_korea': 'Why Japanese and Korean buyers concentrate on Oʻahu',
  'canada': 'Why Canadians buy on Maui and Hawaiʻi Island, and why they pulled back',
  'maui_decline': 'Why Maui’s mainland buyer share fell',
  'investors_military': 'Why investors and VA loans matter so much',
  'affordability': 'Why a home now takes so much more of a local paycheck',
  'leavers': 'Why departing households go where they go',
  'now_2026': 'Why the market is turning toward buyers in 2026',
  'micro_hotspots': 'Why off-island owners and luxury cluster where they do',
}
STR = {'strong': ('Strong', 's3'), 'moderate': ('Moderate', 's2'), 'weak': ('Weak', 's1')}
KIND = {'data': ('Primary', 'p'), 'official': ('Official', 'o'), 'reported': ('Reported', 'r')}


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def match_verdict(drv, verdicts):
    n = norm(drv)
    best, score = None, 0
    for v in verdicts:
        m = norm(v.get('driver'))
        if not m:
            continue
        if m == n:
            return v
        a, b = set(n.split()), set(m.split())
        sc = len(a & b) / max(1, len(a | b))
        if sc > score:
            best, score = v, sc
    return best if score >= 0.35 else None


def render(item):
    k = item['key']; r = item['research']; c = item.get('challenge') or {}
    verdicts = c.get('verdicts', [])
    answer = c.get('final_answer') or r.get('answer')
    drivers = []
    for d in r.get('drivers', []):
        v = match_verdict(d['driver'], verdicts)
        verdict = (v or {}).get('verdict', 'unchecked')
        if verdict == 'refuted':
            continue
        text = (v or {}).get('corrected_wording') or d['driver']
        strength = d.get('strength', 'moderate')
        if verdict == 'weakened' and strength == 'strong':
            strength = 'moderate'
        elif verdict == 'weakened' and strength == 'moderate':
            strength = 'weak'
        drivers.append({'text': text, 'strength': strength, 'effect': d.get('quantified_effect') or '',
                        'evidence': d.get('evidence', []), 'verdict': verdict,
                        'fact_errors': (v or {}).get('fact_errors') or []})
    order = {'strong': 0, 'moderate': 1, 'weak': 2}
    drivers.sort(key=lambda d: order.get(d['strength'], 3))
    o = [f'<aside class="whybox" id="why-{k}">',
         f'<div class="wb-eye">Why</div><h4 class="wb-t">{E(TITLES.get(k, r.get("question")))}</h4>',
         f'<p class="wb-a">{E(answer)}</p>']
    if drivers:
        o.append('<ol class="wb-d">')
        for d in drivers:
            lab, cls = STR.get(d['strength'], ('', 's1'))
            eff = f'<span class="wb-e">{E(d["effect"])}</span>' if d['effect'] and d['effect'].lower() not in ('n/a', 'none', 'not quantified') else ''
            o.append(f'<li><span class="wb-s {cls}">{lab}</span><span class="wb-x">{E(d["text"])}{eff}</span></li>')
        o.append('</ol>')
    fb, fl = r.get('for_brokers'), r.get('for_locals')
    if fb or fl:
        o.append('<div class="wb-so">')
        if fb: o.append(f'<div><b>For brokers</b><p>{E(fb)}</p></div>')
        if fl: o.append(f'<div><b>For local families</b><p>{E(fl)}</p></div>')
        o.append('</div>')
    # evidence
    ev, seen = [], set()
    for d in drivers:
        for e in d['evidence']:
            key = (e.get('fact'), e.get('url'))
            if key in seen:
                continue
            seen.add(key); ev.append(e)
    cav = list(r.get('counter_evidence') or []) + [f'Also likely: {m}' for m in (c.get('missing_drivers') or [])]
    if ev or cav:
        o.append(f'<details class="wb-ev"><summary>Evidence ({len(ev)}) and caveats</summary><ul>')
        for e in ev:
            kl, kc = KIND.get(e.get('kind'), ('Reported', 'r'))
            src = E(e.get('source'))
            if e.get('url', '').startswith('http'):
                src = f'<a href="{E(e["url"])}" target="_blank" rel="noopener">{src}</a>'
            val = f' <b>{E(e["value"])}</b>.' if e.get('value') else ''
            dt = f', {E(e["date"])}' if e.get('date') else ''
            o.append(f'<li><span class="tag {kc}">{kl}</span> {E(e.get("fact"))}{val} <span class="wb-src">{src}{dt}</span></li>')
        o.append('</ul>')
        if cav:
            o.append('<p class="wb-ch">What cuts the other way</p><ul>' + ''.join(f'<li>{E(x)}</li>' for x in cav) + '</ul>')
        conf = r.get('confidence', 'medium')
        o.append(f'<p class="wb-cf">Overall confidence: <b>{E(conf)}</b>. Each driver was checked by a second researcher who tried to refute it; refuted drivers are removed and weakened ones are downgraded.</p></details>')
    o.append('</aside>')
    return '\n'.join(o)


if __name__ == '__main__':
    items = json.load(open(sys.argv[1]))
    out = {it['key']: render(it) for it in items if it and it.get('research')}
    json.dump(out, open(f'{S}/an/why_boxes.json', 'w'), ensure_ascii=False, indent=1)
    print({k: len(v) for k, v in out.items()})
