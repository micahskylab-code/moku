import * as THREE from 'three';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { buildHouse } from './house.js';
import { buildSite } from './site.js';
import { makeDaySky, makeNightSky, dirFromAltAz } from './sky.js';
import { lamps } from './furniture.js';
import { mat, glow } from './materials.js';
import { inside, distToSeg, bounds } from './geom.js';
import { buildNeighborhood, siteLayout } from './neighborhood.js';
import { bakeShell } from './shell.js';

const EYE = 5.4, SPEED = 6, RADIUS = 0.85;
const params = new URLSearchParams(location.search);
const planId = params.get('plan') ?? 'lot25';
const viewId = params.get('view');
const shot = !!viewId || params.has('cam');
const night = params.get('time') === 'night';
// The live sky (src/daylight.js: real sun, moon, stars, weather, wind for any date and time) drives the
// interactive walkthrough, and any still that asks for it (?preset ?hst ?doy ?wx ?weather ?sunpath ?live).
// Fixed stills (?view, ?cam), the films (?video, ?starpass) and the Blender export keep the plan's fixed sun.
const dynamicSky = !params.has('export') && !params.has('starpass') && !params.get('video') &&
  (!shot || ['preset', 'hst', 'doy', 'wx', 'weather', 'sunpath', 'live', 'dyn'].some(k => params.has(k)));
const quality = params.get('q') ?? (shot ? 'high' : matchMedia('(pointer: coarse)').matches ? 'low' : 'high');

const plan = await (await fetch(`plans/${planId}.json`)).json();
document.title = plan.name;
document.getElementById('plan-name').textContent = plan.name;

