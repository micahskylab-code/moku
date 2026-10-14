// The lot and everything around it: terrain, pool, hardscape, planting, street, ocean.
// Layout follows the Lot 25 exterior renderings: infinity-edge pool with a raised spa off the
// lanai, coral-stone retaining walls spilling bougainvillea, tall palms between pool and lanai,
// a paver walk with grass joints up the middle of the front courtyard.
import * as THREE from 'three';
import { mat } from './materials.js';
import { fbm } from './textures.js';
import { footprint } from './house.js';
import { plantBed, plumeria, frondMaterial, foliageTexture } from './plants.js';
import { distToSeg } from './geom.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const rnd = seed => () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822519) ^ (seed + 0x9e3779b9)) >>> 0) / 4294967296;

export function buildSite(plan, scene, colliders) {
  const S = plan.site ?? {};
  const g = new THREE.Group();
  const grade = plan.grade ?? -0.6;

  // ---- golf course: fairways (1), greens (3), bunkers (4) from centre-lines in the plan ----
  if (S.golf && !S.landuse) {
    S.landuse = (x, y) => {
      for (const h of S.golf) {
        for (const b of h.bunkers ?? []) if (Math.hypot(x - b[0], y - b[1]) < b[2]) return 4;
        if (h.green && Math.hypot(x - h.green[0], y - h.green[1]) < h.green[2]) return 3;
        for (let i = 0; i < h.path.length - 1; i++) if (distToSeg(x, y, h.path[i], h.path[i + 1]) < h.width / 2) return 1;
      }
      return 0;
    };
  }
  // ---- terrain: level pad around the house, falling away west toward the coast ----
  const terrainH = makeTerrain(S, grade);
  g.add(terrainMesh(terrainH, S));

  // ---- pool, spa, infinity edge, deck ----
  if (S.pool) g.add(pool(S.pool, grade, colliders));

  // ---- hardscape ----
  for (const p of S.paths ?? []) g.add(slab(p.rect, grade + 0.02, p.material ?? 'pavers'));
  for (const w of S.walls ?? []) g.add(stoneWall(w, terrainH, colliders));

  // ---- street ----
  if (S.street) {
    const [x0, y0, x1, y1] = S.street;
    g.add(slab([x0, y0, x1, y1], grade - 0.3, 'asphalt'));
    g.add(slab([x0 - 1, y0, x0, y1], grade + 0.05, '#d8d4cc'));
  }

  // ---- planting ----
  const plants = new THREE.Group();
  for (const p of S.palms ?? []) plants.add(palm(p[0], p[1], terrainH(p[0], p[1]), p[2] ?? 30, p[3] ?? 1));
  for (const p of S.plumeria ?? []) plants.add(plumeria(p[0], p[1], terrainH(p[0], p[1]), p[2] ?? 1));
  for (const b of S.beds ?? []) plants.add(plantBed(b, terrainH));
  for (const l of S.loungers ?? []) {
    const L = new THREE.Group(); loungerInto(L); L.position.set(l[0], grade + 0.02, l[1]); L.rotation.y = -(l[2] ?? 0) * Math.PI / 180; plants.add(L);
    colliders.push(...footprint({ x: l[0], y: l[1], w: 2.4, d: 6.4, rot: l[2] ?? 0 }));
  }
  g.add(plants);
  g.add(scatterTrees(terrainH, S));

  // ---- ocean on the horizon ----
  const ocean = new THREE.Mesh(new THREE.PlaneGeometry(60000, 60000), new THREE.MeshStandardMaterial({ color: '#2a5f86', roughness: 0.25, metalness: 0.1 }));
  ocean.rotation.x = -Math.PI / 2; ocean.position.set(0, S.seaLevel ?? -230, 0);
  ocean.receiveShadow = false;
  g.add(ocean);

  g.traverse(o => { if (o.isMesh && o !== ocean) { o.castShadow = !o.material.transparent; o.receiveShadow = true; } });
  scene.add(g);
  return { terrainH, group: g };
}

