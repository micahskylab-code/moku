// Renders the star layer for every frame of blender/timeline.json to blender/stars/.
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('/opt/node22/lib/node_modules/playwright');
const root = new URL('..', import.meta.url).pathname;
const [W, H] = (process.argv[2] ?? '1920x1080').split('x').map(Number);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = createServer(async (req, res) => { const p = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)), f = p === '/' ? '/index.html' : p; try { res.writeHead(200, { 'content-type': types[extname(f)] ?? 'application/octet-stream' }).end(await readFile(join(root, f))); } catch { res.writeHead(404).end(); } }).listen(0);
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.setDefaultTimeout(1800000);
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto(`http://localhost:${server.address().port}/?plan=lot25&time=night&starpass=1&hood=0`);
await page.waitForSelector('body[data-ready="1"]');
const n = await page.evaluate(() => window.__frames), out = join(root, 'blender', 'stars');
await mkdir(out, { recursive: true });
for (let i = 0; i < n; i++) {
  await page.evaluate(i => window.renderFrame(i), i);
  await page.screenshot({ path: join(out, `s${String(i).padStart(5, '0')}.png`) });
  if (i % 48 === 0) console.log('stars', i, '/', n);
}
await browser.close(); server.close();