const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: shot, powerPreference: 'high-performance' });
// ultra: supersampled, 8k shadows, denser AO — for a desktop GPU, and for stills (?q=ultra&ss=2)
const ultra = quality === 'ultra';
renderer.setPixelRatio(shot ? Number(params.get('ss') ?? 1) : Math.min(devicePixelRatio * (ultra ? 1.5 : 1), quality === 'low' ? 1.25 : ultra ? 3 : 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = night ? 1.25 : Number(params.get('exposure') ?? 0.58);
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.25, 40000);

const view = viewId ? plan.viewpoints.find(v => v.id === viewId) : null;
if (viewId && !view) throw new Error(`no viewpoint ${viewId}`);

// ---------- build ----------
// for the path tracer, palms are only recorded (position, size); Blender grows them leaf by leaf
if (params.has('export')) globalThis.__palmProxies = [];
const T0 = performance.now(), mark = s => params.has('timing') && console.warn(`[timing] ${s} ${(performance.now() - T0).toFixed(0)} ms`);
const { colliders, roofs, ceilingAt, group: houseGroup } = buildHouse(plan, scene);
mark('house');
const { terrainH } = buildSite(plan, scene, colliders);
mark('site');
let shellParts = null;
if (params.get('hood') !== '0') { shellParts = bakeShell(scene); mark('shell'); await buildNeighborhood(plan, scene, terrainH, shellParts).catch(e => console.warn('neighbourhood', e)); mark('neighbourhood'); }
const B = bounds(plan.rooms.map(r => r.polygon));
const cx = (B.minX + B.maxX) / 2, cz = (B.minY + B.maxY) / 2;

// ---------- export for the path tracer ----------
if (params.has('export')) {
  const { exportForBlender } = await import('./export.js');
  await exportForBlender({ scene, plan, terrainH, lamps, siteLayout, groundAt: (x, y) => plan.rooms.some(r => !r.label_only && inside([x, y], r.polygon)) ? 0 : terrainH(x, y) });
  document.body.dataset.ready = '1';
  throw new Error('exported');   // stop here; the page is only a converter in this mode
}

// ---------- light ----------
let nightSky = null, sun = null, daylight = null;
if (dynamicSky) {
  const { createDaylight } = await import('./daylight.js');
  daylight = await createDaylight({ scene, renderer, camera, plan, quality, north: siteLayout(plan).north, center: [cx, cz], terrainH, ceilingAt, lamps, glow, mat, params, shot });
  mark('daylight');
} else if (!night) {
  const [alt, az] = view?.sun ?? plan.sun ?? [50, 230];
  const { sunDir } = makeDaySky(scene, renderer, { sunAlt: alt, sunAz: az });
  sun = new THREE.DirectionalLight('#ffe9cf', 4.8);
  sun.position.set(cx + sunDir.x * 400, sunDir.y * 400, cz + sunDir.z * 400);
  sun.target.position.set(cx, 0, cz);
  sun.castShadow = true;
  const sm = quality === 'low' ? 2048 : ultra ? 8192 : 4096;
  sun.shadow.mapSize.set(sm, sm);
  Object.assign(sun.shadow.camera, { left: -110, right: 110, top: 110, bottom: -110, near: 50, far: 900 });
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.04; sun.shadow.radius = 3;
  scene.add(sun, sun.target);
  scene.add(new THREE.HemisphereLight('#e8eef5', '#a99b83', 0.12));
  const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
  const roomEnv = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(renderer), 0.04).texture;
  // Materials authored as interior (reflection < 1) see a neutral room, not the sky.
  scene.traverse(o => { if (!o.isMesh) return; for (const m of [].concat(o.material)) if (m.userData.interior && !m.envMap) { m.envMap = roomEnv; m.needsUpdate = true; } });
  scene.fog = new THREE.FogExp2('#c9dbe8', 0.000045);
} else {
  const date = new Date(params.get('date') ?? plan.night?.date ?? '2026-03-20T07:00:00Z');   // 9 pm HST, 19 March 2026, a day after new moon
  nightSky = await makeNightSky(scene, { date, north: siteLayout(plan).north });
  scene.background = new THREE.Color('#02040a');
  scene.add(new THREE.HemisphereLight('#2a3a5c', '#0d1208', 0.4));
  const moon = new THREE.DirectionalLight('#9fb6e0', 0.35);
  moon.position.copy(dirFromAltAz(35, 150).multiplyScalar(400)).add(new THREE.Vector3(cx, 0, cz)); moon.target.position.set(cx, 0, cz);
  scene.add(moon, moon.target);
  window.__neighborhood?.night();
  // Every lamp on; every indoor room glows warm through its glass.
  for (const l of lamps) l.intensity = l.userData.nightIntensity;
  glow.emissiveIntensity = 2.2;
  const lit = plan.rooms.filter(r => !r.label_only && (!r.outdoor || r.covered)).map(r => {
    const xs = r.polygon.map(p => p[0]), ys = r.polygon.map(p => p[1]);
    return { r, area: (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys)), xs, ys };
  }).sort((a, b) => b.area - a.area).slice(0, 8);
  for (const { xs, ys, area } of lit) {
    const x = (Math.min(...xs) + Math.max(...xs)) / 2, y = (Math.min(...ys) + Math.max(...ys)) / 2;
    const l = new THREE.PointLight('#ffc98a', Math.min(40, 6 + area / 12), Math.sqrt(area) * 2.4, 1.6);
    l.position.set(x, Math.min(ceilingAt(x, y) - 1.5, 9), y);
    scene.add(l);
  }
  // pool and spa glow
  const P = plan.site?.pool;
  if (P) {
    const [x0, y0, x1, y1] = P.rect;
    for (const t of [0.25, 0.75]) { const pl = new THREE.PointLight('#38d6ff', 60, 40, 1.4); pl.position.set(x0 + (x1 - x0) / 2, (plan.grade ?? -0.6) - 3, y0 + (y1 - y0) * t); scene.add(pl); }
    const w = mat('water'); w.emissive = new THREE.Color('#0c8fb5'); w.emissiveIntensity = 1.1; w.opacity = 0.85;
    mat('poolTile').emissive = new THREE.Color('#0a6a86'); mat('poolTile').emissiveIntensity = 0.5;
  }
  // landscape uplights on every palm trunk
  for (const p of (plan.site?.palms ?? []).filter(p => Math.hypot(p[0] - cx, p[1] - cz) < 70).slice(0, 8)) {
    const s = new THREE.SpotLight('#ffd7a0', 90, (p[2] ?? 30) + 12, 0.35, 0.6, 1.2);
    s.position.set(p[0] + 1.5, terrainH(p[0], p[1]) + 0.3, p[1] + 1.5);
    s.target.position.set(p[0], terrainH(p[0], p[1]) + (p[2] ?? 30), p[1]);
    scene.add(s, s.target);
  }
  scene.fog = new THREE.FogExp2('#05080f', 0.00012);
}

// ---------- post ----------
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
let aoPass = null;
if (quality !== 'low' && !(night && (params.get('video') || params.has('starpass')))) {
  const ao = aoPass = new GTAOPass(scene, camera, innerWidth, innerHeight);
  ao.updateGtaoMaterial({ radius: 2.2, distanceExponent: 1.5, thickness: 3, scale: 1.2, samples: ultra ? 24 : 16 });
  ao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16 });
  ao.blendIntensity = 1.0;
  composer.addPass(ao);
}
if (night) composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.55, 0.5, 0.82));
else if (daylight) { const b = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0, 0.5, 0.82); composer.addPass(b); daylight.bloom = b; }
composer.addPass(new OutputPass());
composer.addPass(new SMAAPass(innerWidth * renderer.getPixelRatio(), innerHeight * renderer.getPixelRatio()));