// Height of the land (ft) at plan (x, y): the level lot, a lower lawn below the pool's
// retaining wall on the seaward side, golf-course roll beyond, the long fall to the sea and
// the rise inland toward the mountains.
function makeTerrain(S, grade) {
  const lot = S.lot ?? [-60, -40, 140, 90];
  const roll = fbm(4, 4, 7);
  const [ox, oy] = S.oceanDir ?? [-0.87, -0.5];
  const cx = (lot[0] + lot[2]) / 2, cy = (lot[1] + lot[3]) / 2;
  const ss = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  return (x, y) => {
    const dx = Math.max(lot[0] - x, 0, x - lot[2]), dy = Math.max(lot[1] - y, 0, y - lot[3]);
    const out = Math.hypot(dx, dy);
    if (out <= 0) return grade;
    const toward = (x - cx) * ox + (y - cy) * oy;
    const bank = -(S.bank ?? 7.5) * ss(0, 1.2, lot[0] - x);
    const far = ss(60, 600, out);
    const fall = -Math.max(0, toward) * 0.05 * far;
    const rise = Math.max(0, -toward - 900) * 0.11 * far;
    const u = ((x / 7000) % 1 + 1) % 1, v = ((y / 7000) % 1 + 1) % 1;
    const und = (roll(u, v) - 0.5) * 40 * far;
    return grade + bank + fall + rise + und;
  };
}

// Distant tree clumps and palms on the surrounding land (instanced; cheap at any count).
function scatterTrees(H, S) {
  const g = new THREE.Group(), r = rnd(2024);
  const lot = S.lot ?? [-60, -40, 140, 90];
  const keepOut = S.keepOut ?? [];
  const ok = (x, y) => {
    if (x > lot[0] - 25 && x < lot[2] + 40 && y > lot[1] - 20 && y < lot[3] + 20) return false;
    const [ox, oy] = S.oceanDir ?? [-0.87, -0.5], d = Math.hypot(x - 40, y - 20);
    if (((x - 40) * ox + (y - 20) * oy) / d > 0.55 && d < 2500) return false;          // keep the ocean view open
    if (S.landuse && S.landuse(x, y) === 1) return false;            // fairways stay open
    return !keepOut.some(([a, b, c, d]) => x > a && x < c && y > b && y < d);
  };
  // canopy trees as three crossed leaf cards each
  const cards = [];
  for (let k = 0; k < 3; k++) { const p = new THREE.PlaneGeometry(2, 2); p.rotateY(k * Math.PI / 3); p.translate(0, 1, 0); cards.push(p); }
  const top = new THREE.PlaneGeometry(2, 2); top.rotateX(-Math.PI / 2); top.translate(0, 1.3, 0); cards.push(top);
  const treeGeo = mergeGeometries(cards);
  const treeMat = foliageTexture('hedge').clone(); treeMat.color = new THREE.Color('#ffffff');
  const clump = new THREE.InstancedMesh(treeGeo, treeMat, 2600);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), c = new THREE.Color();
  let n = 0;
  for (let i = 0; i < 9000 && n < 2600; i++) {
    const a = r() * Math.PI * 2, d = 200 + Math.pow(r(), 1.4) * 6500, x = 40 + Math.cos(a) * d, y = 20 + Math.sin(a) * d;
    if (!ok(x, y)) continue;
    const s = 9 + r() * 10, h = H(x, y);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), r() * Math.PI);
    m.compose(new THREE.Vector3(x, h, y), q, new THREE.Vector3(s, s * (0.8 + r() * 0.4), s));
    clump.setMatrixAt(n, m); clump.setColorAt(n, c.setHSL(0.24 + r() * 0.06, 0.25, 0.55 + r() * 0.25)); n++;
  }
  q.identity();
  clump.count = n; clump.castShadow = false; clump.receiveShadow = true;
  g.add(clump);
  // tall palms in groups, silhouetted on the skyline
  const trunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.5, 0.7, 1, 6), new THREE.MeshStandardMaterial({ color: '#8f877a', roughness: 1 }), 500);
  const crownGeo = new THREE.ConeGeometry(1, 0.6, 9, 1, true); crownGeo.translate(0, -0.3, 0);
  const crown = new THREE.InstancedMesh(crownGeo, new THREE.MeshStandardMaterial({ color: '#365a24', roughness: 0.9, side: THREE.DoubleSide }), 500);
  let p = 0;
  for (let i = 0; i < 4000 && p < 500; i++) {
    const a = r() * Math.PI * 2, d = 140 + Math.pow(r(), 1.3) * 4000, x = 40 + Math.cos(a) * d, y = 20 + Math.sin(a) * d;
    if (!ok(x, y)) continue;
    const ht = 28 + r() * 22, h = H(x, y);
    for (let k = 0; k < 1 + Math.floor(r() * 3) && p < 500; k++) {
      const ox = (r() - 0.5) * 18, oy = (r() - 0.5) * 18;
      m.compose(new THREE.Vector3(x + ox, h + ht / 2, y + oy), q, new THREE.Vector3(1, ht, 1)); trunk.setMatrixAt(p, m);
      m.compose(new THREE.Vector3(x + ox, h + ht + 1, y + oy), q, new THREE.Vector3(9, 6, 9)); crown.setMatrixAt(p, m); p++;
    }
  }
  trunk.count = crown.count = p;
  g.add(trunk, crown);
  return g;
}

