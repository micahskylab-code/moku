// Records a short clip of the model view (src/inspect.js): the exterior turning, then the cutaway with the great
// room selected, then the translucent display with the primary suite, in fixed camera steps (deterministic, so
// it works under software WebGL). Usage: node scripts/inspect_demo.mjs [out-dir]  ->  <out>/model-view-demo.mp4
import { createServer } from 'node:http';
import { readFile, mkdir, rm } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }
const root = new URL('..', import.meta.url).pathname;
const out = process.argv[2] ?? join(root, 'shots', 'model-view');
const dir = join(out, 'demo-frames');
await rm(dir, { recursive: true, force: true }); await mkdir(dir, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = path === '/' ? '/index.html' : path;
  try { res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }).end(await readFile(join(root, file))); }
  catch { res.writeHead(404).end(); }
}).listen(0);
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.setDefaultTimeout(900000);
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto(`http://localhost:${server.address().port}/?mode=model&q=low&live=0&wx=partly&doy=172&hst=10:30`);
await page.waitForFunction(() => window.__inspect?.active, null, { timeout: 900000 });
const frames = n => page.evaluate(n => new Promise(r => { let k = 0; const f = () => (++k >= n ? r() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);
const settle = () => page.waitForFunction(() => window.__inspect.settled(), null, { polling: 250 });
let i = 0;
const grab = async () => { await frames(1); await page.screenshot({ path: join(dir, `f${String(i++).padStart(4, '0')}.png`) }); };
const hold = async n => { await settle(); await frames(2); for (let k = 0; k < n; k++) await grab(); };
const spin = async (n, deg) => { for (let k = 0; k < n; k++) { await page.evaluate(r => window.__inspect.turn(r), deg * Math.PI / 180); await grab(); } };

await frames(4);
await hold(8); await spin(30, 2);                                                      // exterior, overview card
await page.click('#modelbar [data-display=cutaway]'); await hold(6);
await page.evaluate(() => window.__inspect.select('great')); await hold(10); await spin(30, 2);
await page.click('#modelbar [data-display=translucent]'); await hold(6);
await page.evaluate(() => window.__inspect.select('primary')); await hold(10); await spin(30, 2);
await page.click('#modelbar [data-display=exterior]'); await hold(10);
console.log(`${i} frames`);
await browser.close(); server.close();
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '12', '-i', join(dir, 'f%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', join(out, 'model-view-demo.mp4')]);
console.log('wrote', join(out, 'model-view-demo.mp4'));
