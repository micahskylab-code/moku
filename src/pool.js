// The pool, spa and vanishing-edge waterfall of the back rendering, built at real dimensions.
//
//   - pool: 30 x 13 ft of water, 4.5 ft deep, white-plaster shell, a 6" band of blue glass waterline tile,
//     12" sandstone coping with a bullnose (2 ft pieces, 1/8" joints), entry steps with tiled nosings;
//   - spa: ~7.5 x 8 ft, set into the pool's back wall (pool water wraps its front and left), coping 8" above
//     the pool water, full to 5" below its coping, a bench, six jets and a spill notch into the pool;
//   - vanishing edge on the seaward side: a 10" weir with a rounded wet cap and a 2" tile lip, the falling
//     water as a rain curtain of ~90 streamers (each its own shape, sheeting at the lip, some breaking into
//     drops), a turquoise catch basin 2.5 ft wide 3 ft below with foam and aeration where the water lands.
//
// Water is modelled as closed bodies (pool, spa, basin) whose sides sit 1/4" inside the shell, so Cycles
// sees every wall and step through water and can absorb light along the path (scripts/water_bpy.py shades
// every material named here).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mat } from './materials.js';
import { footprint } from './house.js';

const rnd = seed => () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822519) ^ (seed + 0x9e3779b9)) >>> 0) / 4294967296;

const LIB = {};
function named(name) {
  if (LIB[name]) return LIB[name];
  const S = (o) => new THREE.MeshStandardMaterial(o);
  const make = {
    'pool water': () => mat('water').clone(), 'spa water': () => mat('water').clone(), 'basin water': () => mat('water').clone(),
    'pool plaster': () => S({ color: '#d3e9e8', roughness: 0.6 }),
    'waterline tile': () => S({ color: '#3d6f8a', roughness: 0.08, metalness: 0.0 }),
    'pool coping': () => S({ color: '#d2c0a0', roughness: 0.75 }),
    'weir cap': () => S({ color: '#9d927c', roughness: 0.15 }),
    'falls face': () => S({ color: '#9a917f', roughness: 0.3 }),
    'falls streamer': () => new THREE.MeshPhysicalMaterial({ color: '#e2f5f6', roughness: 0.05, transparent: true, opacity: 0.55, depthWrite: false }),
    'falls foam': () => S({ color: '#f4f8f8', roughness: 0.6, transparent: true, opacity: 0.55, depthWrite: false }),
    'spa jet': () => S({ color: '#c9ccce', roughness: 0.25, metalness: 1 }),
    'pool light lens': () => S({ color: '#f1f3f1', roughness: 0.25 }),
  }[name];
  const m = make(); m.name = name;
  return (LIB[name] = m);
}

// ---------- geometry helpers (plan rect [x0, y0, x1, y1] -> world x / z; heights are world y) ----------
// UVs in feet: tops get (x, z); sides get (along the face, height above vBase), so tile grids line up.
function worldUV(g, vBase = 0) {
  const p = g.attributes.position, n = g.attributes.normal, uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) {
    const nx = Math.abs(n.getX(i)), ny = Math.abs(n.getY(i));
    if (ny > 0.5) uv.setXY(i, p.getX(i), p.getZ(i));
    else uv.setXY(i, nx > 0.5 ? p.getZ(i) : p.getX(i), p.getY(i) - vBase);
  }
  return g;
}
function box([x0, y0, x1, y1], yb, yt, vBase = yb) {
  const g = new THREE.BoxGeometry(Math.abs(x1 - x0), yt - yb, Math.abs(y1 - y0));
  g.translate((x0 + x1) / 2, (yb + yt) / 2, (y0 + y1) / 2);
  return worldUV(g, vBase).toNonIndexed();
}
function cyl(r, h, x, y, z, axis) {
  const g = new THREE.CylinderGeometry(r, r, h, 20);
  if (axis === 'x') g.rotateZ(Math.PI / 2); else if (axis === 'z') g.rotateX(Math.PI / 2);
  g.translate(x, y, z); return g.toNonIndexed();
}
// Closed water body: the plan polygon pts extruded from yb up to the surface yt.
function body(pts, yb, yt) {
  const s = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
  const g = new THREE.ExtrudeGeometry(s, { depth: yt - yb, bevelEnabled: false, curveSegments: 1 });
  g.rotateX(Math.PI / 2); g.translate(0, yt, 0);
  return g;
}

