"""Builds a self-contained copy of the viewer for a private claude.ai Artifact page.

Usage: python3 scripts/build_artifact.py <out-dir>

The Artifact host wraps the page in its own <!doctype html><head><body> skeleton, admits scripts only from a few
CDNs, and passes no query string to the page. So the copy:
  - drops the document skeleton tags and the viewport meta from index.html (the host supplies both);
  - loads three.js r160 (three@0.160.0, byte-identical to vendor/, checked against the npm package) and
    astronomy-engine 2.1.19 (esm/astronomy.js, which vendor/ holds minified) from jsDelivr instead of publishing vendor/;
  - opens in the model view (window.__NAHIKU_MODE), since ?mode=model cannot reach the page;
  - hides the Ultra button (it reloads with a query string) and the 360 tour link (its panoramas are not built);
  - copies only what the viewer loads: src/, plans/, data/, geodata/ (top-level files) and geodata/community/ (the
    community view's tiles), with the height grids as base64 text, since the host serves no binary types.
Everything stays labelled as an independent concept visualization.
"""
import base64
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THREE = 'https://cdn.jsdelivr.net/npm/three@0.160.0/'
# vendor/astronomy.module.min.js is a terser build of this same file (astronomy-engine 2.1.19, esm/astronomy.js)
ASTRONOMY = 'https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/esm/astronomy.js'


def build(out: Path):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    html = (ROOT / 'index.html').read_text()
    html = re.sub(r'<!doctype html>\s*|</?html[^>]*>\s*|</?head>\s*|</?body>\s*', '', html, flags=re.I)
    html = re.sub(r'<meta charset="utf-8">\s*|<meta name="viewport"[^>]*>\s*', '', html)
    html = html.replace('<title>Walkthrough</title>', '<title>Nā Hiku Concept Model</title>')
    imap = '{ "imports": { "three": "./vendor/three.module.js", "three/addons/": "./vendor/addons/" } }'
    assert imap in html, 'importmap changed'
    # relative keys remap the URLs src/ imports by path ('../vendor/...') to the same files on the CDN
    html = html.replace(imap, '{ "imports": { "three": "%sbuild/three.module.js", "three/addons/": "%sexamples/jsm/",\n'
                              '  "./vendor/three.module.js": "%sbuild/three.module.js", "./vendor/astronomy.module.min.js": "%s" } }'
                        % (THREE, THREE, THREE, ASTRONOMY))
    html = html.replace('<a href="tour.html">360° tour</a>', '')
    html = html.replace('</style>', '  #quality { display: none !important; }\n</style>', 1)
    main = '<script type="module" src="src/main.js"></script>'
    assert main in html
    html = html.replace(main, '<script>window.__NAHIKU_MODE = \'model\'; window.__NAHIKU_HOSTED = true;</script>\n' + main)   # hosted: no file download offered
    (out / 'index.html').write_text(html)
    files = []
    for d in ('src', 'plans', 'data'):
        for f in sorted((ROOT / d).rglob('*')):
            if f.is_file() and '__pycache__' not in f.parts:
                files.append(f)
    files += sorted(f for f in (ROOT / 'geodata').iterdir() if f.is_file() and f.suffix != '.bin')
    files = [f for f in files if f.name != 'test-plan.json']
    for f in files:
        rel = f.relative_to(ROOT)
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out / rel)
    # the host serves no binary types: height grids go as base64 text (src/realsite.js decodes '.b64.txt')
    meta = json.loads((ROOT / 'geodata' / 'realsite.json').read_text())
    for g in ('near', 'far'):
        src = ROOT / 'geodata' / meta[g]['height']
        meta[g]['height'] = src.stem + '.b64.txt'
        (out / 'geodata' / meta[g]['height']).write_text(base64.b64encode(src.read_bytes()).decode())
    (out / 'geodata' / 'realsite.json').write_text(json.dumps(meta, indent=1))
    # community view tiles (scripts/geo_community.py): images and json as they are, the height grid as base64 text
    # (src/community.js falls back to h.b64.txt when h.bin is not served)
    comm = ROOT / 'geodata' / 'community'
    if comm.is_dir():
        (out / 'geodata' / 'community').mkdir(parents=True, exist_ok=True)
        for f in sorted(comm.iterdir()):
            if f.suffix in ('.webp', '.png', '.json'):
                shutil.copy2(f, out / 'geodata' / 'community' / f.name)
            elif f.suffix == '.bin':
                (out / 'geodata' / 'community' / (f.stem + '.b64.txt')).write_text(base64.b64encode(f.read_bytes()).decode())
    n = sum(1 for f in out.rglob('*') if f.is_file())
    print(f'{out}: {n} files, {sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6:.1f} MB')


if __name__ == '__main__':
    build(Path(sys.argv[1]))