function render() {
  daylight?.beforeRender(camera);
  if (nightSky) { nightSky.group.position.copy(camera.position); nightSky.starMat.uniforms.uScale.value = renderer.getPixelRatio() * innerHeight / 1000; }
  composer.render();
}

// ---------- camera ----------
const player = camera.position;
function place(pos, look, eye = EYE, lookH = eye - 0.4) {
  const ground = groundAt(pos[0], pos[1]);
  player.set(pos[0], ground + eye, pos[1]);
  camera.lookAt(look[0], lookH ?? ground + eye - 0.4, look[1]);
}
function groundAt(x, y) {
  return plan.rooms.some(r => !r.label_only && inside([x, y], r.polygon)) ? 0 : terrainH(x, y);
}

window.__scene = { scene, camera, renderer, plan, render, nightSky, roofs, daylight };

if (shot) {
  document.body.classList.add('shot');
  if (view) {
    camera.fov = Number(params.get('fov') ?? view.fov ?? 70);
    camera.updateProjectionMatrix();
    const g = groundAt(view.pos[0], view.pos[1]);
    player.set(view.pos[0], view.absolute ? view.eye : g + (view.eye ?? EYE), view.pos[1]);
    camera.lookAt(view.look[0], view.lookH ?? (player.y - 0.4), view.look[1]);
  } else {
    // ?cam=x,y,height,lookX,lookY,lookHeight (absolute heights, ft)
    const [x, y, h, lx, ly, lh] = params.get('cam').split(',').map(Number);
    camera.fov = Number(params.get('fov') ?? 65); camera.updateProjectionMatrix();
    player.set(x, h, y); camera.lookAt(lx, lh, ly);
  }
  if (daylight) { daylight.sunPath.visible = params.has('sunpath') && params.get('sunpath') !== '0'; await daylight.ready(); }
  if (window.__beforeShot) window.__beforeShot();
  mark('pre-render'); render(); mark('render1'); render(); mark('render2');
  document.body.dataset.ready = '1';
} else if (params.has('starpass')) {
  // Star layer for the path-traced night film: only the sky, camera driven by blender/timeline.json
  document.body.classList.add('shot');
  const tl = await (await fetch('blender/timeline.json')).json();
  for (const c of scene.children) c.visible = c === nightSky.group;
  window.__frames = tl.frames.length;
  window.renderFrame = i => {
    const f = tl.frames[i];
    const dir = new THREE.Vector3(Math.cos(f.pitch) * Math.cos(f.yaw), Math.sin(f.pitch), Math.cos(f.pitch) * Math.sin(f.yaw));
    camera.position.set(0, 0, 0); camera.lookAt(dir);
    camera.fov = f.fov; camera.updateProjectionMatrix();
    nightSky.lines.material.opacity = f.lines;
    nightSky.starMat.uniforms.uTwinkle.value = f.twinkle;
    render(); return true;
  };
  window.renderFrame(0);
  document.body.dataset.ready = '1';
} else if (params.get('video')) {
  const { runVideo } = await import('./video.js');
  document.body.classList.add('shot');
  await runVideo({ params, camera, render, plan, nightSky, terrainH, renderer, composer });
} else {
  place(plan.start.pos, plan.start.look);
  await startInteractive();
}