// Coping stone cross-section (across s in [0, w], up t in [0, h]); a full bullnose on the water side(s),
// a 1/4" eased arris elsewhere.
function copingShape(w, h, noseLo, noseHi) {
  const pts = [], r = h / 2, e = 0.02, K = 10;
  pts.push([noseLo ? r : e, 0]);
  if (noseHi) for (let k = 0; k <= K; k++) { const a = -Math.PI / 2 + Math.PI * k / K; pts.push([w - r + r * Math.cos(a), r + r * Math.sin(a)]); }
  else pts.push([w - e, 0], [w, e], [w, h - e], [w - e, h]);
  if (noseLo) for (let k = 0; k <= K; k++) { const a = Math.PI / 2 + Math.PI * k / K; pts.push([r + r * Math.cos(a), r + r * Math.sin(a)]); }
  else pts.push([e, h], [0, h - e], [0, e]);
  return new THREE.Shape(pts.map(([a, b]) => new THREE.Vector2(a, b)));
}
// A run of coping pieces along plan x ('x') or plan y ('y'): across = the other axis from c0 to c1;
// noses: which across side(s) face water ('lo' = c0 side, 'hi' = c1 side).
function copingRun(out, axis, a0, a1, c0, c1, top, h, noses, piece, R) {
  const n = Math.max(1, Math.round((a1 - a0) / piece)), L = (a1 - a0) / n, joint = 0.012, w = c1 - c0, r = h / 2;
  // along x the shape's s axis runs toward -z (a proper rotation), so its low side is c1
  const lo = axis === 'y' ? noses.includes('lo') : noses.includes('hi'), hi = axis === 'y' ? noses.includes('hi') : noses.includes('lo');
  for (let i = 0; i < n; i++) {
    const s0 = a0 + i * L + (i ? joint / 2 : 0), s1 = a0 + (i + 1) * L - (i < n - 1 ? joint / 2 : 0);
    const g = new THREE.ExtrudeGeometry(copingShape(w, h, lo, hi), { depth: s1 - s0, bevelEnabled: false, curveSegments: 1 });
    // smooth normals round the bullnose (the extrusion is faceted)
    const p = g.attributes.position, nn = g.attributes.normal;
    for (let k = 0; k < p.count; k++) {
      if (Math.abs(nn.getZ(k)) > 0.5) continue;
      const s = p.getX(k), t = p.getY(k);
      const c = lo && s < r - 1e-4 ? r : hi && s > w - r + 1e-4 ? w - r : null;
      if (c === null) continue;
      const dx = s - c, dy = t - r, d = Math.hypot(dx, dy) || 1;
      nn.setXYZ(k, dx / d, dy / d, 0);
    }
    // shape (s, t, e) -> world: across s, up t, extrusion e along the run
    const m = new THREE.Matrix4();
    if (axis === 'y') m.set(1, 0, 0, c0, 0, 1, 0, top - h, 0, 0, 1, s0, 0, 0, 0, 1);       // s -> x, e -> z
    else m.set(0, 0, 1, s0, 0, 1, 0, top - h, -1, 0, 0, c1, 0, 0, 0, 1);                    // s -> -z, e -> x
    g.applyMatrix4(m);
    const tint = 0.94 + R() * 0.12, col = new Float32Array(g.attributes.position.count * 3).fill(tint);
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    out.push(g);
  }
}

