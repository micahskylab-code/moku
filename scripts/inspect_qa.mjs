// QA for the model view (src/inspect.js): screenshots of the three displays and the panels, picking, questions
// saved / reloaded / exported, the phone layout, the walk <-> model round trip, console errors and every network
// request (the questions must never leave the browser). Usage: node scripts/inspect_qa.mjs [out-dir]
// Writes <out>/*.png, <out>/qa.json, <out>/spaces.json, <out>/questions-export.json.
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const root = new URL('..', import.meta.url).pathname;
const out = process.argv[2] ?? join(root, 'shots', 'model-view');
await mkdir(out, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = path === '/' ? '/index.html' : path;
  try { res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }).end(await readFile(join(root, file))); }
  catch { res.writeHead(404).end(); }
}).listen(0);
const base = `http://localhost:${server.address().port}/`;
// a fixed sky and simulated weather (21 Jun 10:30 HST, partly cloudy): the shots repeat and the live-weather
// request (src/weather.js, Open-Meteo) stays out of the network check
const SKY = 'q=low&live=0&wx=partly&doy=172&hst=10:30';

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, acceptDownloads: true });
const requests = [], errors = [], checks = [];
const watch = page => {
  page.setDefaultTimeout(900000);
  page.on('request', r => requests.push(r.url()));
  page.on('pageerror', e => errors.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text().slice(0, 300)}`); });
};
const check = (name, ok, detail = '') => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` - ${detail}` : ''}`); };
const frames = (page, n = 3) => page.evaluate(n => new Promise(res => { let k = 0; const f = () => (++k >= n ? res() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);
const ready = async page => { await page.waitForFunction(() => window.__inspect?.active, null, { timeout: 900000 }); await frames(page, 4); };
const settle = page => page.waitForFunction(() => window.__inspect.settled(), null, { timeout: 600000, polling: 250 });
const shot = async (page, name) => { await settle(page); await frames(page, 3); await page.screenshot({ path: join(out, `${name}.png`) }); console.log('shot', name); };
const state = page => page.evaluate(() => window.__inspect.state());

const t0 = Date.now();
const page = await ctx.newPage(); watch(page);
await page.goto(`${base}?mode=model&${SKY}`);
await ready(page);
console.log(`loaded in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
check('model view opens from ?mode=model', (await state(page)).display === 'exterior');
check('concept label visible', /Concept visualization/.test(await page.textContent('#concept')));
check('overview card lists stated areas', /2,300 sq ft/.test(await page.textContent('#inspect')));
await writeFile(join(out, 'spaces.json'), JSON.stringify(await page.evaluate(() => window.__inspect.table()), null, 1));
await shot(page, '1-exterior-overview');

// picking: close the panel, click the projected centre of Bedroom 2's floor (through the roof)
await page.click('#inspect .ic-close'); await frames(page, 2); await settle(page);
const pt = await page.evaluate(() => window.__inspect.screenOf('bed2'));
await page.mouse.click(pt.x, pt.y); await frames(page, 2);
check('click on the model selects the space under the pointer', (await state(page)).selected === 'bed2', JSON.stringify(pt));
await shot(page, '2-exterior-bed2-selected');

// cutaway through the UI button, the great room selected
await page.click('#modelbar [data-display=cutaway]');
await page.evaluate(() => window.__inspect.select('great'));
const cs = await state(page);
check('cutaway display', cs.display === 'cutaway' && cs.selected === 'great' && !cs.trees);
check('URL carries display and space', /display=cutaway/.test(page.url()) && /space=great/.test(page.url()), page.url());
check('space panel has no stray text', !/null|undefined|\[object /.test(await page.textContent('#inspect')));
await shot(page, '3-cutaway-great-room');

// translucent, the primary suite
await page.click('#modelbar [data-display=translucent]');
await page.evaluate(() => window.__inspect.select('primary'));
await shot(page, '4-translucent-primary');

// questions: kitchen in cutaway, "Ask" next to an estimate/assumption, then a typed line, then save
await page.click('#modelbar [data-display=cutaway]');
await page.evaluate(() => window.__inspect.select('kitchen'));
check('kitchen card shows the p6 appliance labels', /36″ REF/.test(await page.textContent('#inspect')));
await page.click('#inspect .ic-ask');
await page.click('#inspect textarea'); await page.keyboard.press('End');
await page.keyboard.type('\nIs the 36" refrigerator included, and which model?');
await page.click('#inspect button.primary');
const qs = await page.evaluate(() => window.__inspect.questions());
check('question saved with space, display and camera', qs.length === 1 && qs[0].space.id === 'kitchen' && qs[0].display === 'cutaway' && qs[0].camera.position.length === 3, qs[0]?.text);
await shot(page, '5-cutaway-kitchen-question');

// a draft (not saved) survives a reload, and so does the saved question
await page.evaluate(() => window.__inspect.select('bed3'));
await page.fill('#inspect textarea', 'Draft: can bedroom 3 take a king bed with two nightstands?');
await page.waitForTimeout(600);
await page.reload(); await ready(page);
const after = await page.evaluate(() => ({ s: window.__inspect.state(), n: window.__inspect.questions().length, draft: document.querySelector('#inspect textarea')?.value }));
check('reload restores display, space, saved questions and the draft', after.s.display === 'cutaway' && after.s.selected === 'bed3' && after.n === 1 && /king bed/.test(after.draft ?? ''), JSON.stringify(after));

// the questions panel and a local export
await page.click('#modelbar button:has-text("Questions")');
const panel = await page.textContent('#inspect');
check('questions panel lists the saved question under its space', /Kitchen/.test(panel) && /36" refrigerator included/.test(panel) && !/\[object /.test(panel));
await shot(page, '6-questions-panel');
const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#inspect button:has-text("Export JSON")')]);
const file = join(out, 'questions-export.json'); await dl.saveAs(file);
const doc = JSON.parse(await readFile(file, 'utf8'));
check('export is a local JSON file with the question and the concept label', doc.format === 'nahiku-questions/1' && doc.questions.length === 1 && /Concept visualization/.test(doc.label), dl.suggestedFilename());

// walk <-> model round trip: the other homes and the materials come back
await page.goto(`${base}?${SKY}`);
await page.waitForFunction(() => window.__inspect && !document.getElementById('model').hidden, null, { timeout: 900000 });
await frames(page, 2);
await page.click('#model'); await frames(page, 2);
const inModel = await page.evaluate(() => ({ a: window.__inspect.active, homes: window.__neighborhood?.homes?.visible }));
await page.click('#model'); await frames(page, 2);
const back = await page.evaluate(() => {
  let ghost = 0, clipped = 0;
  window.__scene.scene.traverse(o => { if (!o.isMesh) return; for (const m of [].concat(o.material)) { if (m.clippingPlanes?.length) clipped++; } });
  window.__scene.scene.getObjectByName('inspect')?.traverse(o => { if (o.isMesh && o.visible) ghost++; });
  return { a: window.__inspect.active, homes: window.__neighborhood?.homes?.visible, clipped, visibleHighlights: ghost, url: location.search, button: document.getElementById('model').textContent };
});
check('Model button enters, hides the other homes', inModel.a && inModel.homes === false, JSON.stringify(inModel));
check('Exit model restores homes, materials and URL', !back.a && back.homes !== false && back.clipped === 0 && back.visibleHighlights === 0 && !/mode=model/.test(back.url) && back.button === 'Model', JSON.stringify(back));
await page.close();

// phone layout: bottom sheet, cutaway, Bedroom 2
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
const mp = await phone.newPage(); watch(mp);
await mp.goto(`${base}?mode=model&display=cutaway&space=bed2&${SKY}`);
await ready(mp);
const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > innerWidth || [...document.querySelectorAll('#modelbar button, #buttons button')].some(b => b.getBoundingClientRect().right > innerWidth + 0.5));
check('phone: nothing overflows the width', !overflow);
await shot(mp, '7-phone-cutaway-bed2');
await phone.close();

const hosts = [...new Set(requests.map(u => new URL(u).host))];
check('no request leaves localhost', hosts.every(h => h.startsWith('localhost')), hosts.join(', '));
check('no page or console errors', !errors.length, errors.slice(0, 5).join(' | '));
await writeFile(join(out, 'qa.json'), JSON.stringify({ when: new Date().toISOString(), seconds: Math.round((Date.now() - t0) / 1000), checks, hosts, errors, requests: requests.length }, null, 1));
console.log(`${checks.filter(c => c.ok).length}/${checks.length} checks passed`);
await browser.close(); server.close();
