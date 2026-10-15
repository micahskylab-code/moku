// Runs the page in export mode and saves nahiku.glb + nahiku-meta.json to blender/ (or the dir given).
//   node scripts/export.mjs lot25 [out_dir]
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('/opt/node22/lib/node_modules/playwright');
const root = new URL('..', import.meta.url).pathname;
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = createServer(async (req, res) => { const p = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)), f = p === '/' ? '/index.html' : p; try { res.writeHead(200, { 'content-type': types[extname(f)] ?? 'application/octet-stream' }).end(await readFile(join(root, f))); } catch { res.writeHead(404).end(); } }).listen(0);
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 640, height: 400 }, acceptDownloads: true });
page.setDefaultTimeout(1800000);
page.on('pageerror', e => { if (!/exported/.test(e.message)) console.error('page error:', e.message); });
const out = process.argv[3] ? normalize(process.argv[3]) : join(root, 'blender'); await mkdir(out, { recursive: true });
const downloads = [];
page.on('download', d => downloads.push(d.saveAs(join(out, d.suggestedFilename())).then(() => console.log('saved', d.suggestedFilename()))));
await page.goto(`http://localhost:${server.address().port}/?plan=${process.argv[2] ?? 'lot25'}&export=1`);
await page.waitForSelector('body[data-ready="1"]');
while (downloads.length < 2) await new Promise(r => setTimeout(r, 500));
await Promise.all(downloads);
await browser.close(); server.close();