function terrainMesh(H, S) {
  // A radial grid: dense near the house, coarse far away, out to ~3.5 miles.
  const rings = 170, segs = 360, pos = [], uv = [], col = [], idx = [];
  const radius = r => 2 + Math.pow(r / rings, 2.4) * 19000;
  const cx = 40, cy = 20;
  const fair = new THREE.Color('#9cc95a'), rough = new THREE.Color('#5f8a36'), far = new THREE.Color('#4f7a33'), field = new THREE.Color('#a98c5d'), green = new THREE.Color('#b4dc6a'), sand = new THREE.Color('#f2e6c8');
  const land = S.landuse ?? (() => 0);
  const nn = fbm(8, 3, 77), land2 = (x, y) => nn(((x / 400) % 1 + 1) % 1, ((y / 400) % 1 + 1) % 1);
  for (let i = 0; i <= rings; i++) for (let j = 0; j <= segs; j++) {
    const r = radius(i), a = j / segs * Math.PI * 2, x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
    pos.push(x, H(x, y), y); uv.push(x, -y);
    const lu = land(x, y);
    const c = lu === 1 ? fair : lu === 2 ? field : lu === 3 ? green : lu === 4 ? sand : r > 2000 ? far : rough;
    const v = 0.88 + land2(x, y) * 0.24;
    const k = r < 160 && lu === 0 ? new THREE.Color(v, v * 1.02, v * 0.95) : c.clone().multiplyScalar((lu === 4 ? 2.6 : 1.25) * v);
    col.push(k.r, k.g, k.b);
  }
  for (let i = 0; i < rings; i++) for (let j = 0; j < segs; j++) {
    const a = i * (segs + 1) + j, b = a + segs + 1;
    idx.push(a, a + 1, b, b, a + 1, b + 1);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.setIndex(idx); geo.computeVertexNormals();
  const m = mat('grass').clone(); m.vertexColors = true;
  const mesh = new THREE.Mesh(geo, m);
  mesh.receiveShadow = true;
  return mesh;
}

function slab([x0, y0, x1, y1], y, material, t = 0.12) {
  const w = x1 - x0, d = y1 - y0;
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, t, d), mat(material));
  setBoxUV(m.geometry, w, t, d);
  m.position.set((x0 + x1) / 2, y - t / 2 + 0.001, (y0 + y1) / 2);
  m.receiveShadow = true;
  return m;
}