// One falling stream: an elliptical tube along a path of points; width w and thickness t per ring.
// uv.x = 0 at the lip .. 1 at the bottom, uv.y = around; colour.r = a per-stream random (for the shader).
function tube(path, ws, ts, seed, out) {
  const seg = 8, n = path.length, pos = [], nrm = [], uv = [], col = [], idx = [];
  const A = new THREE.Vector3(0, 0, 1), T = new THREE.Vector3(), N = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    const p = path[i], q = path[Math.min(n - 1, i + 1)], o = path[Math.max(0, i - 1)];
    T.set(q[0] - o[0], q[1] - o[1], q[2] - o[2]).normalize();
    N.crossVectors(T, A).normalize();
    for (let k = 0; k <= seg; k++) {
      const f = 2 * Math.PI * k / seg, c = Math.cos(f), s = Math.sin(f), w = ws[i] / 2, t = ts[i] / 2;
      pos.push(p[0] + A.x * w * c + N.x * t * s, p[1] + A.y * w * c + N.y * t * s, p[2] + A.z * w * c + N.z * t * s);
      const nn = new THREE.Vector3().addScaledVector(A, c / w).addScaledVector(N, s / t).normalize();
      nrm.push(nn.x, nn.y, nn.z); uv.push(i / (n - 1), k / seg); col.push(seed, seed, seed);
    }
  }
  for (let i = 0; i < n - 1; i++) for (let k = 0; k < seg; k++) {
    const a = i * (seg + 1) + k, b = a + seg + 1;
    idx.push(a, a + 1, b, a + 1, b + 1, b);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  out.push(g.toNonIndexed());
}

// Water leaving a rounded lip at (xl, yTop), spilling toward -x and falling to yEnd.
// A short nose wrap, then a ballistic arc; the stream necks down from its sheet width at the lip.
function fallPath(xs, xl, yTop, r, yEnd, z, v0, R, wob) {
  // xs: where the stream starts on the flat top; xl: outer face of the nose (radius r, top at yTop)
  const g = 32.2, f = 0.014, cx = xl + r, cy = yTop - r, rho = r + f, pts = [[xs, yTop + f, z]];
  for (const deg of [0, 28, 52]) { const a = deg * Math.PI / 180; pts.push([cx - rho * Math.sin(a), cy + rho * Math.cos(a), z]); }
  const a = 52 * Math.PI / 180, [x1, y1] = pts[pts.length - 1], vx = -v0 * Math.cos(a), vy = -v0 * Math.sin(a);
  const T = (-vy - Math.sqrt(vy * vy + 2 * g * (y1 - yEnd))) / -g, ph = R() * 6.28, ph2 = R() * 6.28;
  const m = 20;
  for (let i = 1; i <= m; i++) {
    const t = T * Math.pow(i / m, 0.85), d = (y1 - (y1 + vy * t - g * t * t / 2)) / (y1 - yEnd);
    pts.push([x1 + vx * t + wob * d * 0.5 * Math.sin(ph2 + d * 5), y1 + vy * t - g * t * t / 2, z + wob * d * Math.sin(ph + d * 7)]);
  }
  return pts;
}

