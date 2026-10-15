// Planting built from leaf "cards": many small alpha-textured quads per shrub, merged per bed.
// Reads as foliage at walking distance instead of faceted blobs.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const rnd = seed => () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822519) ^ (seed + 0x9e3779b9)) >>> 0) / 4294967296;
const texCache = new Map();

// Export for the path tracer: plants are only recorded (kind, place, size, seed) and grown leaf by
// leaf in Blender (scripts/plants_bpy.py), like the palms. Only while exporting (main.js sets
// globalThis.__palmProxies), so the live walkthrough is unchanged.
export const recording = () => !!globalThis.__palmProxies;
export function recordPlant(p) { (globalThis.__plantProxies ??= []).push(p); }

const KINDS = {
  bougainvillea: { leaf: ['#2f5a22', '#3d6b2a', '#4a7a30'], bloom: ['#b0388f', '#9c3486', '#c24a98', '#8f3a8c'], bloomShare: 0.45, size: [2.6, 4.2], cards: 22 },
  gardenia: { leaf: ['#244d1c', '#2f5d22', '#3a6a29'], bloom: ['#fbf8ef', '#f4efe0'], bloomShare: 0.16, bloomShape: 'star', size: [2.0, 3.0], cards: 18 },
  hedge: { leaf: ['#2a5420', '#356326', '#3f6e2c'], bloom: [], bloomShare: 0, size: [3.0, 4.5], cards: 22 },
  screen: { leaf: ['#284f1e', '#325e24', '#3c6a2a'], bloom: [], bloomShare: 0, size: [6.5, 7.5], cards: 34 },   // 7 ft lot-line screen hedge
  groundcover: { leaf: ['#3e6e2c', '#4b7d33'], bloom: ['#f3ecda'], bloomShare: 0.08, size: [1.0, 1.4], cards: 8 },
  monstera: { leaf: ['#1f4a1d', '#2a5a24'], bloom: [], bloomShare: 0, big: true, size: [2.6, 3.6], cards: 12 },
  plumeria: { leaf: ['#3a6a2a', '#4a7a31', '#2f5a24'], bloom: ['#fffaf0', '#fff4d6'], bloomShare: 0.35, bloomShape: 'star', size: [2.4, 3.2], cards: 14 },
  // low groundcovers and accents (scripts/plants_bpy.py grows the real ones)
  mondo: { leaf: ['#3c5832', '#4e6e42', '#6e8e58'], bloom: [], bloomShare: 0, size: [0.8, 1.1], cards: 6 },
  jasmine: { leaf: ['#1f3a18', '#2c4a20', '#3f6a2e'], bloom: [], bloomShare: 0, size: [1.2, 1.6], cards: 8 },
  dichondra: { leaf: ['#8a967a', '#9da87e', '#b4bea0'], bloom: [], bloomShare: 0, size: [0.8, 1.1], cards: 6 },
  tradescantia: { leaf: ['#4a2050', '#6b3a7a', '#5a2a62'], bloom: [], bloomShare: 0, size: [0.9, 1.2], cards: 6 },
  alocasia: { leaf: ['#2a5222', '#3a6a2c', '#4a7634'], bloom: [], bloomShare: 0, big: true, size: [3.0, 4.2], cards: 8 },
  heliconia: { leaf: ['#2a5a1e', '#3a6a26', '#4f7f30'], bloom: ['#c42a1c', '#d8c040'], bloomShare: 0.1, big: true, size: [3.0, 5.0], cards: 10 },
  hibiscus: { leaf: ['#1f4317', '#2f5d22', '#3a6a29'], bloom: ['#c8202a', '#b01c26'], bloomShare: 0.12, bloomShape: 'star', size: [3.5, 5.0], cards: 18 },
};

