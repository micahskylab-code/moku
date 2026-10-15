// The lot and everything around it: terrain, pool, hardscape, planting, street, ocean.
// Layout follows the Lot 25 exterior renderings: infinity-edge pool with a raised spa off the
// lanai, coral-stone retaining walls spilling bougainvillea, tall palms between pool and lanai,
// a paver walk with grass joints up the middle of the front courtyard.
import * as THREE from 'three';
import { mat } from './materials.js';
import { fbm, texture } from './textures.js';
import { footprint } from './house.js';
import { chaiseInto } from './furniture.js';
import { plantBed, plumeria, frondMaterial, foliageTexture, recording, recordPlant } from './plants.js';
import { distToSeg } from './geom.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { siteLayout } from './neighborhood.js';
import { inside } from './geom.js';
import { buildPool } from './pool.js';

const rnd = seed => () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822519) ^ (seed + 0x9e3779b9)) >>> 0) / 4294967296;

export function buildSite(plan, scene, colliders) {
  const S = plan.site ?? {};
  const g = new THREE.Group();
  const grade = plan.grade ?? -0.6;

  // ---- golf course: fairways (1), greens (3), bunkers (4) from centre-lines in the plan ----
  const L = siteLayout(plan);
  S.golf = [...(S.golf ?? []), ...L.golf];
  S.fields = [...L.fields]; S.streets = L.streets; S.homes = [...L.homes, ...L.nahiku, ...L.villas, ...L.cottages]; S.ponds = L.ponds;
  if (S.golf && !S.landuse) {
    S.landuse = (x, y) => {
      for (const f of S.fields) if (inside([x, y], f)) return 2;
      for (const f of S.ponds ?? []) if (inside([x, y], f)) return 5;
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
  // the pool (and its copies on the other Na Hiku lots) are cut out of the lawn
  if (S.pool) {
    const [x0, y0, x1, y1] = S.pool.rect, lc = [(S.lot[0] + S.lot[2]) / 2, (S.lot[1] + S.lot[3]) / 2];
    const offs = [[0, 0], ...L.nahiku.map(([x, y]) => [x - lc[0], y - lc[1]])];
    const ex = S.pool.edge === 'x0' ? 3.6 : 0;      // vanishing edge: the catch basin and its wall sit below the lawn
    S.holes = offs.slice(0, 16).map(([dx, dy]) => [x0 - ex + dx + 0.1, y0 + dy + 0.1, x1 + dx - 0.1, y1 + dy - 0.1]);
  }
  g.add(terrainMesh(terrainH, S));

  // ---- pool, spa, infinity edge, deck ----
  if (S.pool) { const p = pool(S.pool, grade, colliders); p.userData.shell = true; g.add(p); }

  // ---- hardscape ----
  for (const p of S.paths ?? []) { const m = slab(p.rect, grade + 0.02, p.material ?? 'pavers'); m.userData.shell = true; g.add(m); }
  // the grass-paver drive sits in a tan coral border band along both long sides (front rendering p4)
  for (const p of (S.paths ?? []).filter(p => p.material === 'grassPavers')) {
    const [x0, y0, x1, y1] = p.rect, bw = 0.9;
    for (const r of [[x0, y0 - bw, x1, y0], [x0, y1, x1, y1 + bw]]) { const m = slab(r, grade + 0.03, 'coral'); m.userData.shell = true; g.add(m); }
  }
  for (const w of S.walls ?? []) { const m = stoneWall(w, terrainH, colliders); m.userData.shell = true; g.add(m); }

  // ---- street ----
  if (S.street) {
    const [x0, y0, x1, y1] = S.street;
    g.add(slab([x0, y0, x1, y1], grade - 0.3, 'asphalt'));
    g.add(slab([x0 - 1, y0, x0, y1], grade + 0.05, '#d8d4cc'));
  }

  // ---- planting ----
  const plants = new THREE.Group();
  // tall palms: [x, y, height, lean, kind] (kind: queen | foxtail | christmas | coconut; Blender grows the species)
  for (const p of S.palms ?? []) plants.add(palm(p[0], p[1], terrainH(p[0], p[1]), p[2] ?? 30, p[3] ?? 1, 0, { kind: p[4] ?? 'queen', trunkR: p[4] === 'christmas' ? 0.3 : 0.55 }));
  // understorey palm clumps [x, y, height, kind, stems]: areca / lipstick clumps (many canes), foxtail / christmas /
  // pygmy date (one to three trunks), cycads: the 3-20 ft palms that fill the renderings
  const CLUMP = { areca: [6, 0.4, 1.4, 0.55], lipstick: [5, 0.3, 1.0, 0.5], foxtail: [1, 2.5, 3.5, 0.85], christmas: [1, 2.0, 3.0, 0.8],
    roebelenii: [1, 1.5, 2.5, 0.75], cycad: [1, 1.0, 1.5, 0.7], queen: [1, 3, 4, 0.9] };
  for (const [x, y, h = 13, kind = 'areca', stems] of S.arecas ?? []) {
    const r = rnd(Math.round(x * 31 + y * 17));
    const [n0, d0, d1, hmin] = CLUMP[kind] ?? CLUMP.areca, n = stems ?? n0;
    for (let k = 0; k < n; k++) {
      const a = r() * Math.PI * 2, d = k === 0 && n0 === 1 ? 0 : d0 + r() * (d1 - d0);
      const clump = kind === 'areca' || kind === 'lipstick';
      plants.add(palm(x + Math.cos(a) * d, y + Math.sin(a) * d, terrainH(x, y), h * (hmin + r() * (1 - hmin)), clump ? 4 : 1.5, k,
        { trunkR: clump ? 0.14 : 0.3, frondLen: clump ? 0.5 : 0.65, fronds: 0.55, shaft: kind !== 'areca', kind }));
    }
  }
  for (const p of S.plumeria ?? []) plants.add(plumeria(p[0], p[1], terrainH(p[0], p[1]), p[2] ?? 1));
  // specimen flowering trees [x, y, scale, kind] (kind 'shower': pink shower tree, grown in Blender by scripts/plants_bpy.py)
  for (const [x, y, s = 1, kind = 'shower'] of S.specimens ?? []) {
    if (recording()) recordPlant({ type: kind, x, y, ground: terrainH(x, y), scale: s, seed: Math.round(x * 17 + y * 3 + 23), shell: true });
    else plants.add(plumeria(x, y, terrainH(x, y), s * 1.6));
  }
  for (const b of S.beds ?? []) plants.add(plantBed(b, terrainH));
  for (const l of S.loungers ?? []) {
    const L = new THREE.Group(); loungerInto(L); L.position.set(l[0], grade + 0.02, l[1]); L.rotation.y = -(l[2] ?? 0) * Math.PI / 180; plants.add(L);
    colliders.push(...footprint({ x: l[0], y: l[1], w: 2.4, d: 6.4, rot: l[2] ?? 0 }));
  }
  plants.userData.shell = true;
  g.add(plants);
  g.add(scatterTrees(terrainH, S));

  // ---- ocean on the horizon ----
  const ocean = new THREE.Mesh(new THREE.PlaneGeometry(60000, 60000), new THREE.MeshStandardMaterial({ name: 'ocean', color: '#2a5f86', roughness: 0.25, metalness: 0.1 }));
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
  const H = (x, y) => {
    const dx = Math.max(lot[0] - x, 0, x - lot[2]), dy = Math.max(lot[1] - y, 0, y - lot[3]);
    const out = Math.hypot(dx, dy);
    if (out <= 0) return grade;
    const toward = (x - cx) * ox + (y - cy) * oy;
    // behind our lot the pad is held by a coral retaining wall on the lot line: the ground steps down
    // exactly on the line (inside the wall), so the wall face shows (as in the rendering); elsewhere a
    // soft bank. terrainMesh() clips its triangles along H.step so no sliver pokes out of the wall.
    const walled = ss(lot[1] - 1.2, lot[1] - 0.2, y) * (1 - ss(lot[3] + 0.2, lot[3] + 1.2, y));   // inside the return walls
    const gentle = ss(0.6, 5, lot[0] - x), steep = lot[0] - x > 0 ? 1 : 0;
    const bank = -(S.bank ?? 7.5) * (gentle + (steep - gentle) * walled);
    const far = ss(60, 600, out);
    const fall = -Math.max(0, toward) * 0.05 * far;
    const rise = Math.max(0, -toward - 900) * 0.11 * far;
    const u = ((x / 7000) % 1 + 1) % 1, v = ((y / 7000) % 1 + 1) % 1;
    const und = (roll(u, v) - 0.5) * 40 * far;
    return grade + bank + fall + rise + und;
  };
  H.step = { x: lot[0], y0: lot[1] - 1.5, y1: lot[3] + 1.5 };
  return H;
}

// Distant tree clumps and palms on the surrounding land (instanced; cheap at any count).
function scatterTrees(H, S) {
  const g = new THREE.Group(), r = rnd(2024);
  const lot = S.lot ?? [-60, -40, 140, 90];
  const keepOut = S.keepOut ?? [];
  const ok = (x, y) => {
    if (x > lot[0] - 90 && x < lot[2] + 40 && y > lot[1] - 40 && y < lot[3] + 30) return false;
    const [ox, oy] = S.oceanDir ?? [-0.87, -0.5], d = Math.hypot(x - 40, y - 20);
    if (((x - 40) * ox + (y - 20) * oy) / d > 0.85 && d < 700) return false;           // keep the ocean view open
    if (S.landuse && S.landuse(x, y) > 0) return false;              // fairways, greens, field stay open
    if ((S.homes ?? []).some(([hx, hy]) => Math.hypot(x - hx, y - hy) < 42)) return false;
    for (const line of S.streets ?? []) for (let i = 0; i < line.length - 1; i++) if (distToSeg(x, y, line[i], line[i + 1]) < 26) return false;
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
  const rec = recording(), r2 = v => Math.round(v * 100) / 100;     // export: record, Blender grows real trees
  let n = 0;
  for (let i = 0; i < 9000 && n < 2600; i++) {
    const a = r() * Math.PI * 2, d = 200 + Math.pow(r(), 1.4) * 6500, x = 40 + Math.cos(a) * d, y = 20 + Math.sin(a) * d;
    if (!ok(x, y)) continue;
    const s = 9 + r() * 10, h = H(x, y);
    if (rec) { r(); const sy = 0.8 + r() * 0.4; r(); r(); recordPlant({ type: 'tree', x: r2(x), y: r2(y), ground: r2(h), size: r2(s), sy: r2(sy), seed: i }); n++; continue; }
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), r() * Math.PI);
    m.compose(new THREE.Vector3(x, h, y), q, new THREE.Vector3(s, s * (0.8 + r() * 0.4), s));
    clump.setMatrixAt(n, m); clump.setColorAt(n, c.setHSL(0.24 + r() * 0.06, 0.25, 0.55 + r() * 0.25)); n++;
  }
  q.identity();
  clump.count = rec ? 0 : n; clump.castShadow = false; clump.receiveShadow = true;
  if (!rec) g.add(clump);
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
      if (rec) { recordPlant({ type: 'farpalm', x: r2(x + ox), y: r2(y + oy), ground: r2(H(x + ox, y + oy)), height: r2(ht * (0.85 + 0.3 * ((p * 0.618) % 1))), seed: 5000 + p }); p++; continue; }
      m.compose(new THREE.Vector3(x + ox, h + ht / 2, y + oy), q, new THREE.Vector3(1, ht, 1)); trunk.setMatrixAt(p, m);
      m.compose(new THREE.Vector3(x + ox, h + ht + 1, y + oy), q, new THREE.Vector3(9, 6, 9)); crown.setMatrixAt(p, m); p++;
    }
  }
  trunk.count = crown.count = rec ? 0 : p;
  if (!rec) g.add(trunk, crown);
  return g;
}