export function buildPool(P, grade, colliders) {
  const R = rnd(7741);
  const parts = {};
  const add = (name, ...gs) => (parts[name] ??= []).push(...gs);
  const [x0, y0, x1, y1] = P.rect;              // x0: seaward vanishing edge (weir face); y0/y1/x1: tile faces
  const G = grade, W = G - 0.35, depth = 4.5, floor = W - depth;
  const copeTop = G + 0.06, copeH = 0.17, copeBot = copeTop - copeH, band = 0.5, tileT = 0.03, wallT = 0.67;
  const xi0 = x0 + 0.8;                         // weir: 10" thick, its inner face
  const ov = 0.02;                              // water bodies run 1/4" into the shell

  // ---- spa (interior / tile faces), set against the back wall ----
  const SP = P.spa ?? [-23.5, 10.5, x1, 17];
  const [sx0, sy0, , sy1] = SP, sx1 = x1;
  const Ts = W + 0.67, Ws = Ts - 0.42, sFloor = Ws - 3.0;      // coping 8" above pool water, water 5" below it
  const so = { x0: sx0 - wallT, y0: sy0 - wallT, y1: sy1 + wallT };   // spa outer wall faces
  const notch = [(sy0 + sy1) / 2 - 0.75, (sy0 + sy1) / 2 + 0.75];

  // ---- pool shell: floor, walls (plaster), waterline tile band ----
  add('pool plaster', box([xi0, y0, x1, y1], floor - 0.5, floor));
  add('pool plaster', box([x1, y0 - wallT, x1 + wallT, y1 + wallT], floor - 0.5, copeBot));                // back
  add('pool plaster', box([x0, y0 - wallT, x1, y0], floor - 0.5, copeBot));                                 // ends
  add('pool plaster', box([x0, y1, x1, y1 + wallT], floor - 0.5, copeBot));
  const tb = copeBot - band;
  for (const [a, b] of [[y0, so.y0], [so.y1, y1]]) add('waterline tile', box([x1 - tileT, a, x1, b], tb, copeBot, copeBot));
  add('waterline tile', box([x0, y0, x1, y0 + tileT], tb, copeBot, copeBot));
  add('waterline tile', box([x0, y1 - tileT, x1, y1], tb, copeBot, copeBot));
  // entry steps: four 12" treads x 11" risers off the back wall right of the spa, three left of it;
  // each tread has a 2" dark tile nosing so the steps read through the water
  const steps = (ya, yb, k) => {
    for (let i = 1; i <= k; i++) {
      const top = W - 0.9 * i, xa = x1 - i, xb = x1 - (i - 1);
      add('pool plaster', box([xa, ya, xb, yb], floor, top));
      add('waterline tile', box([xa, ya, xa + 0.17, yb], top - 0.004, top + 0.006, top));
      add('waterline tile', box([xa - 0.006, ya, xa, yb], top - 0.17, top, top - 0.17));
    }
  };
  steps(so.y1 + 0.08, so.y1 + 6.08, 4);
  steps(y0, so.y0 - 0.08, 3);
  // a 15" bench along the spa's seaward face, 18" under the water
  add('pool plaster', box([so.x0 - 1.25, sy0 - wallT, so.x0, sy1 + wallT], floor, W - 1.5));
  add('waterline tile', box([so.x0 - 1.25, sy0 - wallT, so.x0 - 1.08, sy1 + wallT], W - 1.504, W - 1.494, W - 1.5));
  // main drains and pool lights
  const dx = (xi0 + so.x0 - 1.25) / 2;
  for (const yy of [(y0 + y1) / 2 - 1.5, (y0 + y1) / 2 + 1.5]) add('pool light lens', box([dx - 0.375, yy - 0.375, dx + 0.375, yy + 0.375], floor - 0.01, floor + 0.02));
  const lights = [[x1 - 0.02, (so.y1 + 6.1 + y1) / 2, 'x'], [x0 + 5, y0 + 0.02, 'z']];
  for (const [x, yy, ax] of lights) { add('spa jet', cyl(0.46, 0.04, x, W - 2.4, yy, ax)); add('pool light lens', cyl(0.38, 0.06, x, W - 2.4, yy, ax)); }
  for (const [x, yy, ax] of [[x1 - 0.02, y1 - 1.5, 'x'], [x0 + 9, y0 + 0.02, 'z'], [x0 + 6, y1 - 0.02, 'z']]) add('spa jet', cyl(0.09, 0.06, x, W - 1.3, yy, ax));

  // ---- the spa ----
  const spillBot = Ws - 0.02 - copeH;
  for (const [a, b, t] of [[so.y0, notch[0], Ts - copeH], [notch[0], notch[1], spillBot], [notch[1], so.y1, Ts - copeH]])
    add('pool plaster', box([so.x0, a, sx0, b], floor, t));                                // seaward wall, notched
  add('pool plaster', box([sx0, so.y0, sx1, sy0], floor, Ts - copeH));                     // side walls
  add('pool plaster', box([sx0, sy1, sx1, so.y1], floor, Ts - copeH));
  add('pool coping', box([x1, so.y0, x1 + wallT, so.y1], copeBot, Ts - copeH));            // back upstand to the spa coping
  add('pool plaster', box([sx0, sy0, sx1, sy1], sFloor - 0.5, sFloor));                   // floor
  for (const r of [[sx0, sy0, sx0 + 1.25, sy1], [sx1 - 1.25, sy0, sx1, sy1], [sx0 + 1.25, sy0, sx1 - 1.25, sy0 + 1.25], [sx0 + 1.25, sy1 - 1.25, sx1 - 1.25, sy1]])
    add('pool plaster', box(r, sFloor, Ws - 1.6));                                         // bench all round
  const sb = Ts - copeH - band, stb = Ts - copeH;
  add('waterline tile', box([sx0, sy0, sx0 + tileT, notch[0]], sb, stb, stb));              // inside band
  add('waterline tile', box([sx0, notch[1], sx0 + tileT, sy1], sb, stb, stb));
  add('waterline tile', box([sx1 - tileT, sy0, sx1, sy1], sb, stb, stb));
  add('waterline tile', box([sx0, sy0, sx1, sy0 + tileT], sb, stb, stb));
  add('waterline tile', box([sx0, sy1 - tileT, sx1, sy1], sb, stb, stb));
  const ob = W - 0.25;                                                                     // outside band, down into the pool water
  add('waterline tile', box([so.x0 - tileT, so.y0 - tileT, so.x0, notch[0]], ob, stb, stb));
  add('waterline tile', box([so.x0 - tileT, notch[0], so.x0, notch[1]], ob, spillBot, spillBot));
  add('waterline tile', box([so.x0 - tileT, notch[1], so.x0, so.y1 + tileT], ob, stb, stb));
  add('waterline tile', box([so.x0, so.y0 - tileT, x1, so.y0], ob, stb, stb));
  add('waterline tile', box([so.x0, so.y1, x1, so.y1 + tileT], ob, stb, stb));
  // spill notch: the seaward wall and coping drop to a spill stone just under the spa water
  for (const yy of [sy0 + 2.2, sy1 - 2.2]) add('spa jet', cyl(0.09, 0.07, sx0 + 0.02, Ws - 1.15, yy, 'x'));
  for (const xx of [sx0 + 2.2, sx1 - 2.2]) { add('spa jet', cyl(0.09, 0.07, xx, Ws - 1.15, sy0 + 0.02, 'z')); add('spa jet', cyl(0.09, 0.07, xx, Ws - 1.15, sy1 - 0.02, 'z')); }

  // ---- coping: 12" sandstone, 2" thick, bullnosed to the water, 2 ft pieces ----
  const cope = [], cw = 1.0, in_ = 0.08;
  copingRun(cope, 'y', y0 - cw + in_, so.y0 - 0.25, x1 - in_, x1 - in_ + cw, copeTop, copeH, 'lo', 2.0, R);
  copingRun(cope, 'y', so.y1 + 0.25, y1 + cw - in_, x1 - in_, x1 - in_ + cw, copeTop, copeH, 'lo', 2.0, R);
  copingRun(cope, 'x', x0, x1 - in_, y0 - cw + in_, y0 + in_, copeTop, copeH, 'hi', 2.0, R);
  copingRun(cope, 'x', x0, x1 - in_, y1 - in_, y1 - in_ + cw, copeTop, copeH, 'lo', 2.0, R);
  const sc0 = so.x0 - 0.25, sc0y = so.y0 - 0.25, sc1y = so.y1 + 0.25;
  // spa coping: both edges are water; the seaward run leaves the spill notch
  copingRun(cope, 'y', sc0y, notch[0] - 0.006, sc0, sx0 + in_, Ts, copeH, 'lohi', 2.0, R);
  copingRun(cope, 'y', notch[1] + 0.006, sc1y, sc0, sx0 + in_, Ts, copeH, 'lohi', 2.0, R);
  copingRun(cope, 'y', notch[0], notch[1], sc0, sx0 + in_, Ws - 0.02, copeH, 'lo', 2.0, R);      // spill stone
  copingRun(cope, 'x', sx0 + in_ + 0.006, x1 + cw - in_, sc0y, sy0 + in_, Ts, copeH, 'lohi', 2.0, R);
  copingRun(cope, 'x', sx0 + in_ + 0.006, x1 + cw - in_, sy1 - in_, sc1y, Ts, copeH, 'lohi', 2.0, R);
  copingRun(cope, 'y', sy0 + in_ + 0.006, sy1 - in_ - 0.006, x1 - in_, x1 - in_ + cw, Ts, copeH, 'lo', 2.0, R);
  add('pool coping', ...cope.splice(0));

  // ---- water bodies ----
  const notchX = so.x0 + 0.02;
  add('pool water', body([[x0 + 0.04, y0 - ov], [x1 + ov, y0 - ov], [x1 + ov, so.y0 + ov], [so.x0 + ov, so.y0 + ov], [so.x0 + ov, so.y1 - ov],
    [x1 + ov, so.y1 - ov], [x1 + ov, y1 + ov], [x0 + 0.04, y1 + ov]], floor - ov, W));
  add('spa water', body([[sx0 - ov, sy0 - ov], [sx1 + ov, sy0 - ov], [sx1 + ov, sy1 + ov], [sx0 - ov, sy1 + ov], [sx0 - ov, notch[1]], [notchX, notch[1]], [notchX, notch[0]], [sx0 - ov, notch[0]]], sFloor - ov, Ws));
  // the spa's spill: a clear sheet over the spill stone's nose into the pool
  const fall = [];
  { const pts = fallPath(notchX, sc0, Ws - 0.02, copeH / 2, W - 0.08, (notch[0] + notch[1]) / 2, 0.8, R, 0.0);
    tube(pts, pts.map((_, i) => 1.47 - i * 0.006), pts.map((_, i) => (i < 4 ? 0.022 : 0.03)), 0.5, fall); }

  // ---- vanishing edge: weir, falls, catch basin, retaining wall ----
  if (P.edge === 'x0') {
    const drop = P.drop ?? 3, Wb = W - drop, bFloor = Wb - 1.5, xb = x0 - 2.5;     // catch basin 2.5 ft wide
    const capTop = W - 0.03, capH = 0.15;
    add('pool plaster', box([x0 + 0.06, y0, xi0, y1], floor - 0.5, capTop - capH));
    copingRun(cope, 'y', y0, y1, x0 - 0.02, xi0, capTop, capH, 'lo', 2.0, R);
    add('weir cap', ...cope.splice(0));
    add('waterline tile', box([x0, y0, x0 + 0.06, y1], W - 0.35, capTop - capH, W - 0.35));        // 2" tile lip
    add('falls face', box([x0, y0, x0 + 0.06, y1], Wb - 0.2, W - 0.35, Wb - 0.2));                 // wet stone face
    add('pool plaster', box([x0, y0, x0 + 0.06, y1], bFloor, Wb - 0.2));
    // basin: plaster floor, the retaining wall (coral stone, its lip 3" above the basin water), coping
    add('pool plaster', box([xb, y0, x0, y1], bFloor - 0.6, bFloor));
    const lip = Wb + 0.25, foot = G - 9;
    const g = new THREE.Group();
    const rw = new THREE.Mesh(box([x0 - 4.3, y0 - 3, xb, y1 + 3], foot, lip), mat('ashlar')); g.add(rw);
    add('pool plaster', box([xb, y0, xb + 0.04, y1], bFloor, Wb - 0.3));
    copingRun(cope, 'y', y0, y1, x0 - 4.38, xb + 0.08, lip + copeH, copeH, 'hi', 3.0, R);
    add('pool coping', ...cope.splice(0));
    // stone ends close the basin where the lawn is cut away for it (as high as the garden walls)
    const eTop = G + 0.35;
    for (const [ya, yb] of [[y0 - 0.6, y0], [y1, y1 + 0.6]]) {
      const ew = new THREE.Mesh(box([x0 - 4.3, ya, x0, yb], bFloor - 0.6, eTop), mat('ashlar')); g.add(ew);
      const cap = new THREE.Mesh(box([x0 - 4.4, ya - 0.1, x0 + 0.02, yb + 0.1], eTop, eTop + 0.2), mat('coral')); g.add(cap);
    }
    add('basin water', (() => {
      const b = body([[xb - ov, y0 - ov], [x0 + ov, y0 - ov], [x0 + ov, y1 + ov], [xb - ov, y1 + ov]], bFloor - ov, Wb);
      const p = b.attributes.position, uv = b.attributes.uv;            // u = ft out from the falls, v = along
      for (let i = 0; i < uv.count; i++) uv.setXY(i, x0 - p.getX(i), p.getZ(i));
      return b;
    })());
    // the rain curtain: the sheet leaves the rounded cap and breaks into streams of 1/2"-5", some
    // pairs and threads, the odd one breaking into drops before the basin
    let z = y0 + 0.05;
    while (z < y1 - 0.1) {
      const gap = 0.12 + R() * 0.55 + (R() < 0.15 ? R() * 0.5 : 0), share = Math.min(gap, y1 - 0.05 - z);
      const zc = z + share / 2, w = Math.min(share * 0.9, 0.03 + Math.pow(R(), 1.6) * 0.38), v0 = 0.7 + R() * 0.9, seed = R();
      const brk = R() < 0.3 ? 0.6 + R() * 0.3 : 1.0, end = Wb - 0.12;
      const pts = fallPath(x0 + 0.04, x0 - 0.02, capTop, capH / 2, end, zc, v0, R, 0.012 + R() * 0.03);
      const n = pts.length, cut = Math.max(6, Math.round(n * brk));
      const hold = 6 + R() * 10, y0p = pts[0][1];
      const ws = pts.map(p => { const f = (y0p - p[1]) / (y0p - end), k = Math.exp(-f * hold); return share * 1.01 * k + w * (1 - k) * (1 - 0.3 * f); });
      const ts = ws.map((ww, i) => Math.min(Math.max(0.018, ww * 0.55), 0.07) * (i < 2 ? 0.6 : 1));
      tube(pts.slice(0, cut), ws.slice(0, cut), ts.slice(0, cut), seed, fall);
      for (let k = cut; k < n - 1; k += 2 + Math.floor(R() * 2)) {           // drops: short necked lengths
        const seg = pts.slice(k, Math.min(n, k + 2)).map(p => [p[0], p[1], p[2]]);
        if (seg.length < 2) break;
        const ww = ws[k] * 0.7, tt = ts[k] * 0.8;
        tube(seg, [ww * 0.4, ww * 0.5], [tt * 0.5, tt * 0.6], seed, fall);
      }
      z += gap;
    }
    // foam and aeration where the streams land; a milky cloud of bubbles just under the surface
    for (const [yy, ww, ofs] of [[Wb + 0.012, 0.75, 0.0], [Wb - 0.12, 1.1, 0.0]]) {
      const pg = new THREE.PlaneGeometry(ww, y1 - y0 - 0.1, 8, 240);
      pg.rotateX(-Math.PI / 2);
      const p = pg.attributes.position, uv = pg.attributes.uv;
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i) + x0 - 0.04 - ww / 2 + ofs, zz = p.getZ(i) + (y0 + y1) / 2;
        p.setXYZ(i, x, yy + (yy > Wb ? 0.025 * Math.max(0, Math.sin(zz * 9.1 + x * 13) * Math.sin(zz * 3.3 - x * 7)) : 0), zz);
        uv.setXY(i, x0 - x, zz);
      }
      pg.computeVertexNormals();
      add('falls foam', pg.toNonIndexed());
    }
    rw.receiveShadow = true;
    parts.__group = g;
  }
  for (const g of fall) add('falls streamer', g);

  // ---- assemble: one mesh per material ----
  const out = parts.__group ?? new THREE.Group(); delete parts.__group;
  for (const [name, list] of Object.entries(parts)) {
    const keys = [...new Set(list.flatMap(g => Object.keys(g.attributes)))];
    const geos = list.map(g => { const h = g.index ? g.toNonIndexed() : g; for (const k of Object.keys(h.attributes)) if (!keys.includes(k)) h.deleteAttribute(k); return h; });
    for (const h of geos) for (const k of keys) if (!h.attributes[k]) h.setAttribute(k, new THREE.BufferAttribute(new Float32Array(h.attributes.position.count * (k === 'uv' ? 2 : 3)).fill(1), k === 'uv' ? 2 : 3));
    const m = new THREE.Mesh(mergeGeometries(geos, false), named(name));
    m.name = name;
    if (name.endsWith('water')) m.renderOrder = 3;
    out.add(m);
  }

  // ---- lounger pad: 24" limestone pavers beside the pool's near end ----
  const pad = new THREE.Mesh(box([x0 - 0.2, -5.9, x1 - 4.5, y0 - cw + in_], G - 0.08, G + 0.04), mat('pavers'));
  out.add(pad);
  colliders.push(...footprint({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, w: x1 - x0, d: y1 - y0 }));
  return out;
}
