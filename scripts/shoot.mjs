// Renders viewpoints to shots/<plan>/<view>.png for the critic to compare with the reference images.
// Usage: node scripts/shoot.mjs <plan-id> [view-id ...] [--night] [--w=1600 --h=1000] [--q=a=1&b=2]
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const root = new URL('..', import.meta.url).pathname;
const args = process.argv.slice(2);
const flag = (k, d) => (args.find(a => a.startsWith(`--${k}=`)) ?? `=${d}`).split('=').slice(1).join('=');
const night = args.includes('--night');
const pos = args.filter(a => !a.startsWith('--'));
const planId = pos[0] ?? 'lot25';
const plan = JSON.parse(await readFile(join(root, 'plans', `${planId}.json`), 'utf8'));
const only = pos.slice(1);
const views = only.length ? only.map(id => plan.viewpoints.find(v => v.id === id) ?? { id, cam: id }) : plan.viewpoints;
const W = Number(flag('w', 1600)), H = Number(flag('h', 1000)), extra = flag('q', '');

const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = path === '/' ? '/index.html' : path;
  try { res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }).end(await readFile(join(root, file))); }
  catch { res.writeHead(404).end(); }
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('pageerror', e => console.error('page error:', e.message));
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('console:', m.text().slice(0, 300)); });
const out = join(root, 'shots', planId);
await mkdir(out, { recursive: true });
for (const v of views) {
  const q = v.cam ? `cam=${v.cam}` : `view=${v.id}`;
  const t0 = Date.now();
  await page.goto(`http://localhost:${port}/?plan=${planId}&${q}${night ? '&time=night' : ''}${extra ? '&' + extra : ''}`);
  await page.waitForSelector('body[data-ready="1"]', { timeout: 600000 });
  const name = (v.cam ? 'cam-' + v.cam.replace(/[^0-9.-]+/g, '_') : v.id) + (night ? '-night' : '');
  await page.screenshot({ path: join(out, `${name}.png`) });
  console.log(`shots/${planId}/${name}.png  ${((Date.now() - t0) / 1000).toFixed(1)}s${v.photo ? `  vs  ${v.photo}` : ''}`);
}
await browser.close();
server.close();
