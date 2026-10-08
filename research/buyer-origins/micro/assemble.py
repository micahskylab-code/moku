# Assemble the report: swap in the freshly built micro-markets chapter, place the "Why" boxes, inject page data.
# Idempotent: why boxes sit between <!--WHYBOX:key--> ... <!--/WHYBOX:key--> markers and are replaced on each run.
import json, os, re
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
src = open(f'{S}/hawaii-buyer-origins.src.html').read()

# 1. micro chapter
ch = open(f'{S}/an/micro_chapter.html').read().strip('\n')
a = src.find('<div class="chapter" id="micro">'); b = src.find('<div class="chapter"', a + 10)
assert a > 0 and b > a
src = src[:a] + ch.lstrip() + '\n\n  ' + src[b:]

# 2. why boxes: section id -> list of why keys (placed at the end of that section)
PLACE = {
    'corridors': ['leavers'],
    'buyers': ['california', 'west_states', 'japan_korea', 'canada'],
    'islands': ['maui_decline'],
    'mm-glance': ['investors_military'],
    'mm-oahu': ['micro_hotspots'],
    'squeeze': ['affordability'],
    'now': ['now_2026'],
}
extra = json.load(open(f'{S}/an/why_extra.json')) if os.path.exists(f'{S}/an/why_extra.json') else {}
boxes = json.load(open(f'{S}/an/why_boxes.json')) if os.path.exists(f'{S}/an/why_boxes.json') else {}
src = re.sub(r'\n?[ ]*<!--WHYBOX:[a-z_0-9-]+-->.*?<!--/WHYBOX:[a-z_0-9-]+-->', '', src, flags=re.S)


def section_end(s, sid):
    i = s.find(f'<section id="{sid}"')
    assert i >= 0, sid
    depth, j = 0, i
    for m in re.finditer(r'<section\b|</section>', s[i:]):
        depth += 1 if m.group(0) == '<section' else -1
        if depth == 0:
            return i + m.start()
    raise ValueError(sid)


for sid, keys in PLACE.items():
    got = [k for k in keys if k in boxes]
    if not got:
        continue
    inner = '\n'.join(boxes[k] for k in got)
    if len(got) > 1:
        inner = f'<div class="whygrid">{inner}</div>'
    blk = f'\n    <!--WHYBOX:{sid}-->\n{inner}\n    <!--/WHYBOX:{sid}-->\n  '
    e = section_end(src, sid)
    # trim trailing whitespace before the closing tag so the block sits flush
    k = e
    while src[k - 1] in ' \n':
        k -= 1
    src = src[:k] + blk + src[e:]

# micro-market placeholders: short, data-led "why" notes written for each section
for key, htmltext in extra.items():
    src = src.replace(f'<!--WHY:{key}-->', f'<!--WHY:{key}-->\n    <!--WHYBOX:{key}-->{htmltext}<!--/WHYBOX:{key}-->')

open(f'{S}/hawaii-buyer-origins.src.html', 'w').write(src)
d = json.dumps(json.load(open(f'{S}/an/page_data.json')), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
open(f'{S}/hawaii-buyer-origins.html', 'w').write(src.replace('__DATA__', d))
print('placed', {k: v for k, v in PLACE.items() if any(x in boxes for x in v)}, 'extra', list(extra))
