// Renders every viewpoint in a plan to shots/<plan>/<view>.png for the critic to compare with the photos.
// Usage: node scripts/shoot.mjs <plan-id> [view-id ...]
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); }
catch { ({ chromium } = require(join(process.execPath, '../../lib/node_modules/playwright'))); }

const root = new URL('..', import.meta.url).pathname;
const planId = process.argv[2] ?? 'test-plan';
const plan = JSON.parse(await readFile(join(root, 'plans', `${planId}.json`), 'utf8'));
const only = process.argv.slice(3);
const views = plan.viewpoints.filter(v => !only.length || only.includes(v.id));

const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = path === '/' ? '/index.html' : path;
  try {
    const body = await readFile(join(root, file));
    res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }).end(body);
  } catch { res.writeHead(404).end(); }
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
page.on('pageerror', e => console.error('page error:', e.message));
const out = join(root, 'shots', planId);
await mkdir(out, { recursive: true });
for (const v of views) {
  await page.goto(`http://localhost:${port}/?plan=${planId}&view=${v.id}${v.fov ? `&fov=${v.fov}` : ''}`);
  await page.waitForSelector('body[data-ready="1"]', { timeout: 60000 });
  await page.screenshot({ path: join(out, `${v.id}.png`) });
  console.log(`shots/${planId}/${v.id}.png${v.photo ? `  vs  ${v.photo}` : ''}`);
}
await browser.close();
server.close();
