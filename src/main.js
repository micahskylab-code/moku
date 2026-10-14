import * as THREE from '../vendor/three.module.js';
import { PointerLockControls } from '../vendor/PointerLockControls.js';
import { buildHouse, inside } from './build.js';
import { materialFor } from './materials.js';

const EYE = 5.4;        // feet
const SPEED = 6;        // feet per second, a relaxed walk
const RADIUS = 0.9;     // how close you can get to a wall

const params = new URLSearchParams(location.search);
const planId = params.get('plan') ?? 'test-plan';
const viewId = params.get('view'); // screenshot mode for the critic loop: fixed camera, no HUD

const plan = await (await fetch(`plans/${planId}.json`)).json();
document.title = plan.name;
document.getElementById('plan-name').textContent = plan.name;

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: !!viewId });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(plan.sky ?? '#a9cfe6');
scene.fog = new THREE.Fog(scene.background, 120, 400);

const camera = new THREE.PerspectiveCamera(Number(params.get('fov') ?? plan.fov ?? 70), innerWidth / innerHeight, 0.1, 1000);

scene.add(new THREE.HemisphereLight('#e6f1ff', '#d9cfbf', 1.4));
const sun = new THREE.DirectionalLight('#fff3df', 2.4);
const { colliders, bounds } = buildHouse(plan, scene);
const cx = (bounds.minX + bounds.maxX) / 2, cy = (bounds.minY + bounds.maxY) / 2;
const span = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
const sunDir = plan.sunFrom ?? [-0.6, 1, -0.8]; // default: high afternoon sun over the lanai side
sun.position.set(cx + sunDir[0] * span, sunDir[1] * span, cy + sunDir[2] * span);
sun.target.position.set(cx, 0, cy);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 1, far: span * 4 });
sun.shadow.bias = -0.0005;
scene.add(sun, sun.target);
// Soft fill so interiors are not black where the sun cannot reach.
for (const r of plan.rooms.filter(r => !r.outdoor)) {
  const [x, y] = centroid(r.polygon);
  const l = new THREE.PointLight('#fff1dc', 2.5, 40, 1);
  l.position.set(x, (plan.wallHeight ?? 10) - 3, y);
  scene.add(l);
}

const ground = new THREE.Mesh(new THREE.PlaneGeometry(1000, 1000), materialFor(plan.ground ?? 'grass'));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.02;
ground.receiveShadow = true;
scene.add(ground);

const controls = new PointerLockControls(camera, document.body);
const player = camera.position;

function place(pos, look) {
  player.set(pos[0], EYE, pos[1]);
  camera.lookAt(look[0], EYE - 0.4, look[1]);
}

if (viewId) {
  const v = plan.viewpoints.find(v => v.id === viewId);
  if (!v) throw new Error(`no viewpoint ${viewId}`);
  document.body.classList.add('shot');
  place(v.pos, v.look);
  if (v.eye) player.y = v.eye;
  renderer.render(scene, camera);
  document.body.dataset.ready = '1';
} else {
  place(plan.start.pos, plan.start.look);
  startWalking();
}

