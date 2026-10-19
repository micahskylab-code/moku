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
check('notice visible', /independent concept/i.test(notice) && /not by the developer/i.test(notice) && /views not shown or verified/i.test(notice), notice);
const credits = await shown('#community .cm-attr');
check('short credits visible', /© OpenStreetMap contributors/.test(credits) && /Copernicus Sentinel/.test(credits) && /Meta\/WRI/.test(credits) && /CC BY 4\.0/.test(credits) && /Credits\s*$/.test(credits), credits);
check('card note in the card', /not an aerial photograph/.test(await page.textContent('#community .cm-fine')));
await frames(2);
await page.screenshot({ path: join(out, '0-opening.png') });   // the opening frame, before the flight in (512 px tiles)
const poses = {
  '1-establishing': `C.establishing()`,
  '2-overview': `C.overview()`,
  '3-home-close': `C.pose(C.pins[0].ground, 900, 0.95, C.northAz - 0.6)`,
  '4-coast': `(() => { const [x, z] = C.fromLatLon(21.8846, -159.4925); const g = new (C.pins[0].ground.constructor)(x, C.groundAt(x, z), z); return C.pose(g, 2400, 1.05, C.northAz + 0.4); })()`,
  '5-golf-oblique': `(() => { const [x, z] = C.fromLatLon(21.8925, -159.4850); const g = new (C.pins[0].ground.constructor)(x, C.groundAt(x, z), z); return C.pose(g, 3200, 1.18, C.northAz + 2.6); })()`,
  // the walkthrough's 3D trees nearest the home, east of the strip, low and close: trunks on the ground, not buried
  '6-trees-east': `(() => { const g = new (C.pins[0].ground.constructor)(445, C.groundAt(445, 200), 200); return C.pose(g, 420, 1.15, C.northAz - 0.6); })()`,
};
const only = process.env.SHOTS ? process.env.SHOTS.split(',') : null;   // e.g. SHOTS=1,3 for a quick pass
for (const [name, expr] of Object.entries(poses)) {
  if (only && !only.some(k => name.startsWith(k))) continue;
  await page.evaluate(e => { const C = window.__community; C.jump(eval(e)); }, expr);
  await frames(3);
  await shot(name);
}
// The walkthrough's 3D trees stand on the tiles while the view is on (trunk base on the tile surface) and get their own
// matrices back on exit (trunk base on the realsite ground, crowns moved back by the same amount); re-entering repeats it.
const treeState = () => page.evaluate(() => {
  const C = window.__community, R = window.__realsite; let grp = null;
  window.__scene?.scene.traverse(o => { if (o.name === 'realsite trees') grp = o; });
  if (!grp || !R) return null;
  const meshes = grp.children.filter(m => m.isInstancedMesh).map(m => {
    const a = m.instanceMatrix.array, xyz = [];
    for (let k = 0; k < m.count; k++) xyz.push(a[16 * k + 12], a[16 * k + 13], a[16 * k + 14]);
    return { trunk: /trunk/.test(m.material.name), xyz };
  });
  // per instance: the tile surface and the realsite ground under it (identity group transform, see neighborhood.js)
  for (const m of meshes) { m.s = []; m.g = []; for (let i = 0; i < m.xyz.length; i += 3) { m.s.push(C.surfaceAt(m.xyz[i], m.xyz[i + 2])); m.g.push(R.ground(m.xyz[i], m.xyz[i + 2])); } }
  return meshes;
});
const inView = await treeState();
if (inView) {
  const toggle = () => page.evaluate(() => document.getElementById('community-btn').click());
  await toggle(); await page.waitForFunction(() => !document.body.classList.contains('community-mode')); await frames(2);
  const walk = await treeState();
  await toggle(); await page.waitForFunction(() => document.body.classList.contains('community-mode')); await frames(2);
  const again = await treeState();
  let onTiles = 0, n = 0, back = 0, crownMove = 0, same = 0, worst = '', big = 0, maxD = 0;
  inView.forEach((m, j) => {
    for (let k = 0; k < m.s.length; k++) {
      const y = m.xyz[3 * k + 1], yw = walk[j].xyz[3 * k + 1], s = m.s[k] ?? NaN, g = m.g[k];   // NaN (off the tiles) arrives as null
      same = Math.max(same, Math.abs(again[j].xyz[3 * k + 1] - y), Math.abs(walk[j].xyz[3 * k] - m.xyz[3 * k]), Math.abs(walk[j].xyz[3 * k + 2] - m.xyz[3 * k + 2]));
      if (m.trunk) {
        back = Math.max(back, Math.abs(yw + 0.4 - g));
        if (!Number.isNaN(s)) {
          n++; const e = Math.abs(y + 0.4 - s); if (e > onTiles) { onTiles = e; worst = `trunk ${k}`; }
          if (Math.abs(s - g) > 1) big++; maxD = Math.max(maxD, Math.abs(s - g));
        }
      }
      crownMove = Math.max(crownMove, Math.abs((y - yw) - (Number.isNaN(s) ? 0 : s - g)));
    }
  });
  check('3D trees stand on the tiles in the view', onTiles < 0.05, `${n} trunks over tiles, worst gap ${onTiles.toFixed(3)} ft (${worst}); ${big} moved more than 1 ft, at most ${maxD.toFixed(1)} ft`);
  check('3D trees back on the walkthrough ground on exit', back < 0.05 && crownMove < 0.05, `trunk base vs realsite ground ${back.toFixed(3)} ft, crown shift vs tile offset ${crownMove.toFixed(3)} ft`);
  check('re-entering the view moves the same trees the same way', same < 1e-3, `max difference ${same.toExponential(1)} ft`);
} else check('3D trees present', false, 'no realsite trees group');
const errs = errors.filter(e => !/GPU stall|swiftshader|WebGL: INVALID_ENUM|Automatic fallback/i.test(e));
check('no page errors', !errs.some(e => e.startsWith('pageerror')), errs.join(' | ').slice(0, 600));
await writeFile(join(out, 'qa.json'), JSON.stringify({ checks, errors: errs }, null, 1));
await browser.close(); server.close();
