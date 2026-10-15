// Renders a camera timeline frame by frame and encodes an MP4.
// Usage: node scripts/video.mjs <plan-id> <video-name> [--w=1920 --h=1080 --fps=24 --seconds=18 --frames=a-b]
// Needs an ffmpeg binary: $FFMPEG, or `pip install imageio-ffmpeg`.
import { createServer } from 'node:http';
import { readFile, mkdir, rm } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const root = new URL('..', import.meta.url).pathname;
const args = process.argv.slice(2), pos = args.filter(a => !a.startsWith('--'));
const flag = (k, d) => (args.find(a => a.startsWith(`--${k}=`)) ?? `=${d}`).split('=').slice(1).join('=');
const planId = pos[0] ?? 'lot25', name = pos[1] ?? 'night';
const W = Number(flag('w', 1920)), H = Number(flag('h', 1080)), fps = Number(flag('fps', 24)), seconds = Number(flag('seconds', 16));

const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = createServer(async (req, res) => {
  const p = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)), f = p === '/' ? '/index.html' : p;
  try { res.writeHead(200, { 'content-type': types[extname(f)] ?? 'application/octet-stream' }).end(await readFile(join(root, f))); } catch { res.writeHead(404).end(); }
}).listen(0);

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.setDefaultTimeout(1800000);
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto(`http://localhost:${server.address().port}/?plan=${planId}&video=${name}&time=${name === 'night' ? 'night' : 'day'}&fps=${fps}&seconds=${seconds}`);
await page.waitForSelector('body[data-ready="1"]', { timeout: 900000 });
const frames = await page.evaluate(() => window.__frames);
const dir = join(root, 'shots', `${name}-frames`);
const [a, b] = flag('frames', `0-${frames - 1}`).split('-').map(Number);
if (a === 0) await rm(dir, { recursive: true, force: true });
await mkdir(dir, { recursive: true });
const t0 = Date.now();
const step = Number(flag('step', 1));
for (let i = a; i <= b; i += step) {
  await page.evaluate(i => window.renderFrame(i), i);
  await page.screenshot({ path: join(dir, `f${String(i).padStart(5, '0')}.png`) });
  if (i % 24 === 0) console.log(`frame ${i}/${frames}  ${((Date.now() - t0) / 1000 / (i - a + 1)).toFixed(2)} s/frame`);
}
await browser.close(); server.close();

if (b === frames - 1 && step === 1) {
  let ff = process.env.FFMPEG;
  if (!ff) ff = execFileSync('python3', ['-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim();
  const out = join(root, 'shots', `${planId}-${name}.mp4`);
  execFileSync(ff, ['-y', '-framerate', String(fps), '-i', join(dir, 'f%05d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow', '-movflags', '+faststart', out], { stdio: 'inherit' });
  console.log('wrote', out);
}