export function foliageTexture(kind) {
  if (texCache.has(kind)) return texCache.get(kind);
  const K = KINDS[kind], S = 512, c = document.createElement('canvas'); c.width = c.height = S;
  const x = c.getContext('2d'), r = rnd(kind.length * 977);
  const leaf = (cx, cy, len, wid, ang, col) => {
    x.save(); x.translate(cx, cy); x.rotate(ang); x.fillStyle = col;
    x.beginPath(); x.moveTo(0, 0); x.quadraticCurveTo(wid, len * 0.45, 0, len); x.quadraticCurveTo(-wid, len * 0.45, 0, 0); x.fill();
    x.strokeStyle = 'rgba(255,255,255,.12)'; x.lineWidth = 1; x.beginPath(); x.moveTo(0, 2); x.lineTo(0, len - 3); x.stroke();
    x.restore();
  };
  const n = K.big ? 26 : 340;
  for (let i = 0; i < n; i++) {
    const a = r() * Math.PI * 2, d = Math.sqrt(r()) * S * 0.44;
    const px = S / 2 + Math.cos(a) * d, py = S / 2 + Math.sin(a) * d;
    if (K.big) leaf(px, py, 120 + r() * 60, 70 + r() * 30, r() * 6.28, K.leaf[i % K.leaf.length]);
    else leaf(px, py, 22 + r() * 18, 9 + r() * 6, r() * 6.28, K.leaf[Math.floor(r() * K.leaf.length)]);
  }
  const blooms = Math.round(n * K.bloomShare);
  for (let i = 0; i < blooms; i++) {
    const a = r() * Math.PI * 2, d = Math.sqrt(r()) * S * 0.42;
    const px = S / 2 + Math.cos(a) * d, py = S / 2 + Math.sin(a) * d, col = K.bloom[Math.floor(r() * K.bloom.length)];
    if (K.bloomShape === 'star') {
      for (let p = 0; p < 5; p++) leaf(px, py, 11 + r() * 3, 6, p * 1.2566 + r() * 0.2, col);
      x.fillStyle = '#f2c84b'; x.beginPath(); x.arc(px, py, 2.5, 0, 7); x.fill();
    } else {
      for (let p = 0; p < 3; p++) leaf(px, py, 15 + r() * 6, 11, p * 2.094 + r(), col);
    }
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  const m = new THREE.MeshStandardMaterial({ name: `foliage-${kind}`, map: t, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.8 });
  texCache.set(kind, m);
  return m;
}

// One shrub as a set of cards inside an ellipsoid; returns a geometry (not yet merged).
function shrubGeometry(x, y, z, s, K, r) {
  const parts = [];
  const n = K.cards;
  for (let i = 0; i < n; i++) {
    const g = new THREE.PlaneGeometry(s * 0.75, s * 0.75);
    const e = new THREE.Euler(r() * Math.PI, r() * Math.PI * 2, r() * Math.PI);
    g.applyMatrix4(new THREE.Matrix4().makeRotationFromEuler(e));
    const a = r() * Math.PI * 2, d = Math.sqrt(r()) * s * 0.32, h = r();
    g.translate(x + Math.cos(a) * d, z + s * (0.18 + h * 0.5), y + Math.sin(a) * d);
    parts.push(g);
  }
  return parts;
}

export function plantBed(B, H) {
  const K = KINDS[B.kind];
  const g = new THREE.Group();
  const [x0, y0, x1, y1] = B.rect, r = rnd(Math.round(x0 * 31 + y0 * 11 + 7));
  // curved sides / no edging travel to Blender in the kind ('mondo@y0', 'ti@!'; parsed by scripts/plants_bpy.py)
  const spec = (B.curve ?? '') + (B.edge === false ? '!' : '');
  if (recording()) { recordPlant({ type: 'bed', kind: spec ? `${B.kind}@${spec}` : B.kind, rect: B.rect, density: B.density ?? 1.1, ground: H((x0 + x1) / 2, (y0 + y1) / 2), seed: Math.round(x0 * 31 + y0 * 11 + 7), shell: true }); return g; }
  if (B.kind === 'ti') return tiBed(B, H, r);
  if (!K) return g;
  const area = (x1 - x0) * (y1 - y0), n = Math.max(1, Math.round(area / (K.size[0] * K.size[0]) * (B.density ?? 1.1)));
  const parts = [];
  for (let k = 0; k < n; k++) {
    const x = x0 + r() * (x1 - x0), y = y0 + r() * (y1 - y0), s = K.size[0] + r() * (K.size[1] - K.size[0]);
    parts.push(...shrubGeometry(x, y, H(x, y), s, K, r));
  }
  const mesh = new THREE.Mesh(mergeGeometries(parts), foliageTexture(B.kind));
  mesh.castShadow = true; mesh.receiveShadow = true;
  g.add(mesh);
  return g;
}

// Red ti plants: upright fans of long glossy leaves.
const tiLeaf = (() => { const s = new THREE.Shape(); s.moveTo(-0.12, 0); s.quadraticCurveTo(-0.32, 1.1, 0, 2.2); s.quadraticCurveTo(0.32, 1.1, 0.12, 0); return new THREE.ShapeGeometry(s, 5); })();
function tiBed(B, H, r) {
  const [x0, y0, x1, y1] = B.rect;
  const n = Math.max(1, Math.round((x1 - x0) * (y1 - y0) / 3.2));
  const cols = [new THREE.Color('#9a1e2e'), new THREE.Color('#c8304a'), new THREE.Color('#6a1a2a'), new THREE.Color('#7d2a3a'), new THREE.Color('#4f6a2e')];
  const parts = [], colors = [];
  for (let k = 0; k < n; k++) {
    const x = x0 + r() * (x1 - x0), y = y0 + r() * (y1 - y0), base = H(x, y), s = 0.6 + r() * 0.8, stem = 0.6 + r() * 2.2;
    for (let j = 0; j < 14; j++) {
      const g = tiLeaf.clone();
      g.scale(s, s * (0.8 + r() * 0.4), s);
      g.applyMatrix4(new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(-0.15 - r() * 1.1, r() * Math.PI * 2, 0, 'YXZ')));
      g.translate(x, base + stem, y);
      const c = cols[Math.floor(r() * cols.length)];
      const cnt = g.attributes.position.count, arr = new Float32Array(cnt * 3);
      for (let i = 0; i < cnt; i++) arr.set([c.r, c.g, c.b], i * 3);
      g.setAttribute('color', new THREE.BufferAttribute(arr, 3));
      parts.push(g);
    }
    const st = new THREE.CylinderGeometry(0.05, 0.07, stem, 5); st.translate(x, base + stem / 2, y);
    const cnt = st.attributes.position.count, arr = new Float32Array(cnt * 3).fill(0.35); st.setAttribute('color', new THREE.BufferAttribute(arr, 3));
    st.deleteAttribute('normal'); st.computeVertexNormals();
    parts.push(st.toNonIndexed ? st : st);
  }
  const geo = mergeGeometries(parts.map(p => p.index ? p.toNonIndexed() : p));
  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ name: 'foliage-ti', vertexColors: true, side: THREE.DoubleSide, roughness: 0.45 }));
  mesh.castShadow = true; mesh.receiveShadow = true;
  const g = new THREE.Group(); g.add(mesh); return g;
}

