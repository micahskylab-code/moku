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
import { buildNeighborhood } from './neighborhood.js';

const EYE = 5.4, SPEED = 6, RADIUS = 0.85;
const params = new URLSearchParams(location.search);
const planId = params.get('plan') ?? 'lot25';
const viewId = params.get('view');
const shot = !!viewId || params.has('cam');
const night = params.get('time') === 'night';
const quality = params.get('q') ?? (shot ? 'high' : matchMedia('(pointer: coarse)').matches ? 'low' : 'high');

const plan = await (await fetch(`plans/${planId}.json`)).json();
document.title = plan.name;
document.getElementById('plan-name').textContent = plan.name;

const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: shot, powerPreference: 'high-performance' });
renderer.setPixelRatio(shot ? 1 : Math.min(devicePixelRatio, quality === 'low' ? 1.25 : 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = night ? 1.4 : Number(params.get('exposure') ?? 0.58);
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.25, 40000);

const view = viewId ? plan.viewpoints.find(v => v.id === viewId) : null;
if (viewId && !view) throw new Error(`no viewpoint ${viewId}`);

// ---------- build ----------
const { colliders, roofs, ceilingAt } = buildHouse(plan, scene);
const { terrainH } = buildSite(plan, scene, colliders);
if (params.get('hood') !== '0') await buildNeighborhood(plan, scene, terrainH).catch(e => console.warn('neighbourhood', e));
const B = bounds(plan.rooms.map(r => r.polygon));
const cx = (B.minX + B.maxX) / 2, cz = (B.minY + B.maxY) / 2;

// ---------- light ----------
let nightSky = null, sun = null;
if (!night) {
  const [alt, az] = view?.sun ?? plan.sun ?? [50, 230];
  const { sunDir } = makeDaySky(scene, renderer, { sunAlt: alt, sunAz: az });
  sun = new THREE.DirectionalLight('#fff1dc', 4.0);
  sun.position.set(cx + sunDir.x * 400, sunDir.y * 400, cz + sunDir.z * 400);
  sun.target.position.set(cx, 0, cz);
  sun.castShadow = true;
  sun.shadow.mapSize.set(quality === 'low' ? 2048 : 4096, quality === 'low' ? 2048 : 4096);
  Object.assign(sun.shadow.camera, { left: -110, right: 110, top: 110, bottom: -110, near: 50, far: 900 });
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.04; sun.shadow.radius = 3;
  scene.add(sun, sun.target);
  scene.add(new THREE.HemisphereLight('#e8eef5', '#a99b83', 0.2));
  const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
  const roomEnv = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(renderer), 0.04).texture;
  // Materials authored as interior (reflection < 1) see a neutral room, not the sky.
  scene.traverse(o => { if (!o.isMesh) return; for (const m of [].concat(o.material)) if (m.userData.interior && !m.envMap) { m.envMap = roomEnv; m.needsUpdate = true; } });
  scene.fog = new THREE.FogExp2('#c9dbe8', 0.000045);
} else {
  const date = new Date(params.get('date') ?? plan.night?.date ?? '2026-03-20T07:15:00Z');
  nightSky = await makeNightSky(scene, { date });
  scene.background = new THREE.Color('#02040a');
  scene.add(new THREE.HemisphereLight('#2a3a5c', '#0d1208', 0.55));
  const moon = new THREE.DirectionalLight('#9fb6e0', 0.35);
  moon.position.copy(dirFromAltAz(35, 150).multiplyScalar(400)).add(new THREE.Vector3(cx, 0, cz)); moon.target.position.set(cx, 0, cz);
  scene.add(moon, moon.target);
  // Every lamp on; every indoor room glows warm through its glass.
  for (const l of lamps) l.intensity = l.userData.nightIntensity;
  glow.emissiveIntensity = 2.2;
  for (const r of plan.rooms.filter(r => !r.label_only && (!r.outdoor || r.covered))) {
    const xs = r.polygon.map(p => p[0]), ys = r.polygon.map(p => p[1]);
    const x = (Math.min(...xs) + Math.max(...xs)) / 2, y = (Math.min(...ys) + Math.max(...ys)) / 2;
    const area = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
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
  for (const p of plan.site?.palms ?? []) {
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
if (quality !== 'low') {
  const ao = new GTAOPass(scene, camera, innerWidth, innerHeight);
  ao.updateGtaoMaterial({ radius: 1.6, distanceExponent: 1.5, thickness: 3, scale: 1.2, samples: 16 });
  ao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16 });
  ao.blendIntensity = 0.85;
  composer.addPass(ao);
}
if (night) composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.55, 0.5, 0.82));
composer.addPass(new OutputPass());
composer.addPass(new SMAAPass(innerWidth * renderer.getPixelRatio(), innerHeight * renderer.getPixelRatio()));