function terrainMesh(H, S) {
  // A radial grid: a fine, even mesh (0.8 ft rings) out to 130 ft so the bank and the pool cut-out
  // are smooth, then coarser and coarser out to ~3.5 miles.
  const NI = 160, NO = 170, rings = NI + NO, segs = 360, pos = [], uv = [], col = [], idx = [];
  const radius = i => i <= NI ? 2 + i * 0.8 : 2 + NI * 0.8 + Math.pow((i - NI) / NO, 2.4) * 19000;
  const cx = 40, cy = 20;
  const fair = new THREE.Color('#9cc95a'), rough = new THREE.Color('#5f8a36'), far = new THREE.Color('#4f7a33'), field = new THREE.Color('#a98c5d'), green = new THREE.Color('#b4dc6a'), sand = new THREE.Color('#f2e6c8');
  const land = S.landuse ?? (() => 0);
  const nn = fbm(8, 3, 77), land2 = (x, y) => nn(((x / 400) % 1 + 1) % 1, ((y / 400) % 1 + 1) % 1);
  const vert = (x, y, h) => {
    pos.push(x, h, y); uv.push(x, -y);
    const lu = land(x, y), r = Math.hypot(x - cx, y - cy);
    const c = r > 2600 ? far : rough;
    const v = 0.88 + land2(x, y) * 0.24;
    const lt = S.lot ?? [-60, -40, 140, 90], out = Math.hypot(Math.max(lt[0] - x, 0, x - lt[2]), Math.max(lt[1] - y, 0, y - lt[3]));
    const lawn = new THREE.Color(v, v * 1.02, v * 0.95), wild = c.clone().multiplyScalar((lu === 4 ? 2.6 : lu ? 1.25 : 1.1) * v);
    const k = lawn.lerp(wild, Math.min(1, out / 60));
    col.push(k.r, k.g, k.b);
    return pos.length / 3 - 1;
  };
  for (let i = 0; i <= rings; i++) for (let j = 0; j <= segs; j++) {
    const r = radius(i), a = j / segs * Math.PI * 2, x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
    vert(x, y, H(x, y));
  }
  // Triangles that cross the retaining-wall step (H.step) are cut exactly on the step line, with the
  // line's vertices doubled (one at the pad level, one at the lower level), so the drop is a clean
  // vertical break hidden inside the wall instead of slivers sticking out of its faces.
  const st = H.step, X = st?.x ?? 0;
  const px = k => pos[k * 3], pz = k => pos[k * 3 + 2];
  const crosses = t => st && t.some(k => pz(k) > st.y0 && pz(k) < st.y1) && t.some(k => px(k) >= X) && t.some(k => px(k) < X);
  const tri = t => {
    if (!crosses(t)) { idx.push(...t); return; }
    const hi = [], lo = [];
    for (let e = 0; e < 3; e++) {
      const p = t[e], q = t[(e + 1) % 3], pHi = px(p) >= X;
      (pHi ? hi : lo).push(p);
      if (pHi !== (px(q) >= X)) {
        const f = (X - px(p)) / (px(q) - px(p)), y = pz(p) + f * (pz(q) - pz(p));
        hi.push(vert(X, y, H(X + 1e-3, y))); lo.push(vert(X, y, H(X - 1e-3, y)));
      }
    }
    for (const poly of [hi, lo]) for (let k = 1; k + 1 < poly.length; k++) idx.push(poly[0], poly[k], poly[k + 1]);
  };
  for (let i = 0; i < rings; i++) for (let j = 0; j < segs; j++) {
    const a = i * (segs + 1) + j, b = a + segs + 1;
    tri([a, a + 1, b]); tri([b, a + 1, b + 1]);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.setIndex(idx); geo.computeVertexNormals();
  const m = mat('grass').clone(); m.vertexColors = true; m.name = 'terrain';
  const landMap = landTexture(S);
  m.onBeforeCompile = sh => {
    sh.uniforms.uLand = { value: landMap.tex }; sh.uniforms.uLandBox = { value: new THREE.Vector4(...landMap.box) };
    const holes = (S.holes ?? []).slice(0, 16); while (holes.length < 16) holes.push([0, 0, 0, 0]);
    sh.uniforms.uHoles = { value: holes.map(h => new THREE.Vector4(...h)) };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec2 vLandXZ;').replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvLandXZ = (modelMatrix * vec4(transformed, 1.0)).xz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec2 vLandXZ; uniform sampler2D uLand; uniform vec4 uLandBox; uniform vec4 uHoles[16];')
      .replace('void main() {', 'void main() {\n  for (int i = 0; i < 16; i++) { vec4 h = uHoles[i]; if (vLandXZ.x > h.x && vLandXZ.x < h.z && vLandXZ.y > h.y && vLandXZ.y < h.w) discard; }')
      .replace('#include <color_fragment>', `#include <color_fragment>
      vec2 luv = (vLandXZ - uLandBox.xy) / uLandBox.zw;
      if (luv.x > 0.0 && luv.x < 1.0 && luv.y > 0.0 && luv.y < 1.0) { vec4 L = texture2D(uLand, luv); diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb / max(vColor, vec3(0.05)) * L.rgb * 1.9, L.a); }`);
  };
  const mesh = new THREE.Mesh(geo, m);
  mesh.receiveShadow = true;
  return mesh;
}