// World-scale UVs on a box so textures keep their real size.
function setBoxUV(geo, w, h, d) {
  const uv = geo.attributes.uv, n = geo.attributes.normal, p = geo.attributes.position;
  for (let i = 0; i < uv.count; i++) {
    const nx = Math.abs(n.getX(i)), ny = Math.abs(n.getY(i));
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    if (ny > 0.5) uv.setXY(i, x, z); else if (nx > 0.5) uv.setXY(i, z, y); else uv.setXY(i, x, y);
  }
  uv.needsUpdate = true;
}
function sbox(w, h, d, material) { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(material)); setBoxUV(m.geometry, w, h, d); return m; }

function pool(P, grade, colliders) {
  const g = new THREE.Group();
  const [x0, y0, x1, y1] = P.rect, w = x1 - x0, d = y1 - y0, depth = 4.5, water = grade - 0.35;
  const deckW = P.deck ?? 3;
  // deck: coral pavers around three sides (the seaward side is the vanishing edge)
  g.add(slab([x0 - (P.edge === 'x0' ? 0 : deckW), y0 - deckW, x0, y1 + deckW], grade + 0.04, 'coral'));
  g.add(slab([x1, y0 - deckW, x1 + deckW, y1 + deckW], grade + 0.04, 'coral'));
  g.add(slab([x0, y0 - deckW, x1, y0], grade + 0.04, 'coral'));
  g.add(slab([x0, y1, x1, y1 + deckW], grade + 0.04, 'coral'));
  // shell: tiled floor and walls
  const floor = sbox(w, 0.2, d, 'poolTile'); floor.position.set((x0 + x1) / 2, water - depth, (y0 + y1) / 2); g.add(floor);
  for (const [cx, cz, ww, dd] of [[(x0 + x1) / 2, y0, w, 0.3], [(x0 + x1) / 2, y1, w, 0.3], [x1, (y0 + y1) / 2, 0.3, d], [x0, (y0 + y1) / 2, 0.3, d]]) {
    const wall = sbox(ww, depth + 0.6, dd, 'poolTile'); wall.position.set(cx, water - depth / 2 + 0.25, cz); g.add(wall);
  }
  // coping on the three deck sides
  for (const [cx, cz, ww, dd] of [[(x0 + x1) / 2, y0 - 0.5, w + 2, 1], [(x0 + x1) / 2, y1 + 0.5, w + 2, 1], [x1 + 0.5, (y0 + y1) / 2, 1, d]]) {
    const c = sbox(ww, 0.25, dd, 'coral'); c.position.set(cx, grade + 0.08, cz); g.add(c);
  }
  // water
  const wat = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.3, d - 0.3), mat('water'));
  wat.rotation.x = -Math.PI / 2; wat.position.set((x0 + x1) / 2, water, (y0 + y1) / 2); wat.renderOrder = 3; g.add(wat);
  // raised spa in the corner nearest the house, spilling into the pool
  if (P.spa) {
    const [sx0, sy0, sx1, sy1] = P.spa, sw = sx1 - sx0, sd = sy1 - sy0;
    const rim = 1.2;
    for (const [cx, cz, ww, dd] of [[(sx0 + sx1) / 2, sy0, sw, 0.6], [(sx0 + sx1) / 2, sy1, sw, 0.6], [sx0, (sy0 + sy1) / 2, 0.6, sd], [sx1, (sy0 + sy1) / 2, 0.6, sd]]) {
      const wall = sbox(ww + 0.6, depth + rim, dd, 'coral'); wall.position.set(cx, water - depth / 2 + rim / 2 + 0.2, cz); g.add(wall);
    }
    const sp = new THREE.Mesh(new THREE.PlaneGeometry(sw - 0.6, sd - 0.6), mat('water'));
    sp.rotation.x = -Math.PI / 2; sp.position.set((sx0 + sx1) / 2, water + rim - 0.15, (sy0 + sy1) / 2); g.add(sp);
    const inner = sbox(sw - 0.6, 0.1, sd - 0.6, 'poolTile'); inner.position.set((sx0 + sx1) / 2, water - 2.5, (sy0 + sy1) / 2); g.add(inner);
  }
  // vanishing edge on the x0 side: a sheet of water over a tiled face into a catch basin,
  // all held up by a coral-stone retaining wall
  if (P.edge === 'x0') {
    const drop = P.drop ?? 4;
    const sheet = new THREE.Mesh(new THREE.PlaneGeometry(d, drop), new THREE.MeshPhysicalMaterial({ color: '#cfeff3', transparent: true, opacity: 0.55, roughness: 0.15, envMapIntensity: 1.5 }));
    sheet.position.set(x0 - 0.2, water - drop / 2, (y0 + y1) / 2); sheet.rotation.y = -Math.PI / 2; g.add(sheet);
    const face = sbox(0.3, drop, d, 'poolTile'); face.position.set(x0 - 0.05, water - drop / 2, (y0 + y1) / 2); g.add(face);
    const basin = new THREE.Mesh(new THREE.PlaneGeometry(2.6, d), mat('water')); basin.rotation.x = -Math.PI / 2; basin.position.set(x0 - 1.6, water - drop, (y0 + y1) / 2); g.add(basin);
    const rw = sbox(1.2, drop + 6, d + 6, 'ashlar'); rw.position.set(x0 - 3.4, water - drop - 3 + 0.4, (y0 + y1) / 2); g.add(rw);
    const bf = sbox(3, 1.0, d + 6, 'ashlar'); bf.position.set(x0 - 1.6, water - drop - 0.4, (y0 + y1) / 2); g.add(bf);
  }
  colliders.push(...footprint({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, w, d }));
  return g;
}

