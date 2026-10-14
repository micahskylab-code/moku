// Load a view and evaluate a JS expression in the page (debugging aid).
// Usage: node scripts/eval.mjs "<query>" "<expression>"
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('/opt/node22/lib/node_modules/playwright');
const root = new URL('..', import.meta.url).pathname;
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = createServer(async (req, res) => { const p = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)); const f = p === '/' ? '/index.html' : p; try { res.writeHead(200, { 'content-type': types[extname(f)] ?? 'application/octet-stream' }).end(await readFile(join(root, f))); } catch { res.writeHead(404).end(); } }).listen(0);
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await b.newPage({ viewport: { width: 800, height: 500 } });
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto(`http://localhost:${server.address().port}/?${process.argv[2]}`);
await page.waitForSelector('body[data-ready="1"]', { timeout: 600000 });
console.log(JSON.stringify(await page.evaluate(process.argv[3]), null, 1));
await b.close(); server.close();