async function startInteractive() {
  const keys = new Set();
  addEventListener('keydown', e => keys.add(e.code));
  addEventListener('keyup', e => keys.delete(e.code));
  const overlay = document.getElementById('overlay');
  const look = new PointerLockControls(camera, document.body);
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enabled = false; orbit.maxPolarAngle = Math.PI * 0.49; orbit.minDistance = 20; orbit.maxDistance = 9000; orbit.enableDamping = true;
  // model view (src/inspect.js): this one home to orbit, cut away or ghost, with selectable spaces and local questions
  const { createInspector } = await import('./inspect.js');
  const inspector = await createInspector({ planId, plan, scene, camera, renderer, orbit, house: houseGroup, ceilingAt, center: [cx, cz], aoPass, daylight }).catch(e => { console.warn('model view', e); return null; });
  const want = params.get('mode') ?? globalThis.__NAHIKU_MODE;   // index.html of a hosted copy may set the opening mode
  let mode = ['fly', 'model'].includes(want) && (want !== 'model' || inspector) ? want : 'walk';
  const btn = document.getElementById('mode'), modelBtn = document.getElementById('model');
  modelBtn.hidden = !inspector;
  const setMode = m => {
    if (mode === 'model' && m !== 'model') inspector.exit();
    mode = m; btn.textContent = m === 'fly' ? 'Walk in' : 'Fly over'; modelBtn.textContent = m === 'model' ? 'Exit model' : 'Model';
    orbit.enabled = m !== 'walk'; overlay.hidden = m !== 'walk';
    if (m === 'fly') { look.unlock(); orbit.target.set(cx, 0, cz); camera.position.set(cx - 160, 140, cz + 120); }
    else if (m === 'model') { look.unlock(); inspector.enter(); }
    else { place(plan.start.pos, plan.start.look); }
    daylight?.autoSunPath(m === 'fly');
  };
  btn.addEventListener('click', e => { e.stopPropagation(); setMode(mode === 'fly' ? 'walk' : 'fly'); });
  modelBtn.addEventListener('click', e => { e.stopPropagation(); setMode(mode === 'model' ? 'walk' : 'model'); });
  const timeBtn = document.getElementById('time');
  if (daylight) {
    // in-page: to the next great night for Na Hiku and back to daylight, no reload
    timeBtn.addEventListener('click', e => { e.stopPropagation(); if (daylight.isNight) daylight.toDay(); else daylight.preset('stars'); });
    daylight.onPreset = id => { if (mode === 'walk') turnTo(id); };
  } else {
    timeBtn.addEventListener('click', e => { e.stopPropagation(); const p = new URLSearchParams(location.search); p.set('time', night ? 'day' : 'night'); location.search = p; });
    timeBtn.textContent = night ? 'Day' : 'Night sky';
  }
  const qb = document.getElementById('quality'); qb.textContent = ultra ? 'Standard' : 'Ultra';
  qb.addEventListener('click', e => { e.stopPropagation(); const p = new URLSearchParams(location.search); p.set('q', ultra ? 'high' : 'ultra'); location.search = p; });
  overlay.addEventListener('click', () => { if (!matchMedia('(pointer: coarse)').matches) look.lock(); else overlay.hidden = true; });
  look.addEventListener('lock', () => (overlay.hidden = true));
  look.addEventListener('unlock', () => (overlay.hidden = mode !== 'walk'));
  setMode(mode);

  const touch = { move: null, look: null };
  addEventListener('touchstart', e => { if (mode !== 'walk') return; for (const t of e.changedTouches) { const s = t.clientX < innerWidth / 2 ? 'move' : 'look'; touch[s] = { id: t.identifier, x0: t.clientX, y0: t.clientY, x: t.clientX, y: t.clientY }; } }, { passive: true });
  addEventListener('touchmove', e => {
    if (mode !== 'walk') return;
    for (const t of e.changedTouches) for (const s of ['move', 'look']) {
      const T = touch[s]; if (T?.id !== t.identifier) continue;
      if (s === 'look') {
        const eu = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
        eu.y -= (t.clientX - T.x) * 0.005; eu.x = Math.max(-1.4, Math.min(1.4, eu.x - (t.clientY - T.y) * 0.005));
        camera.quaternion.setFromEuler(eu);
      }
      T.x = t.clientX; T.y = t.clientY;
    }
  }, { passive: true });
  addEventListener('touchend', e => { for (const t of e.changedTouches) for (const s of ['move', 'look']) if (touch[s]?.id === t.identifier) touch[s] = null; });

  const minimap = setupMinimap((x, y) => mode === 'model' && inspector.selectAt(x, y));
  const label = document.getElementById('room');
  const clock = new THREE.Clock(), fwd = new THREE.Vector3(), right = new THREE.Vector3();
  // after a sky preset, outdoors, turn smoothly toward the sun, the moon or Na Hiku
  let turn = null;
  function turnTo(id) {
    const room = plan.rooms.find(rm => inside([player.x, player.z], rm.polygon));
    if (room && !room.outdoor) return;
    const L = daylight.target(id);
    if (!L) return;
    const eu = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
    const yaw = Math.atan2(-L[0], -L[2]), pitch = Math.max(-0.1, Math.min(0.75, Math.asin(L[1]) * 0.7));
    let dy = yaw - eu.y; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
    turn = { y0: eu.y, dy, p0: eu.x, p1: pitch, t: 0 };
  }
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.05);
    if (nightSky) nightSky.starMat.uniforms.uTwinkle.value += dt;
    if (daylight) {
      daylight.update(dt);
      timeBtn.textContent = daylight.isNight ? 'Day' : 'Night sky';
      if (turn && mode === 'walk') {
        turn.t = Math.min(1, turn.t + dt / 1.6); const k = turn.t * turn.t * (3 - 2 * turn.t);
        camera.quaternion.setFromEuler(new THREE.Euler(turn.p0 + (turn.p1 - turn.p0) * k, turn.y0 + turn.dy * k, 0, 'YXZ'));
        if (turn.t >= 1) turn = null;
      }
    }
    if (mode === 'fly') { orbit.update(); label.textContent = 'Nā Hiku · Kukuiʻula'; render(); return; }
    if (mode === 'model') { orbit.update(); inspector.update(dt); label.textContent = inspector.title(); minimap(null, camera, inspector.selectedPolygon()); render(); return; }
    let f = (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0);
    let r = (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0) - (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0);
    if (touch.move) { f = Math.max(-1, Math.min(1, -(touch.move.y - touch.move.y0) / 60)); r = Math.max(-1, Math.min(1, (touch.move.x - touch.move.x0) / 60)); }
    const speed = SPEED * (keys.has('ShiftLeft') ? 1.8 : 1);
    camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize(); right.crossVectors(fwd, camera.up);
    const dx = (fwd.x * f + right.x * r) * speed * dt, dz = (fwd.z * f + right.z * r) * speed * dt;
    if (!blocked(player.x + dx, player.z)) player.x += dx;
    if (!blocked(player.x, player.z + dz)) player.z += dz;
    const target = groundAt(player.x, player.z) + EYE;
    player.y += (target - player.y) * Math.min(1, dt * 8);
    const room = plan.rooms.find(rm => inside([player.x, player.z], rm.polygon));
    label.textContent = room?.name ?? 'Outside';
    minimap(player, camera);
    render();
  });
}