// Coral-stone wall from a polyline; height above local ground, with a cap.
function stoneWall(W, H, colliders) {
  const g = new THREE.Group();
  for (let i = 0; i < W.pts.length - 1; i++) {
    const [ax, ay] = W.pts[i], [bx, by] = W.pts[i + 1], len = Math.hypot(bx - ax, by - ay);
    const nx = -(by - ay) / len, ny = (bx - ax) / len, probe = [];
    for (const t of [0, 0.5, 1]) for (const s of [-2.5, 2.5]) probe.push(H(ax + (bx - ax) * t + nx * s, ay + (by - ay) * t + ny * s));
    const base = Math.min(...probe) - (W.footing ?? 1);
    const top = (W.top ?? (H(ax, ay) + (W.height ?? 2)));
    const m = sbox(len + 1.2, top - base, 1.2, 'ashlar');
    m.position.set((ax + bx) / 2, (top + base) / 2, (ay + by) / 2); m.rotation.y = -Math.atan2(by - ay, bx - ax); g.add(m);
    const cap = sbox(len + 1.4, 0.2, 1.5, 'coral'); cap.position.set((ax + bx) / 2, top + 0.1, (ay + by) / 2); cap.rotation.y = m.rotation.y; g.add(cap);
    colliders.push({ a: [ax, ay], b: [bx, by] });
  }
  return g;
}

// ---------- plants ----------
const frondShape = (() => {
  const s = new THREE.Shape(); s.moveTo(0, -0.08); s.quadraticCurveTo(0.5, -0.5, 1, -0.05); s.lineTo(1, 0.05); s.quadraticCurveTo(0.5, 0.5, 0, 0.08); return s;
})();