// Land cover map (fairways, greens, bunkers, the ag field) painted on a canvas with soft edges.
function landTexture(S) {
  const size = 2048, half = 4200, cx = 40, cy = 20, k = size / (2 * half);
  const c = document.createElement('canvas'); c.width = c.height = size;
  const x = c.getContext('2d');
  const P = ([px, py]) => [(px - cx + half) * k, (py - cy + half) * k];
  x.filter = 'blur(2px)';
  for (const f of S.fields ?? []) {
    x.fillStyle = 'rgba(170,140,95,0.95)'; x.beginPath(); f.forEach((p, i) => (i ? x.lineTo : x.moveTo).call(x, ...P(p))); x.closePath(); x.fill();
  }
  // plough lines across the field
  x.filter = 'none';
  x.strokeStyle = 'rgba(120,95,60,0.35)'; x.lineWidth = 2;
  for (const f of S.fields ?? []) { x.save(); x.beginPath(); f.forEach((p, i) => (i ? x.lineTo : x.moveTo).call(x, ...P(p))); x.closePath(); x.clip(); for (let i = -size; i < size * 2; i += 9) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i + size * 0.4, size); x.stroke(); } x.restore(); }
  x.filter = 'blur(2px)';
  for (const h of S.golf ?? []) {
    x.lineCap = x.lineJoin = 'round';
    x.strokeStyle = 'rgba(140,196,82,0.95)'; x.lineWidth = h.width * k; x.beginPath(); h.path.forEach((p, i) => (i ? x.lineTo : x.moveTo).call(x, ...P(p))); x.stroke();
    // mowing stripes
    x.strokeStyle = 'rgba(160,212,96,0.5)'; x.lineWidth = h.width * k * 0.5; x.setLineDash([6, 6]); x.stroke(); x.setLineDash([]);
    if (h.green) { x.fillStyle = 'rgba(168,222,104,1)'; x.beginPath(); x.arc(...P(h.green), h.green[2] * k, 0, 7); x.fill(); }
    for (const b of h.bunkers ?? []) { x.fillStyle = 'rgba(240,226,190,1)'; x.beginPath(); x.ellipse(...P(b), b[2] * k * 1.3, b[2] * k * 0.8, 0.6, 0, 7); x.fill(); }
  }
  // mowing stripes on lawns near the house
  if (S.lot) {
    const [x0, y0, x1, y1] = S.lot; x.filter = 'blur(1px)';
    for (let yy = y0 - 20; yy < y1 + 20; yy += 8) { x.fillStyle = ((yy - y0) / 8) % 2 < 1 ? 'rgba(150,170,110,0.18)' : 'rgba(110,130,80,0.12)'; const [a, b] = P([x0 - 60, yy]), [c2, d2] = P([x1, yy + 8]); x.fillRect(a, b, c2 - a, d2 - b); }
  }
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return { tex, box: [cx - half, cy - half, 2 * half, 2 * half] };
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

