// Screens of the community view (src/community.js): the opening flight, the whole community, the coast, the home.
// Usage: node scripts/community_qa.mjs [out-dir] [query]   (fixed sky: 21 Jun 09:15 HST, clear trades)
// Env: W, H viewport (default 1600x900); SHOTS=1,3 a subset of the poses; Q=low the phone quality (CM_LOW paths).
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const root = new URL('..', import.meta.url).pathname;
const out = process.argv[2] ?? join(root, 'shots', 'community');
const extra = process.argv[3] ?? '';
await mkdir(out, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = path === '/' ? '/index.html' : path;
  let body;
  try { body = await readFile(join(root, file)); } catch { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }).end(body);
}).listen(0);
const base = `http://localhost:${server.address().port}/`;
const SKY = `q=${process.env.Q ?? 'high'}&live=0&wx=clear&doy=172&hst=09:15`;
const W = Number(process.env.W ?? 1600), H = Number(process.env.H ?? 900);

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext({ viewport: { width: W, height: H } });
const errors = [], checks = [];
const page = await ctx.newPage();
page.setDefaultTimeout(900000);
page.on('pageerror', e => errors.push(`pageerror: ${e.message}`));
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text().slice(0, 300)}`); });
const check = (name, ok, detail = '') => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` - ${detail}` : ''}`); };
const frames = (n = 3) => page.evaluate(n => new Promise(res => { let k = 0; const f = () => (++k >= n ? res() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);
const settle = () => page.waitForFunction(() => window.__community?.settled(), null, { timeout: 900000, polling: 500 });
const shot = async name => { await settle(); await frames(4); await page.screenshot({ path: join(out, `${name}.png`) }); console.log('shot', name, `${((Date.now() - t0) / 1000).toFixed(0)} s`); };

const t0 = Date.now();
await page.goto(`${base}?mode=community&${SKY}${extra ? '&' + extra : ''}`);
await page.waitForFunction(() => window.__community && document.body.classList.contains('community-mode'), null, { timeout: 900000 });
console.log(`loaded in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
check('community view opens from ?mode=community', true);
// what stays on screen: the one-line notice under the title and the short credits (the card's note folds away with it)
const shown = sel => page.evaluate(sel => { const e = document.querySelector(sel), r = e?.getBoundingClientRect();
  return e && getComputedStyle(e).display !== 'none' && r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight ? e.innerText.replace(/\s+/g, ' ') : ''; }, sel);
const notice = await shown('#concept .cc-cm');
check('notice visible', /independent concept/i.test(notice) && /homes modeled/i.test(notice) && /not by the developer/i.test(notice) && /views not shown or verified/i.test(notice), notice);
const credits = await shown('#community .cm-attr');
check('short credits visible', /photo: USDA NAIP 2022/i.test(credits) && /© OpenStreetMap contributors/.test(credits) && (W <= 600 || /Copernicus Sentinel/.test(credits)) && /Meta\/WRI/.test(credits) && /CC BY 4\.0/.test(credits) && /Credits\s*$/.test(credits), credits);
check('card note in the card', /Aerial photo: USDA NAIP 2022/.test(await page.textContent('#community .cm-fine')) && /homes are modeled/.test(await page.textContent('#community .cm-fine')));
await frames(2);
await page.screenshot({ path: join(out, '0-opening.png') });   // the opening frame, before the flight in (512 px tiles)
const poses = {
  '1-establishing': `C.establishing()`,
  '2-overview': `C.overview()`,
  '3-home-close': `C.pose(C.pins[0].ground, 900, 0.95, C.northAz - 0.6)`,
  '4-coast': `(() => { const [x, z] = C.fromLatLon(21.8846, -159.4925); const g = new (C.pins[0].ground.constructor)(x, C.groundAt(x, z), z); return C.pose(g, 2400, 1.05, C.northAz + 0.4); })()`,
  '5-golf-oblique': `(() => { const [x, z] = C.fromLatLon(21.8925, -159.4850); const g = new (C.pins[0].ground.constructor)(x, C.groundAt(x, z), z); return C.pose(g, 3200, 1.18, C.northAz + 2.6); })()`,
  // the view's own 3D trees nearest the home, east of the strip, low and close: umbrella trunks on the tiles, not buried or afloat
  '6-trees-east': `(() => { const g = new (C.pins[0].ground.constructor)(445, C.groundAt(445, 200), 200); return C.pose(g, 420, 1.15, C.northAz - 0.6); })()`,
};
const only = process.env.SHOTS ? process.env.SHOTS.split(',') : null;   // e.g. SHOTS=1,3 for a quick pass
for (const [name, expr] of Object.entries(poses)) {
  if (only && !only.some(k => name.startsWith(k))) continue;
  await page.evaluate(e => { const C = window.__community; C.jump(eval(e)); }, expr);
  await frames(3);
  await shot(name);
}
// The view's own 3D trees (realsite.js communityTrees) stand on the surface the tiles draw: each umbrella's trunk base
// (sunk 0.4 ft) on the tile triangles under it. The walkthrough's trees are hidden while the view is open, are never
// moved, and are shown again on exit on their own ground; entering again draws the same trees.
const treeState = () => page.evaluate(() => {
  const C = window.__community, R = window.__realsite, grp = {};
  window.__scene?.scene.traverse(o => { if (o.name === 'realsite trees' || o.name === 'community trees') grp[o.name] = o; });
  const shown = o => { for (let p = o; p; p = p.parent) if (!p.visible) return false; return true; };
  // instance positions (identity group transforms, see neighborhood.js), and under each trunk the ground it should stand on
  const read = (o, ground) => o ? { shown: shown(o), meshes: o.children.filter(m => m.isInstancedMesh).map(m => {
    const a = m.instanceMatrix.array, xyz = [], g = [], trunk = /trunk/.test(m.material.name);
    for (let k = 0; k < m.count; k++) { xyz.push(a[16 * k + 12], a[16 * k + 13], a[16 * k + 14]); if (trunk) g.push(ground(a[16 * k + 12], a[16 * k + 14])); }
    return { trunk, xyz, g };
  }) } : null;
  return { cm: read(grp['community trees'], (x, z) => C.surfaceAt(x, z)), rs: R ? read(grp['realsite trees'], (x, z) => R.ground(x, z)) : null };
});
// largest move of any instance between two states (Infinity if the sets differ)
const moved = (a, b) => {
  if (!a || !b || a.meshes.length !== b.meshes.length) return Infinity;
  let d = 0;
  a.meshes.forEach((m, j) => { const o = b.meshes[j].xyz; if (o.length !== m.xyz.length) d = Infinity; else for (let i = 0; i < o.length; i++) d = Math.max(d, Math.abs(o[i] - m.xyz[i])); });
  return d;
};
const inView = await treeState();
if (inView.cm) {
  const toggle = () => page.evaluate(() => document.getElementById('community-btn').click());
  await toggle(); await page.waitForFunction(() => !document.body.classList.contains('community-mode')); await frames(2);
  const walk = await treeState();
  await toggle(); await page.waitForFunction(() => document.body.classList.contains('community-mode')); await frames(2);
  const again = await treeState();
  let n = 0, off = 0, gap = 0, worst = '';
  for (const m of inView.cm.meshes) if (m.trunk) m.g.forEach((s, k) => {
    if (s == null || Number.isNaN(s)) { off++; return; }                // off the tiles (NaN arrives as null)
    n++; const e = Math.abs(m.xyz[3 * k + 1] + 0.4 - s);
    if (e > gap) { gap = e; worst = `trunk ${k} at (${m.xyz[3 * k].toFixed(0)}, ${m.xyz[3 * k + 2].toFixed(0)})`; }
  });
  check('3D trees stand on the tiles in the view', inView.cm.shown && n > 0 && gap < 0.05, `${n} umbrella trunks over tiles (${off} off them), worst gap ${gap.toFixed(3)} ft${worst ? ` (${worst})` : ''}`);
  const again1 = moved(inView.cm, again.cm);
  check("the view's trees hidden on exit, the same trees on entering again", !walk.cm.shown && again.cm.shown && again1 < 1e-3, `max difference ${again1.toExponential(1)} ft`);
  if (inView.rs && walk.rs && again.rs) {
    let back = 0;
    for (const m of walk.rs.meshes) if (m.trunk) m.g.forEach((g, k) => { back = Math.max(back, Math.abs(m.xyz[3 * k + 1] + 0.4 - g)); });
    const still = Math.max(moved(inView.rs, walk.rs), moved(walk.rs, again.rs));
    check("the walkthrough's trees hidden in the view", !inView.rs.shown && !again.rs.shown);
    check("the walkthrough's trees shown on exit, unmoved, on their own ground", walk.rs.shown && still < 1e-3 && back < 0.05, `max move ${still.toExponential(1)} ft, trunk base vs realsite ground ${back.toFixed(3)} ft`);
  } else check("the walkthrough's trees present", false, 'no realsite trees group');
} else check('3D trees present', false, 'no community trees group');
const errs = errors.filter(e => !/GPU stall|swiftshader|WebGL: INVALID_ENUM|Automatic fallback/i.test(e));
check('no page errors', !errs.some(e => e.startsWith('pageerror')), errs.join(' | ').slice(0, 600));
await writeFile(join(out, 'qa.json'), JSON.stringify({ checks, errors: errs }, null, 1));
await browser.close(); server.close();