function startWalking() {
  const keys = new Set();
  addEventListener('keydown', e => keys.add(e.code));
  addEventListener('keyup', e => keys.delete(e.code));
  const overlay = document.getElementById('overlay');
  overlay.addEventListener('click', () => { if (!matchMedia('(pointer: coarse)').matches) controls.lock(); else overlay.hidden = true; });
  controls.addEventListener('lock', () => (overlay.hidden = true));
  controls.addEventListener('unlock', () => (overlay.hidden = false));

  // Touch: drag on the left half to walk, on the right half to look.
  const touch = { move: null, look: null };
  addEventListener('touchstart', e => {
    for (const t of e.changedTouches) {
      const slot = t.clientX < innerWidth / 2 ? 'move' : 'look';
      touch[slot] = { id: t.identifier, x0: t.clientX, y0: t.clientY, x: t.clientX, y: t.clientY };
    }
  }, { passive: true });
  addEventListener('touchmove', e => {
    for (const t of e.changedTouches) for (const slot of ['move', 'look']) {
      const s = touch[slot];
      if (s?.id !== t.identifier) continue;
      if (slot === 'look') {
        const euler = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
        euler.y -= (t.clientX - s.x) * 0.005;
        euler.x = Math.max(-1.4, Math.min(1.4, euler.x - (t.clientY - s.y) * 0.005));
        camera.quaternion.setFromEuler(euler);
      }
      s.x = t.clientX; s.y = t.clientY;
    }
  }, { passive: true });
  addEventListener('touchend', e => { for (const t of e.changedTouches) for (const k of ['move', 'look']) if (touch[k]?.id === t.identifier) touch[k] = null; });

  const minimap = setupMinimap();
  const label = document.getElementById('room');
  const clock = new THREE.Clock();
  const fwd = new THREE.Vector3(), right = new THREE.Vector3();

  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.05);
    let f = (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0);
    let r = (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0) - (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0);
    if (touch.move) {
      f = Math.max(-1, Math.min(1, -(touch.move.y - touch.move.y0) / 60));
      r = Math.max(-1, Math.min(1, (touch.move.x - touch.move.x0) / 60));
    }
    const speed = SPEED * (keys.has('ShiftLeft') ? 1.8 : 1);
    camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
    right.crossVectors(fwd, camera.up);
    const dx = (fwd.x * f + right.x * r) * speed * dt, dz = (fwd.z * f + right.z * r) * speed * dt;
    // Axis-separated moves let you slide along a wall instead of sticking to it.
    if (!blocked(player.x + dx, player.z)) player.x += dx;
    if (!blocked(player.x, player.z + dz)) player.z += dz;

    const room = plan.rooms.find(rm => inside([player.x, player.z], rm.polygon));
    label.textContent = room?.name ?? 'Outside';
    minimap(player, camera);
    renderer.render(scene, camera);
  });
}

function blocked(x, z) {
  for (const { a, b } of colliders) if (distToSeg(x, z, a, b) < RADIUS) return true;
  return false;
}

function distToSeg(px, py, [ax, ay], [bx, by]) {
  const vx = bx - ax, vy = by - ay, L = vx * vx + vy * vy || 1;
  const t = Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / L));
  return Math.hypot(px - (ax + t * vx), py - (ay + t * vy));
}

function centroid(poly) {
  return poly.reduce(([sx, sy], [x, y]) => [sx + x / poly.length, sy + y / poly.length], [0, 0]);
}

function setupMinimap() {
  const c = document.getElementById('minimap'), ctx = c.getContext('2d');
  const pad = 8, W = c.width, H = c.height;
  const s = Math.min((W - 2 * pad) / (bounds.maxX - bounds.minX), (H - 2 * pad) / (bounds.maxY - bounds.minY));
  const tx = x => pad + (x - bounds.minX) * s, ty = y => pad + (y - bounds.minY) * s;
  c.addEventListener('click', e => {
    const rect = c.getBoundingClientRect();
    const x = bounds.minX + ((e.clientX - rect.left) * (W / rect.width) - pad) / s;
    const y = bounds.minY + ((e.clientY - rect.top) * (H / rect.height) - pad) / s;
    if (!blocked(x, y)) { player.x = x; player.z = y; }
  });
  return (p, cam) => {
    ctx.clearRect(0, 0, W, H);
    for (const r of plan.rooms) {
      ctx.beginPath();
      r.polygon.forEach(([x, y], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, tx(x), ty(y)));
      ctx.closePath();
      ctx.fillStyle = r.outdoor ? 'rgba(160,140,110,.35)' : 'rgba(255,255,255,.55)';
      ctx.fill();
    }
    ctx.strokeStyle = '#222'; ctx.lineWidth = 2;
    for (const { a, b } of colliders) { ctx.beginPath(); ctx.moveTo(tx(a[0]), ty(a[1])); ctx.lineTo(tx(b[0]), ty(b[1])); ctx.stroke(); }
    const d = new THREE.Vector3(); cam.getWorldDirection(d);
    ctx.fillStyle = '#d0452f';
    ctx.beginPath(); ctx.arc(tx(p.x), ty(p.z), 4, 0, 7); ctx.fill();
    ctx.strokeStyle = '#d0452f';
    ctx.beginPath(); ctx.moveTo(tx(p.x), ty(p.z)); ctx.lineTo(tx(p.x + d.x * 4), ty(p.z + d.z * 4)); ctx.stroke();
  };
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