// Pool, spa, vanishing edge and catch basin: src/pool.js (shaded for Cycles in scripts/water_bpy.py).
function pool(P, grade, colliders) { return buildPool(P, grade, colliders); }

// Coral-stone wall from a polyline; height above local ground, with a cap.
// Runs that meet at a corner overlap there; each successive run drops its cap 1/8" and pulls its ends
// in a hair so no two faces coincide (coincident faces shadow each other and render black in Cycles).
let wallRun = 0;
function stoneWall(W, H, colliders) {
  const g = new THREE.Group();
  for (let i = 0; i < W.pts.length - 1; i++) {
    const [ax, ay] = W.pts[i], [bx, by] = W.pts[i + 1], len = Math.hypot(bx - ax, by - ay);
    const nx = -(by - ay) / len, ny = (bx - ax) / len, probe = [];
    for (const t of [0, 0.5, 1]) for (const s of [-6, -2.5, 2.5, 6]) probe.push(H(ax + (bx - ax) * t + nx * s, ay + (by - ay) * t + ny * s));
    const base = Math.min(...probe) - (W.footing ?? 2.5);
    // thickness stays 1.8 / 2.0 (the pool's basin walls are set 1/8" inside these faces); only the run
    // ends pull back (so an end never lies in the plane of the crossing run's face) and caps step down
    const k = wallRun++ % 4, drop = k * 0.0104, pull = (k + 1) * 0.03;
    const top = (W.top ?? (H(ax, ay) + (W.height ?? 2))) - drop;
    const m = sbox(len + 1.8 - 2 * pull, top - base, 1.8, 'ashlar');
    m.position.set((ax + bx) / 2, (top + base) / 2, (ay + by) / 2); m.rotation.y = -Math.atan2(by - ay, bx - ax); g.add(m);
    const cap = sbox(len + 2.0 - 2 * pull, 0.2, 2.0, 'coral'); cap.position.set((ax + bx) / 2, top + 0.1, (ay + by) / 2); cap.rotation.y = m.rotation.y; g.add(cap);
    colliders.push({ a: [ax, ay], b: [bx, by] });
  }
  return g;
}

