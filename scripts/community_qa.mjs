// Screens of the community view (src/community.js): the opening flight, the whole community, the coast, the home.
// Usage: node scripts/community_qa.mjs [out-dir] [query]   (fixed sky: 21 Jun 09:15 HST, clear trades)
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
const SKY = 'q=high&live=0&wx=clear&doy=172&hst=09:15';
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
check('disclaimer visible', /not an aerial photograph/.test(await page.textContent('#community .cm-fine')));
await frames(2);
await page.screenshot({ path: join(out, '0-opening.png') });   // the opening frame, before the flight in (512 px tiles)
const poses = {
  '1-establishing': `C.establishing()`,
  '2-overview': `C.overview()`,
  '3-home-close': `C.pose(C.pins[0].ground, 900, 0.95, C.northAz - 0.6)`,
  '4-coast': `(() => { const [x, z] = C.fromLatLon(21.8846, -159.4925); const g = new (C.pins[0].ground.constructor)(x, C.groundAt(x, z), z); return C.pose(g, 2400, 1.05, C.northAz + 0.4); })()`,
  '5-golf-oblique': `(() => { const [x, z] = C.fromLatLon(21.8925, -159.4850); const g = new (C.pins[0].ground.constructor)(x, C.groundAt(x, z), z); return C.pose(g, 3200, 1.18, C.northAz + 2.6); })()`,
};
const only = process.env.SHOTS ? process.env.SHOTS.split(',') : null;   // e.g. SHOTS=1,3 for a quick pass
for (const [name, expr] of Object.entries(poses)) {
  if (only && !only.some(k => name.startsWith(k))) continue;
  await page.evaluate(e => { const C = window.__community; C.jump(eval(e)); }, expr);
  await frames(3);
  await shot(name);
}
const errs = errors.filter(e => !/GPU stall|swiftshader|WebGL: INVALID_ENUM|Automatic fallback/i.test(e));
check('no page errors', !errs.some(e => e.startsWith('pageerror')), errs.join(' | ').slice(0, 600));
await writeFile(join(out, 'qa.json'), JSON.stringify({ checks, errors: errs }, null, 1));
await browser.close(); server.close();