// Tall palm: curved ringed trunk, ~16 arching fronds.
export function palm(x, y, ground, height = 30, lean = 1, seed = 0) {
  const r = rnd(Math.round(x * 13 + y * 7 + seed));
  const g = new THREE.Group(); g.position.set(x, ground, y);
  const leanDir = r() * Math.PI * 2, bend = (0.03 + r() * 0.05) * lean;
  const pts = [];
  for (let k = 0; k <= 12; k++) { const t = k / 12; pts.push(new THREE.Vector3(Math.cos(leanDir) * bend * height * t * t, height * t, Math.sin(leanDir) * bend * height * t * t)); }
  const curve = new THREE.CatmullRomCurve3(pts);
  const trunk = new THREE.Mesh(new THREE.TubeGeometry(curve, 24, 0.55, 10), trunkMat());
  const pos = trunk.geometry.attributes.position;
  for (let i = 0; i < pos.count; i++) { const t = pos.getY(i) / height; const s = 1.15 - t * 0.35; pos.setX(i, pos.getX(i) * s + (1 - s) * pts[Math.min(12, Math.round(t * 12))].x); pos.setZ(i, pos.getZ(i) * s + (1 - s) * pts[Math.min(12, Math.round(t * 12))].z); }
  trunk.geometry.computeVertexNormals();
  g.add(trunk);
  const top = pts[12];
  // smooth green crownshaft under the fronds (foxtail / royal palm)
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.7, 4.0, 14), mat('#56653a')); shaft.position.copy(top).add(new THREE.Vector3(0, -2.2, 0)); g.add(shaft);
  const crown = new THREE.Mesh(new THREE.SphereGeometry(0.9, 10, 8), mat('#556b2c')); crown.position.copy(top); g.add(crown);
  const fm = frondMaterial();
  const n = 24 + Math.floor(r() * 6);
  for (let k = 0; k < n; k++) {
    const len = 10 + r() * 4, a = k / n * Math.PI * 2 + r() * 0.3, droop = 0.35 + r() * 0.65;
    const geo = new THREE.PlaneGeometry(len, len * 0.32, 12, 1);
    geo.rotateX(-Math.PI / 2); geo.translate(len / 2, 0, 0);
    const p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) { const u = Math.max(0, p.getX(i) / len); p.setY(i, p.getY(i) - Math.pow(u, 1.8) * len * (0.3 + droop * 0.35)); }
    geo.computeVertexNormals();
    const fr = new THREE.Mesh(geo, fm);
    fr.rotation.x = (r() - 0.5) * 0.7;
    const holder = new THREE.Group(); holder.position.copy(top);
    holder.rotation.order = 'YZX'; holder.rotation.y = a; holder.rotation.z = 0.5 - droop * 0.55;
    holder.add(fr); g.add(holder);
  }
  g.traverse(o => { if (o.isMesh) o.castShadow = true; });
  return g;
}

let tMat = null;
function trunkMat() {
  if (tMat) return tMat;
  const c = document.createElement('canvas'); c.width = 64; c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '#7f786c'; x.fillRect(0, 0, 64, 256);
  for (let k = 0; k < 256; k += 8) { x.fillStyle = 'rgba(60,45,30,.45)'; x.fillRect(0, k, 64, 2); x.fillStyle = 'rgba(200,185,160,.25)'; x.fillRect(0, k + 3, 64, 2); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 10); t.colorSpace = THREE.SRGBColorSpace;
  tMat = new THREE.MeshStandardMaterial({ map: t, roughness: 0.95 });
  return tMat;
}

function loungerInto(g) {
  const b = (w, h, d, x, y, z, m) => { const mm = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(m)); mm.position.set(x, y, z); g.add(mm); return mm; };
  b(2.3, 0.2, 6.3, 0, 1.0, 0, 'teak');
  for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) b(0.2, 1.0, 0.2, sx * 1.0, 0.5, sz * 2.9, 'teak');
  b(2.2, 0.3, 3.8, 0, 1.25, 1.1, 'linenWhite');
  b(2.2, 0.3, 2.4, 0, 1.75, -1.9, 'linenWhite').rotation.x = 0.6;
  b(1.6, 0.14, 0.9, 0, 1.47, 1.6, '#ffffff').rotation.y = 0.15;
}
