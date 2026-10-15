// 360° tour of path-traced panoramas (Blender Cycles, scripts/blender_render.py --panos).
// Each panorama is equirectangular with its centre facing three.js -Z and right = +X.
import * as THREE from 'three';

const spec = await (await fetch('tour/panos.json')).json();
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.prepend(renderer.domElement);
const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.1, 100);

// the panorama is looked up per pixel from the view direction, exactly as Cycles projected it
// (no UV seam at the back, no pinching at the poles)
const mat = new THREE.ShaderMaterial({
  uniforms: { map: { value: null } },
  vertexShader: 'varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D map; varying vec3 vDir;
    void main() {
      vec3 d = normalize(vDir);
      vec2 uv = vec2(0.5 + atan(d.x, -d.z) / 6.2831853, 0.5 + asin(clamp(d.y, -1.0, 1.0)) / 3.1415927);
      gl_FragColor = texture2D(map, uv);
      #include <colorspace_fragment>
    }`,
  side: THREE.BackSide, depthWrite: false,
});
const sphere = new THREE.Mesh(new THREE.SphereGeometry(50, 64, 32), mat);
scene.add(sphere);

const loader = new THREE.TextureLoader(), cache = new Map();
const load = id => { if (!cache.has(id)) cache.set(id, new Promise(res => loader.load(`tour/${id}.jpg`, t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; t.minFilter = THREE.LinearFilter; t.generateMipmaps = false; res(t); }))); return cache.get(id); };

let yaw = 0, pitch = 0, fov = 75, current = null;
const roomsEl = document.getElementById('rooms'), fade = document.getElementById('fade'), spots = [];
for (const p of spec.panos) {
  const b = document.createElement('button'); b.textContent = p.name; b.onclick = () => go(p.id); roomsEl.append(b); p.button = b;
  const s = document.createElement('div'); s.className = 'spot'; s.innerHTML = `<span>${p.name}</span>`; s.onclick = () => go(p.id); document.body.append(s); spots.push([p, s]);
}

async function go(id) {
  const p = spec.panos.find(q => q.id === id); if (!p || p === current) return;
  fade.style.opacity = 1;
  const tex = await load(id);
  // face the direction of travel
  if (current) { const dx = p.pos[0] - current.pos[0], dz = p.pos[2] - current.pos[2]; yaw = Math.atan2(dx, -dz); }
  mat.uniforms.map.value = tex; current = p;
  document.getElementById('room').textContent = p.name;
  for (const q of spec.panos) q.button.classList.toggle('on', q === p);
  fade.style.opacity = 0;
  for (const q of spec.panos) if (q !== p) load(q.id);   // prefetch
}

// drag / swipe to look, wheel / pinch to zoom
let drag = null;
addEventListener('pointerdown', e => { if (e.target === renderer.domElement) drag = { x: e.clientX, y: e.clientY }; });
addEventListener('pointermove', e => { if (!drag) return; const k = fov / innerHeight * Math.PI / 180; yaw -= (e.clientX - drag.x) * k; pitch = Math.max(-1.45, Math.min(1.45, pitch + (e.clientY - drag.y) * k)); drag = { x: e.clientX, y: e.clientY }; });
addEventListener('pointerup', () => (drag = null));
addEventListener('wheel', e => { fov = Math.max(35, Math.min(95, fov + e.deltaY * 0.04)); });
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

renderer.setAnimationLoop(() => {
  const dir = new THREE.Vector3(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
  camera.lookAt(dir); camera.fov = fov; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  // hotspots for the other stops, at their real positions
  for (const [p, s] of spots) {
    if (!current || p === current) { s.style.display = 'none'; continue; }
    const v = new THREE.Vector3(p.pos[0] - current.pos[0], p.pos[1] - current.pos[1] - 4.5, p.pos[2] - current.pos[2]).normalize().multiplyScalar(10).project(camera);
    const vis = v.z < 1 && Math.abs(v.x) < 1 && Math.abs(v.y) < 1;
    s.style.display = vis ? 'grid' : 'none';
    s.style.left = `${(v.x + 1) / 2 * innerWidth}px`; s.style.top = `${(1 - v.y) / 2 * innerHeight}px`;
  }
});
go(new URLSearchParams(location.search).get('room') ?? spec.panos[0].id);