// Plumeria: forked grey branches ending in leaf-and-flower clusters.
export function plumeria(x, y, ground, s = 1) {
  const r = rnd(Math.round(x * 17 + y * 3 + 11));
  const g = new THREE.Group(); g.position.set(x, ground, y); g.scale.setScalar(s);
  if (recording()) { recordPlant({ type: 'plumeria', x, y, ground, scale: s, seed: Math.round(x * 17 + y * 3 + 11), shell: true }); return g; }
  const bark = new THREE.MeshStandardMaterial({ color: '#6e665c', roughness: 0.9 });
  const tips = [];
  const branch = (from, dir, len, depth) => {
    const to = from.clone().addScaledVector(dir, len);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.1 * depth, 0.14 * depth, len, 7), bark);
    m.position.copy(from).lerp(to, 0.5); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize()); g.add(m);
    if (depth <= 1) { tips.push(to); return; }
    for (let k = 0; k < 2 + (r() > 0.4 ? 1 : 0); k++) branch(to, new THREE.Vector3(dir.x + (r() - 0.5) * 1.5, dir.y + 0.25, dir.z + (r() - 0.5) * 1.5).normalize(), len * 0.72, depth - 1);
  };
  branch(new THREE.Vector3(), new THREE.Vector3(0, 1, 0), 3.2, 4);
  const parts = [];
  for (const t of tips) parts.push(...shrubGeometry(t.x, t.z, t.y - 0.9, 2.6 + r() * 0.6, KINDS.plumeria, r));
  const crown = new THREE.Mesh(mergeGeometries(parts), foliageTexture('plumeria'));
  g.add(crown);
  g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  g.userData.tree = true;   // the model view can hide trees (src/inspect.js)
  return g;
}

// Feathery palm frond texture (alpha leaflets on a rachis).
let frondMat = null;
export function frondMaterial() {
  if (frondMat) return frondMat;
  const c = document.createElement('canvas'); c.width = 1024; c.height = 256;
  const x = c.getContext('2d'), r = rnd(42);
  x.strokeStyle = '#5a5a2a'; x.lineWidth = 6; x.beginPath(); x.moveTo(0, 128); x.lineTo(1024, 128); x.stroke();
  for (let i = 0; i < 150; i++) {
    const t = i / 150, px = 14 + t * 1000, len = 118 * Math.sin(Math.PI * Math.min(1, t * 1.1 + 0.06)) + 10;
    for (const s of [-1, 1]) {
      const col = ['#2e5a1c', '#3a6a22', '#466f26', '#33601f'][Math.floor(r() * 4)];
      x.strokeStyle = col; x.lineWidth = 3 + r() * 1.5; x.lineCap = 'round';
      const bend = (r() - 0.5) * 0.25;
      x.beginPath(); x.moveTo(px, 128); x.quadraticCurveTo(px + len * (0.3 + bend), 128 + s * len * 0.55, px + len * (0.55 + bend), 128 + s * len); x.stroke();
    }
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  frondMat = new THREE.MeshStandardMaterial({ name: 'foliage-frond', map: t, alphaTest: 0.35, side: THREE.DoubleSide, roughness: 0.7 });
  return frondMat;
}