// ---------- plants ----------
const frondShape = (() => {
  const s = new THREE.Shape(); s.moveTo(0, -0.08); s.quadraticCurveTo(0.5, -0.5, 1, -0.05); s.lineTo(1, 0.05); s.quadraticCurveTo(0.5, 0.5, 0, 0.08); return s;
})();

// Tall palm: curved ringed trunk, ~16 arching fronds.
export function palm(x, y, ground, height = 30, lean = 1, seed = 0, { trunkR = 0.55, frondLen = 1, fronds = 1, shaft = true, kind = null } = {}) {
  const r = rnd(Math.round(x * 13 + y * 7 + seed));
  const g = new THREE.Group(); g.position.set(x, ground, y);
  if (globalThis.__palmProxies) { globalThis.__palmProxies.push({ x, y, ground, height, lean, seed, trunkR, frondLen, kind: kind ?? (shaft ? 'foxtail' : 'areca') }); return g; }
  if (kind === 'queen' || kind === 'coconut' || kind === 'roebelenii' || kind === 'cycad') shaft = false;
  const leanDir = r() * Math.PI * 2, bend = (0.03 + r() * 0.05) * lean;
  const pts = [];
  for (let k = 0; k <= 12; k++) { const t = k / 12; pts.push(new THREE.Vector3(Math.cos(leanDir) * bend * height * t * t, height * t, Math.sin(leanDir) * bend * height * t * t)); }
  const curve = new THREE.CatmullRomCurve3(pts);
  const trunk = new THREE.Mesh(new THREE.TubeGeometry(curve, 24, trunkR, 10), trunkMat());
  const pos = trunk.geometry.attributes.position;
  for (let i = 0; i < pos.count; i++) { const t = pos.getY(i) / height; const s = 1.15 - t * 0.35; pos.setX(i, pos.getX(i) * s + (1 - s) * pts[Math.min(12, Math.round(t * 12))].x); pos.setZ(i, pos.getZ(i) * s + (1 - s) * pts[Math.min(12, Math.round(t * 12))].z); }
  trunk.geometry.computeVertexNormals();
  g.add(trunk);
  const top = pts[12];
  // smooth green crownshaft under the fronds (foxtail / royal palm)
  if (shaft) { const sh = new THREE.Mesh(new THREE.CylinderGeometry(trunkR * 1.1, trunkR * 1.25, 4.0, 14), mat('#5d6e38')); sh.position.copy(top).add(new THREE.Vector3(0, -2.2, 0)); g.add(sh); }
  const crown = new THREE.Mesh(new THREE.SphereGeometry(trunkR * 1.6, 10, 8), mat('#556b2c')); crown.position.copy(top); g.add(crown);
  const fm = frondMaterial();
  const n = Math.round((16 + Math.floor(r() * 5)) * fronds);
  for (let k = 0; k < n; k++) {
    const len = (10 + r() * 4) * frondLen, a = k / n * Math.PI * 2 + r() * 0.3, droop = 0.35 + r() * 0.65;
    const geo = new THREE.PlaneGeometry(len, len * 0.32, 12, 1);
    geo.rotateX(-Math.PI / 2); geo.translate(len / 2, 0, 0);
    const p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) { const u = Math.max(0, p.getX(i) / len); p.setY(i, p.getY(i) - Math.pow(u, 1.8) * len * (0.3 + droop * 0.35)); }
    geo.computeVertexNormals();
    const fr = new THREE.Group();
    for (const tilt of [-0.45, 0.45]) { const half = new THREE.Mesh(geo, fm); half.rotation.x = tilt; half.castShadow = true; fr.add(half); }
    fr.rotation.x = (r() - 0.5) * 0.4;
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
  const x = c.getContext('2d'); x.fillStyle = '#6f675c'; x.fillRect(0, 0, 64, 256);
  for (let k = 0; k < 256; k += 8) { x.fillStyle = 'rgba(60,45,30,.45)'; x.fillRect(0, k, 64, 2); x.fillStyle = 'rgba(200,185,160,.25)'; x.fillRect(0, k + 3, 64, 2); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 10); t.colorSpace = THREE.SRGBColorSpace;
  tMat = new THREE.MeshStandardMaterial({ name: 'trunk', map: t, roughness: 0.95 });
  return tMat;
}

// pool-deck chaise (p5): the shared teak chaise with welted canvas pads and rolled towels (src/furniture.js)
function loungerInto(g) { chaiseInto(g, 2.3, 6.3); }