function blocked(x, z) { for (const { a, b } of colliders) if (distToSeg(x, z, a, b) < RADIUS) return true; return false; }

function setupMinimap(pick) {
  const c = document.getElementById('minimap'), ctx = c.getContext('2d');
  const pad = 10, W = c.width, H = c.height;
  // north (+x) up on the map
  const s = Math.min((W - 2 * pad) / (B.maxY - B.minY), (H - 2 * pad) / (B.maxX - B.minX));
  const tx = (x, y) => pad + (y - B.minY) * s, ty = (x, y) => H - pad - (x - B.minX) * s;
  c.addEventListener('click', e => {
    const rect = c.getBoundingClientRect(), mx = (e.clientX - rect.left) * W / rect.width, my = (e.clientY - rect.top) * H / rect.height;
    const y = B.minY + (mx - pad) / s, x = B.minX + (H - pad - my) / s;
    if (pick?.(x, y)) return;
    if (!blocked(x, y)) { player.x = x; player.z = y; }
  });
  return (p, cam, highlight) => {
    ctx.clearRect(0, 0, W, H);
    for (const r of plan.rooms) {
      if (r.label_only) continue;
      ctx.beginPath(); r.polygon.forEach(([x, y], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, tx(x, y), ty(x, y))); ctx.closePath();
      ctx.fillStyle = r.outdoor ? 'rgba(160,140,110,.35)' : 'rgba(255,255,255,.6)'; ctx.fill();
    }
    if (highlight) {
      ctx.beginPath(); highlight.forEach(([x, y], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, tx(x, y), ty(x, y))); ctx.closePath();
      ctx.fillStyle = 'rgba(240,180,41,.75)'; ctx.fill();
    }
    ctx.strokeStyle = '#2a2a2a'; ctx.lineWidth = 1.5;
    for (const { a, b } of colliders) { ctx.beginPath(); ctx.moveTo(tx(...a), ty(...a)); ctx.lineTo(tx(...b), ty(...b)); ctx.stroke(); }
    if (!p) return;
    const d = new THREE.Vector3(); cam.getWorldDirection(d);
    ctx.fillStyle = ctx.strokeStyle = '#d0452f';
    ctx.beginPath(); ctx.arc(tx(p.x, p.z), ty(p.x, p.z), 4, 0, 7); ctx.fill();
    ctx.beginPath(); ctx.moveTo(tx(p.x, p.z), ty(p.x, p.z)); ctx.lineTo(tx(p.x + d.x * 5, p.z + d.z * 5), ty(p.x + d.x * 5, p.z + d.z * 5)); ctx.lineWidth = 2; ctx.stroke();
  };
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight);
});