function render() {
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

window.__scene = { scene, camera, renderer, plan, render, nightSky, roofs };

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
  if (window.__beforeShot) window.__beforeShot();
  render(); render();
  document.body.dataset.ready = '1';
} else if (params.get('video')) {
  const { runVideo } = await import('./video.js');
  document.body.classList.add('shot');
  await runVideo({ params, camera, render, plan, nightSky, terrainH, renderer, composer });
} else {
  place(plan.start.pos, plan.start.look);
  startInteractive();
}

function startInteractive() {
  const keys = new Set();
  addEventListener('keydown', e => keys.add(e.code));
  addEventListener('keyup', e => keys.delete(e.code));
  const overlay = document.getElementById('overlay');
  const look = new PointerLockControls(camera, document.body);
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enabled = false; orbit.maxPolarAngle = Math.PI * 0.49; orbit.minDistance = 20; orbit.maxDistance = 9000; orbit.enableDamping = true;
  let mode = params.get('mode') === 'fly' ? 'fly' : 'walk';
  const btn = document.getElementById('mode');
  const setMode = m => {
    mode = m; btn.textContent = m === 'walk' ? 'Fly over' : 'Walk in';
    orbit.enabled = m === 'fly'; overlay.hidden = m === 'fly';
    if (m === 'fly') { look.unlock(); orbit.target.set(cx, 0, cz); camera.position.set(cx - 160, 140, cz + 120); }
    else { place(plan.start.pos, plan.start.look); }
  };
  btn.addEventListener('click', e => { e.stopPropagation(); setMode(mode === 'walk' ? 'fly' : 'walk'); });
  document.getElementById('time').addEventListener('click', e => { e.stopPropagation(); const p = new URLSearchParams(location.search); p.set('time', night ? 'day' : 'night'); location.search = p; });
  document.getElementById('time').textContent = night ? 'Day' : 'Night sky';
  overlay.addEventListener('click', () => { if (!matchMedia('(pointer: coarse)').matches) look.lock(); else overlay.hidden = true; });
  look.addEventListener('lock', () => (overlay.hidden = true));
  look.addEventListener('unlock', () => (overlay.hidden = mode === 'fly'));
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

  const minimap = setupMinimap();
  const label = document.getElementById('room');
  const clock = new THREE.Clock(), fwd = new THREE.Vector3(), right = new THREE.Vector3();
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.05);
    if (nightSky) nightSky.starMat.uniforms.uTwinkle.value += dt;
    if (mode === 'fly') { orbit.update(); label.textContent = 'Nā Hiku · Kukuiʻula'; render(); return; }
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

function setupMinimap() {
  const c = document.getElementById('minimap'), ctx = c.getContext('2d');
  const pad = 10, W = c.width, H = c.height;
  // north (+x) up on the map
  const s = Math.min((W - 2 * pad) / (B.maxY - B.minY), (H - 2 * pad) / (B.maxX - B.minX));
  const tx = (x, y) => pad + (y - B.minY) * s, ty = (x, y) => H - pad - (x - B.minX) * s;
  c.addEventListener('click', e => {
    const rect = c.getBoundingClientRect(), mx = (e.clientX - rect.left) * W / rect.width, my = (e.clientY - rect.top) * H / rect.height;
    const y = B.minY + (mx - pad) / s, x = B.minX + (H - pad - my) / s;
    if (!blocked(x, y)) { player.x = x; player.z = y; }
  });
  return (p, cam) => {
    ctx.clearRect(0, 0, W, H);
    for (const r of plan.rooms) {
      if (r.label_only) continue;
      ctx.beginPath(); r.polygon.forEach(([x, y], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, tx(x, y), ty(x, y))); ctx.closePath();
      ctx.fillStyle = r.outdoor ? 'rgba(160,140,110,.35)' : 'rgba(255,255,255,.6)'; ctx.fill();
    }
    ctx.strokeStyle = '#2a2a2a'; ctx.lineWidth = 1.5;
    for (const { a, b } of colliders) { ctx.beginPath(); ctx.moveTo(tx(...a), ty(...a)); ctx.lineTo(tx(...b), ty(...b)); ctx.stroke(); }
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
