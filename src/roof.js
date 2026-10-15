// Roofs: hip, gable and shed roofs over rectangles of wall lines (plan feet), built as real geometry.
// Where roofs overlap, the house is their union: each roof plane keeps exactly the part that is the
// highest surface there (convex polygon clipping, no per-pixel tricks), so valleys, wings running into
// the main hip and the vaulted ceilings inside meet cleanly in any renderer, the Blender export included.
//
// What a standing-seam roof on these pavilions is made of (front and back renderings):
//  - panels 16" wide with 1 1/4" standing seams (real ribs, world-aligned along the eave, matching the
//    rib grid of scripts/materials_bpy.py r_standing_seam), formed hip and ridge caps in the roof colour;
//  - a 6" metal fascia in the roof colour, a 5" K-style gutter on every eave, 3" round downspouts with
//    a gooseneck back to the wall at chosen corners;
//  - Dutch gables (`dutch`: the skirt's run in ft): the hip skirt runs up-slope from the eave, then a
//    gable rides the ridge and ends in a vertical gable wall filled with a recessed louvered vent;
//  - roof openings (`holes`) over the garden showers: cedar-lined well with 2x6 slats.
import * as THREE from 'three';
import { mat } from './materials.js';

export const ROOF_T = 0.6;      // ceiling plane to metal surface, ft
export const SEAM = 4 / 3;      // standing seams 16" on centre
const EPS = 0.004;
const TYPE = { hip: 0, gableX: 1, gableY: 2, shed: 3 };

// ---------------------------------------------------------------------------------- own finishes
const own = new Map();
function finish(name, color, roughness, metalness = 0, extra = {}) {
  if (!own.has(name)) own.set(name, new THREE.MeshStandardMaterial({ name, color, roughness, metalness, ...extra }));
  return own.get(name);
}
const SEAM_M = () => finish('roofSeam', '#80858b', 0.42, 0.2);            // ribs, hip and ridge caps: the roof's paint
const GUTTER_M = () => finish('gutter', '#36393d', 0.4, 0.3);             // K-style gutters, downspouts: dark bronze
const LOUVER_M = () => finish('gableLouver', '#7b8086', 0.5, 0.15);       // gable vent blades: roof colour
const CAVITY_M = () => finish('gableCavity', '#121314', 0.95);            // the dark attic behind the vent
const FLASH_M = () => finish('flashing', '#6f7378', 0.4, 0.3);            // valley pans, curbs

// ---------------------------------------------------------------------------------- 2D polygon helpers
const area = P => { let a = 0; for (let i = 0; i < P.length; i++) { const A = P[i], B = P[(i + 1) % P.length]; a += A[0] * B[1] - B[0] * A[1]; } return a / 2; };
function clip(P, a, b, c) {               // keep a x + b y + c >= 0
  const out = [];
  for (let i = 0; i < P.length; i++) {
    const A = P[i], B = P[(i + 1) % P.length];
    const da = a * A[0] + b * A[1] + c, db = a * B[0] + b * B[1] + c;
    if (da >= 0) out.push(A);
    if ((da >= 0) !== (db >= 0)) { const t = da / (da - db); out.push([A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t]); }
  }
  const q = out.filter((p, i) => { const r = out[(i + 1) % out.length]; return Math.hypot(p[0] - r[0], p[1] - r[1]) > 1e-7; });
  return q.length >= 3 ? q : null;
}
function clipAll(P, H) { for (const h of H) { P = clip(P, ...h); if (!P) return null; } return P; }
// A \ (intersection of half-planes H), for every convex piece of `pieces`; the result is convex pieces.
function subtract(pieces, H) {
  const out = [];
  for (const A of pieces) {
    const inter = clipAll(A, H);
    if (!inter || Math.abs(area(inter)) < 1e-6) { out.push(A); continue; }
    let rest = A;
    for (const [a, b, c] of H) {
      const o = clip(rest, -a, -b, -c);
      if (o && Math.abs(area(o)) > 1e-6) out.push(o);
      rest = clip(rest, a, b, c);
      if (!rest) break;
    }
  }
  return out;
}
const rectHalf = ([x0, y0, x1, y1]) => [[1, 0, -x0], [-1, 0, x1], [0, 1, -y0], [0, -1, y1]];
function inConvex(P, x, y) {
  let s = 0;
  for (let i = 0; i < P.length; i++) {
    const A = P[i], B = P[(i + 1) % P.length];
    const cr = (B[0] - A[0]) * (y - A[1]) - (B[1] - A[1]) * (x - A[0]);
    if (Math.abs(cr) < 1e-9) continue;
    const g = Math.sign(cr);
    if (!s) s = g; else if (g !== s) return false;
  }
  return true;
}
// Runs of t in [0, 1] where test(t) holds, ends refined by bisection.
function runs(len, test, step = 0.08) {
  const n = Math.max(2, Math.ceil(len / step)), v = [];
  for (let i = 0; i <= n; i++) v.push(test(i / n));
  const edge = (a, b, va) => { for (let k = 0; k < 14; k++) { const m = (a + b) / 2; if (test(m) === va) a = m; else b = m; } return (a + b) / 2; };
  const out = [];
  for (let i = 0; i <= n; i++) {
    if (!v[i] || (i > 0 && v[i - 1])) continue;
    let j = i; while (j < n && v[j + 1]) j++;
    const t0 = i === 0 ? 0 : edge(i / n, (i - 1) / n, true), t1 = j === n ? 1 : edge(j / n, (j + 1) / n, true);
    if ((t1 - t0) * len > 0.05) out.push([t0, t1]);
    i = j;
  }
  return out;
}

// ---------------------------------------------------------------------------------- geometry accumulator
// One-sided quad wound so its normal points along `want`. Thin linings are one face, never a pair of
// coincident faces back to back: in Cycles each of a coincident pair shadows the other and both go black.
function quadToward(acc, a, b, c, d, want) {
  const n = cross([b[0] - a[0], b[1] - a[1], b[2] - a[2]], [c[0] - a[0], c[1] - a[1], c[2] - a[2]]);
  if (dot(n, want) >= 0) acc.quad(a, b, c, d); else acc.quad(d, c, b, a);
}

class Acc {
  constructor() { this.pos = []; this.uv = []; }
  tri(a, b, c, ua = [0, 0], ub = [0, 0], uc = [0, 0]) { this.pos.push(...a, ...b, ...c); this.uv.push(...ua, ...ub, ...uc); }
  quad(a, b, c, d, uvs) { const u = uvs ?? [[0, 0], [1, 0], [1, 1], [0, 1]]; this.tri(a, b, c, u[0], u[1], u[2]); this.tri(a, c, d, u[0], u[2], u[3]); }
  fan(P, uvs) { for (let k = 1; k < P.length - 1; k++) this.tri(P[0], P[k], P[k + 1], uvs?.[0], uvs?.[k], uvs?.[k + 1]); }
  // 8 corners: bottom face a0..a3, top face b0..b3 (same winding) -> closed box-like solid
  hexa(a, b) {
    this.quad(a[3], a[2], a[1], a[0]); this.quad(b[0], b[1], b[2], b[3]);
    for (let i = 0; i < 4; i++) { const j = (i + 1) % 4; this.quad(a[i], a[j], b[j], b[i]); }
  }
  // sweep a closed 2D profile (in the frame e1, e2) from point A to point B; caps the ends
  sweep(profile, A, B, e1, e2, caps = true) {
    const at = (O, [p, q]) => [O[0] + e1[0] * p + e2[0] * q, O[1] + e1[1] * p + e2[1] * q, O[2] + e1[2] * p + e2[2] * q];
    const PA = profile.map(p => at(A, p)), PB = profile.map(p => at(B, p));
    const L = Math.hypot(B[0] - A[0], B[1] - A[1], B[2] - A[2]);
    let s = 0;
    for (let i = 0; i < profile.length; i++) {
      const j = (i + 1) % profile.length, d = Math.hypot(profile[j][0] - profile[i][0], profile[j][1] - profile[i][1]);
      this.quad(PA[i], PA[j], PB[j], PB[i], [[s, 0], [s + d, 0], [s + d, L], [s, L]]);
      s += d;
    }
    if (!caps) return;
    const tris = THREE.ShapeUtils.triangulateShape(profile.map(([p, q]) => new THREE.Vector2(p, q)), []);
    const ccw = THREE.ShapeUtils.isClockWise(profile.map(([p, q]) => new THREE.Vector2(p, q))) ? -1 : 1;
    // which way the sweep runs relative to e1 x e2 decides the cap windings
    const ax = [B[0] - A[0], B[1] - A[1], B[2] - A[2]], n = cross(e1, e2), fw = Math.sign(dot(ax, n)) * ccw;
    for (const [i, j, k] of tris) {
      if (fw > 0) { this.tri(PA[i], PA[k], PA[j], profile[i], profile[k], profile[j]); this.tri(PB[i], PB[j], PB[k], profile[i], profile[j], profile[k]); }
      else { this.tri(PA[i], PA[j], PA[k], profile[i], profile[j], profile[k]); this.tri(PB[i], PB[k], PB[j], profile[i], profile[k], profile[j]); }
    }
  }
  mesh(material) {
    if (!this.pos.length) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, material);
    m.castShadow = m.receiveShadow = true;
    return m;
  }
}
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const nrm = v => { const l = Math.hypot(...v) || 1; return v.map(x => x / l); };
const add = (a, b, k = 1) => [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k];

// ---------------------------------------------------------------------------------- roof definitions
function norm(r, plate) {
  const [x0, y0, x1, y1] = r.rect;
  const t = r.type === 'hip' ? TYPE.hip : r.type === 'shed' ? TYPE.shed : (r.ridge === 'y' ? TYPE.gableY : TYPE.gableX);
  return { ...r, x0: Math.min(x0, x1), y0: Math.min(y0, y1), x1: Math.max(x0, x1), y1: Math.max(y0, y1), t, o: r.overhang ?? 2, rk: r.rake ?? r.overhang ?? 2, h0: r.plate ?? plate, p: r.pitch };
}
// Footprint (outer outline) of a roof.
function outline(R) {
  const { x0, y0, x1, y1, o, rk, t } = R;
  if (t === TYPE.hip) return [x0 - o, y0 - o, x1 + o, y1 + o];
  if (t === TYPE.gableY) return [x0 - o, y0 - rk, x1 + o, y1 + rk];
  return [x0 - rk, y0 - o, x1 + rk, y1 + o];
}
// The ceiling plane rising in `dir` from the wall line it starts at: h = a x + b y + c.
function planeOf(R, dir) {
  const { h0, p } = R;
  if (dir[0] > 0) return [p, 0, h0 - p * R.x0];
  if (dir[0] < 0) return [-p, 0, h0 + p * R.x1];
  if (dir[1] > 0) return [0, p, h0 - p * R.y0];
  return [0, -p, h0 + p * R.y1];
}
const DIRS = { [TYPE.hip]: [[1, 0], [-1, 0], [0, 1], [0, -1]], [TYPE.gableX]: [[0, 1], [0, -1]], [TYPE.gableY]: [[1, 0], [-1, 0]], [TYPE.shed]: [[0, -1]] };
const planes = R => (R._planes ??= DIRS[R.t].map(d => planeOf(R, d)));
const evalP = ([a, b, c], x, y) => a * x + b * y + c;

// Ceiling height of one roof at (x, y), or null when the point is outside it.
function ceilingOf(R, x, y) {
  const [X0, Y0, X1, Y1] = outline(R);
  if (x < X0 || x > X1 || y < Y0 || y > Y1) return null;
  let h = Infinity;
  for (const P of planes(R)) h = Math.min(h, evalP(P, x, y));
  return h;
}

export class Roofs {
  constructor(plan) {
    this.plate = plan.plate ?? 10;
    this.grade = plan.grade ?? -0.6;
    this.list = [];
    for (const r of plan.roofs ?? []) {
      const R = norm(r, this.plate);
      R.idx = this.list.length; this.list.push(R);
      const ext = this.#gableRun(R, r);
      if (ext) {
        // Dutch hip: a gable riding the ridge, cut off by the gable walls at both ends
        const [X0, Y0, X1, Y1] = outline(R), alongX = X1 - X0 >= Y1 - Y0;
        const h = (alongX ? Y1 - Y0 : X1 - X0) / 2;
        const ra = (alongX ? X0 : Y0) + h, rb = (alongX ? X1 : Y1) - h;
        const ends = r.dutchEnds ?? 'both', lo = ends === 'both' || ends === 'lo' ? ext : 0, hi = ends === 'both' || ends === 'hi' ? ext : 0;
        const C = alongX
          ? norm({ type: 'gable', ridge: 'x', rect: [ra - lo, R.y0, rb + hi, R.y1], pitch: R.p, overhang: R.o, rake: 0, plate: R.h0 }, this.plate)
          : norm({ type: 'gable', ridge: 'y', rect: [R.x0, ra - lo, R.x1, rb + hi], pitch: R.p, overhang: R.o, rake: 0, plate: R.h0 }, this.plate);
        C.companion = true; C.parent = R; R.child = C; C.alongX = alongX; C.ends = [lo > 0, hi > 0];
        C.idx = this.list.length; this.list.push(C);
      }
    }
    this.#faceCache = new Map();
  }
  #faceCache;

  // How far a Dutch hip's gable runs past the hip ridge ends (ft), from `dutch` (skirt run) or `gablet`.
  #gableRun(R, r) {
    if (R.t !== TYPE.hip) return 0;
    const [X0, Y0, X1, Y1] = outline(R), h = Math.min(X1 - X0, Y1 - Y0) / 2;
    if (r.dutch != null) return Math.max(0, h - r.dutch);
    return r.gablet ?? 0;
  }

  // Interior ceiling height: highest roof over the point; the plate height if none.
  ceilingAt(x, y, fallback = this.plate) {
    let best = null;
    for (const R of this.list) { if (R.companion) continue; const c = ceilingOf(R, x, y); if (c !== null && (best === null || c > best)) best = c; }
    return best ?? fallback;
  }
  covered(x, y) { return this.list.some(R => ceilingOf(R, x, y) !== null); }
  // Top of the metal over a point (union of all roofs), or null.
  topAt(x, y) {
    let best = null;
    for (const R of this.list) { const c = ceilingOf(R, x, y); if (c !== null && (best === null || c > best)) best = c; }
    return best === null ? null : best + ROOF_T;
  }

  // ------------------------------------------------------------------------------ faces and visibility
  // Plane polygons of a roof, each with its up-slope direction and ceiling plane.
  #faces(R) {
    if (R._faces) return R._faces;
    const [X0, Y0, X1, Y1] = outline(R), { t } = R;
    let F;
    if (t === TYPE.hip) {
      const W = X1 - X0, D = Y1 - Y0;
      if (W >= D) {
        const h = D / 2, yc = (Y0 + Y1) / 2, ra = X0 + h, rb = X1 - h;
        F = [
          { pts: [[X0, Y0], [X1, Y0], [rb, yc], [ra, yc]], dir: [0, 1] },
          { pts: [[X1, Y1], [X0, Y1], [ra, yc], [rb, yc]], dir: [0, -1] },
          { pts: [[X0, Y1], [X0, Y0], [ra, yc]], dir: [1, 0] },
          { pts: [[X1, Y0], [X1, Y1], [rb, yc]], dir: [-1, 0] },
        ];
        R._lines = [{ a: [ra, yc], b: [rb, yc], f: [0, 1] }, { a: [X0, Y0], b: [ra, yc], f: [0, 2] }, { a: [X0, Y1], b: [ra, yc], f: [1, 2] },
          { a: [X1, Y0], b: [rb, yc], f: [0, 3] }, { a: [X1, Y1], b: [rb, yc], f: [1, 3] }];
      } else {
        const h = W / 2, xc = (X0 + X1) / 2, ra = Y0 + h, rb = Y1 - h;
        F = [
          { pts: [[X0, Y1], [X0, Y0], [xc, ra], [xc, rb]], dir: [1, 0] },
          { pts: [[X1, Y0], [X1, Y1], [xc, rb], [xc, ra]], dir: [-1, 0] },
          { pts: [[X0, Y0], [X1, Y0], [xc, ra]], dir: [0, 1] },
          { pts: [[X1, Y1], [X0, Y1], [xc, rb]], dir: [0, -1] },
        ];
        R._lines = [{ a: [xc, ra], b: [xc, rb], f: [0, 1] }, { a: [X0, Y0], b: [xc, ra], f: [0, 2] }, { a: [X1, Y0], b: [xc, ra], f: [1, 2] },
          { a: [X0, Y1], b: [xc, rb], f: [0, 3] }, { a: [X1, Y1], b: [xc, rb], f: [1, 3] }];
      }
    } else if (t === TYPE.gableX) {
      const yc = (R.y0 + R.y1) / 2;
      F = [{ pts: [[X0, Y0], [X1, Y0], [X1, yc], [X0, yc]], dir: [0, 1] }, { pts: [[X1, Y1], [X0, Y1], [X0, yc], [X1, yc]], dir: [0, -1] }];
      R._lines = [{ a: [X0, yc], b: [X1, yc], f: [0, 1] }];
    } else if (t === TYPE.gableY) {
      const xc = (R.x0 + R.x1) / 2;
      F = [{ pts: [[X0, Y1], [X0, Y0], [xc, Y0], [xc, Y1]], dir: [1, 0] }, { pts: [[X1, Y0], [X1, Y1], [xc, Y1], [xc, Y0]], dir: [-1, 0] }];
      R._lines = [{ a: [xc, Y0], b: [xc, Y1], f: [0, 1] }];
    } else {
      F = [{ pts: [[X0, Y1], [X1, Y1], [X1, Y0], [X0, Y0]], dir: [0, -1] }];
      R._lines = [];
    }
    F = F.filter(f => Math.abs(area(f.pts)) > 1e-6);
    for (const f of F) f.L = planeOf(R, f.dir);
    R._faces = F;
    return F;
  }

  // The part of face f of roof R that is the union's surface. kind 'top': the metal; 'under': the ceiling.
  #visible(R, fi, kind) {
    const key = `${R.idx}:${fi}:${kind}`;
    if (this.#faceCache.has(key)) return this.#faceCache.get(key);
    const f = this.#faces(R)[fi];
    let pieces = [f.pts];
    for (const S of this.list) {
      if (S === R || !pieces.length) continue;
      if (kind === 'under' && S.companion) continue;
      let m;
      if (R.companion && S === R.parent) m = EPS;                               // the gable only exists above its hip
      else if (S.companion && S.parent === R) m = -EPS;                        // the hip under its own gable
      else m = S.idx < R.idx ? EPS : -EPS;                                     // ties go to the earlier roof
      const H = rectHalf(outline(S));
      let empty = false;
      for (const [a, b, c] of planes(S)) {
        const ha = a - f.L[0], hb = b - f.L[1], hc = c - f.L[2] + m;           // hidden where f is below S
        if (Math.abs(ha) < 1e-9 && Math.abs(hb) < 1e-9) { if (hc > 0) continue; empty = true; break; }
        H.push([ha, hb, hc]);
      }
      if (!empty) pieces = subtract(pieces, H);
    }
    for (const h of (R.companion ? R.parent.holes : R.holes) ?? []) pieces = subtract(pieces, rectHalf(h));   // a well can sit in the gable's zone
    this.#faceCache.set(key, pieces);
    return pieces;
  }
  #shows(R, fi, x, y) { return this.#visible(R, fi, 'top').some(P => inConvex(P, x, y)); }

  build() {
    const group = new THREE.Group();
    this.list.forEach(R => group.add(this.#buildOne(R)));
    const ds = this.#downspouts();
    if (ds) group.add(ds);
    group.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    return group;
  }

  #buildOne(R) {
    const g = new THREE.Group();
    g.name = `roof ${R.id ?? R.idx}${R.companion ? ' gable' : ''}`;
    const top = new Acc(), under = new Acc(), ribs = new Acc(), caps = new Acc();
    const faces = this.#faces(R), T = ROOF_T, k = Math.hypot(1, R.p);
    faces.forEach((f, fi) => {
      const ux = -f.dir[1], uy = f.dir[0];
      const uvOf = (x, y) => [x * ux + y * uy, (x * f.dir[0] + y * f.dir[1]) * k];
      for (const P of this.#visible(R, fi, 'top')) {
        top.fan(P.map(([x, y]) => [x, evalP(f.L, x, y) + T, y]), P.map(([x, y]) => uvOf(x, y)));
      }
      if (!R.companion) for (const P of this.#visible(R, fi, 'under')) {
        const Q = [...P].reverse();
        under.fan(Q.map(([x, y]) => [x, evalP(f.L, x, y), y]), Q.map(([x, y]) => uvOf(x, y)));
      }
      this.#seams(ribs, R, f, fi);
    });
    for (const [acc, m] of [[top, mat('roof')], [under, mat('soffit')], [ribs, SEAM_M()]]) { const me = acc.mesh(m); if (me) g.add(me); }
    this.#caps(caps, R);
    const cm = caps.mesh(SEAM_M()); if (cm) g.add(cm);
    if (!R.companion) this.#edges(g, R);
    else this.#gableEnds(g, R);
    // the well is built by whichever roof carries the metal over its centre (the hip, or its Dutch gable)
    if (!R.companion) for (const h of R.holes ?? []) {
      const cx = (h[0] + h[2]) / 2, cy = (h[1] + h[3]) / 2, C = R.child;
      const own = C && (ceilingOf(C, cx, cy) ?? -1e9) > (ceilingOf(R, cx, cy) ?? -1e9) + EPS ? C : R;
      this.#opening(g, own, h);
    }
    return g;
  }

  // ------------------------------------------------------------------------------ standing seams
  #seams(acc, R, f, fi) {
    const ux = -f.dir[1], uy = f.dir[0], dx = f.dir[0], dy = f.dir[1];
    const [a, b, c] = f.L, T = ROOF_T;
    const n3 = nrm([-a, 1, -b]), u3 = [ux, 0, uy];
    const byK = new Map();
    for (const P of this.#visible(R, fi, 'top')) {
      const ts = P.map(([x, y]) => x * ux + y * uy);
      const k0 = Math.ceil(Math.min(...ts) / SEAM + 1e-6), k1 = Math.floor(Math.max(...ts) / SEAM - 1e-6);
      for (let k = k0; k <= k1; k++) {
        const t = k * SEAM;
        // clip the seam line {x ux + y uy = t} to the piece: param s = x dx + y dy
        let lo = Infinity, hi = -Infinity;
        for (let i = 0; i < P.length; i++) {
          const A = P[i], B = P[(i + 1) % P.length], ta = A[0] * ux + A[1] * uy, tb = B[0] * ux + B[1] * uy;
          if ((ta - t) * (tb - t) > 0 || ta === tb) continue;
          const w = (t - ta) / (tb - ta), s = (A[0] + (B[0] - A[0]) * w) * dx + (A[1] + (B[1] - A[1]) * w) * dy;
          lo = Math.min(lo, s); hi = Math.max(hi, s);
        }
        if (hi - lo < 0.05) continue;
        if (!byK.has(k)) byK.set(k, []);
        byK.get(k).push([lo, hi]);
      }
    }
    const prof = [[-0.045, -0.01], [0.045, -0.01], [0.03, 0.085], [0.016, 0.11], [-0.016, 0.11], [-0.03, 0.085]];
    for (const [k, ivs] of byK) {
      ivs.sort((p, q) => p[0] - q[0]);
      const merged = [];
      for (const iv of ivs) { const l = merged[merged.length - 1]; if (l && iv[0] <= l[1] + 0.01) l[1] = Math.max(l[1], iv[1]); else merged.push([...iv]); }
      const t = k * SEAM;
      for (const [s0, s1] of merged) {
        const P = s => { const x = t * ux + s * dx, y = t * uy + s * dy; return [x, a * x + b * y + c + T, y]; };
        acc.sweep(prof, P(s0), P(s1), u3, n3);
      }
    }
  }

  // ------------------------------------------------------------------------------ hip and ridge caps
  #caps(acc, R) {
    const faces = this.#faces(R), T = ROOF_T;
    for (const { a, b, f: [i, j] } of R._lines) {
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (L < 0.2) continue;
      const lx = (b[0] - a[0]) / L, ly = (b[1] - a[1]) / L;
      // horizontal offsets into each face (perpendicular to the line, toward the face's centroid)
      const into = fi => {
        const P = faces[fi].pts, cx = P.reduce((s, p) => s + p[0], 0) / P.length, cy = P.reduce((s, p) => s + p[1], 0) / P.length;
        let ox = -ly, oy = lx; if ((cx - a[0]) * ox + (cy - a[1]) * oy < 0) { ox = -ox; oy = -oy; }
        return [ox, oy];
      };
      const oi = into(i), oj = into(j);
      const at = t => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
      const test = t => { const [x, y] = at(t); return this.#shows(R, i, x + oi[0] * 0.06, y + oi[1] * 0.06) && this.#shows(R, j, x + oj[0] * 0.06, y + oj[1] * 0.06); };
      for (const [t0, t1] of runs(L, test)) {
        const A2 = at(t0), B2 = at(t1), Li = faces[i].L, Lj = faces[j].L;
        const A = [A2[0], evalP(Li, ...A2) + T, A2[1]], B = [B2[0], evalP(Li, ...B2) + T, B2[1]];
        const ax = nrm([B[0] - A[0], B[1] - A[1], B[2] - A[2]]);
        // in-plane directions away from the line on each face, and the face normals
        const inPlane = (o, Lf) => nrm(cross(ax, cross([o[0], Lf[0] * o[0] + Lf[1] * o[1], o[1]], ax)));
        const ei = inPlane(oi, Li), ej = inPlane(oj, Lj);
        const ni = nrm([-Li[0], 1, -Li[1]]), nj = nrm([-Lj[0], 1, -Lj[1]]);
        const up = nrm(add(ni, nj));
        // formed cap: flanges 4" over each plane, a rounded roll on the line
        const pt = (e, n, w, h) => add(add([0, 0, 0], e, w), n, h);
        const ring = [pt(ei, ni, 0.36, 0.0), pt(ei, ni, 0.3, 0.035), pt(ei, ni, 0.12, 0.05), add(pt(ei, ni, 0.05, 0.05), up, 0.07), add([0, 0, 0], up, 0.15),
          add(pt(ej, nj, 0.05, 0.05), up, 0.07), pt(ej, nj, 0.12, 0.05), pt(ej, nj, 0.3, 0.035), pt(ej, nj, 0.36, 0.0), pt(ej, nj, 0.33, -0.01), add([0, 0, 0], up, 0.02), pt(ei, ni, 0.33, -0.01)];
        // express the ring in a 2D frame (s1, s2) perpendicular to the line so sweep() can cap it
        const s1 = nrm(cross(up, ax)), s2 = up;
        acc.sweep(ring.map(p => [dot(p, s1), dot(p, s2)]), A, B, s1, s2);
      }
    }
  }

  // ------------------------------------------------------------------------------ fascia, gutters
  #edges(g, R) {
    const faces = this.#faces(R), T = ROOF_T, [X0, Y0, X1, Y1] = outline(R);
    const fascia = new Acc(), gutters = new Acc();
    const onSide = (p, q) => (Math.abs(p[0] - X0) < 1e-6 && Math.abs(q[0] - X0) < 1e-6) || (Math.abs(p[0] - X1) < 1e-6 && Math.abs(q[0] - X1) < 1e-6) ||
      (Math.abs(p[1] - Y0) < 1e-6 && Math.abs(q[1] - Y0) < 1e-6) || (Math.abs(p[1] - Y1) < 1e-6 && Math.abs(q[1] - Y1) < 1e-6);
    faces.forEach((f, fi) => {
      for (let i = 0; i < f.pts.length; i++) {
        const A = f.pts[i], B = f.pts[(i + 1) % f.pts.length];
        if (!onSide(A, B)) continue;
        const L = Math.hypot(B[0] - A[0], B[1] - A[1]), ex = (B[0] - A[0]) / L, ey = (B[1] - A[1]) / L;
        // outward normal: away from the roof's centre
        let nx = ey, ny = -ex; const cx = (X0 + X1) / 2, cy = (Y0 + Y1) / 2;
        if ((A[0] - cx) * nx + (A[1] - cy) * ny < 0) { nx = -nx; ny = -ny; }
        const h = (x, y) => evalP(f.L, x, y);
        const eave = Math.abs(h(...A) - h(...B)) < 1e-6;
        // the edge shows where its face does, and nothing carries the roof on past it (an adjoining roof
        // continuing the same plane, or rising over the edge)
        const test = t => {
          const x = A[0] + (B[0] - A[0]) * t, y = A[1] + (B[1] - A[1]) * t;
          if (!this.#shows(R, fi, x - nx * 0.04, y - ny * 0.04)) return false;
          const top = h(x, y) + T;
          for (const S of this.list) {
            if (S === R || S.parent === R || R.parent === S) continue;
            const c = ceilingOf(S, x + nx * 0.1, y + ny * 0.1);
            if (c !== null && c + T > top - 0.15) return false;
          }
          return true;
        };
        for (const [t0, t1] of runs(L, test)) {
          // full corners get mitred overlaps; cut ends stop flush
          const e0 = t0 < 1e-6 ? 0.5 : 0, e1 = t1 > 1 - 1e-6 ? 0.5 : 0;
          const P0 = [A[0] + (B[0] - A[0]) * t0 - ex * e0 * 0.14, A[1] + (B[1] - A[1]) * t0 - ey * e0 * 0.14];
          const P1 = [A[0] + (B[0] - A[0]) * t1 + ex * e1 * 0.14, A[1] + (B[1] - A[1]) * t1 + ey * e1 * 0.14];
          const PA = [P0[0], h(...P0), P0[1]], PB = [P1[0], h(...P1), P1[1]];
          const n3 = [nx, 0, ny];
          // 1x8 metal-clad fascia board: from just under the soffit to the drip edge
          fascia.sweep([[0, -0.04], [0.07, -0.04], [0.07, T + 0.04], [0.035, T + 0.07], [0, T + 0.05]], PA, PB, n3, [0, 1, 0]);
          if (eave) {
            const G0 = [P0[0] - ex * e0 * 0.36, P0[1] - ey * e0 * 0.36], G1 = [P1[0] + ex * e1 * 0.36, P1[1] + ey * e1 * 0.36];
            const hy = h(...A) + T - 0.03;
            // 5" K-style gutter: flat back on the fascia, ogee front, rolled bead, dark inside
            const K = [[0, 0], [0, -0.36], [0.26, -0.36], [0.3, -0.345], [0.325, -0.3], [0.34, -0.25], [0.37, -0.225], [0.395, -0.19], [0.405, -0.14],
              [0.405, -0.03], [0.43, -0.005], [0.43, 0.015], [0.395, 0.015], [0.375, -0.05], [0.03, -0.05], [0.015, 0.0]];
            gutters.sweep(K.map(([p, q]) => [p + 0.07, q]), [G0[0], hy, G0[1]], [G1[0], hy, G1[1]], n3, [0, 1, 0]);
          }
        }
      }
    });
    const fm = fascia.mesh(mat('fascia')); if (fm) g.add(fm);
    const gm = gutters.mesh(GUTTER_M()); if (gm) g.add(gm);
  }

  // ------------------------------------------------------------------------------ Dutch gable walls
  #gableEnds(g, C) {
    const P = C.parent, p = C.p, T = ROOF_T;
    const trim = new Acc(), blades = new Acc(), frame = new Acc(), cavity = new Acc();
    const vm = C.alongX ? (C.y0 + C.y1) / 2 : (C.x0 + C.x1) / 2;
    const apexC = C.h0 + p * (C.alongX ? C.y1 - C.y0 : C.x1 - C.x0) / 2;
    [[C.alongX ? C.x0 : C.y0, -1, C.ends[0]], [C.alongX ? C.x1 : C.y1, 1, C.ends[1]]].forEach(([e, n, on]) => {
      if (!on) return;
      // world point from gable-plane coordinates: v across, y height, d outward from the plane
      const W = (v, y, d) => C.alongX ? [e + n * d, y, v] : [v, y, e + n * d];
      const plan = (v, d) => C.alongX ? [e + n * d, v] : [v, e + n * d];
      const b = ceilingOf(P, ...plan(vm, -0.01));
      if (b === null) return;
      const gh = (apexC - b) / p;
      if (gh < 0.6) return;
      // buried in another roof (a wing's inner end): no vent
      const buried = (v, y, d) => this.list.some(S => S !== C && S !== P && !S.companion && (ceilingOf(S, ...plan(v, d)) ?? -1e9) + T > y);
      if (buried(vm, apexC + T - 0.2, 0.2) || buried(vm, b + T + 0.3, 0.3)) return;
      const Ht = v => apexC + T - p * Math.abs(v - vm);          // metal top at the gable plane
      // No two trim solids may share a face plane where they overlap: coincident faces shadow each other in
      // Cycles and render pure black (the notches that showed at both ends of every gablet base).
      // rake boards (metal-clad, roof colour) covering the gable roof's cut edge; they butt at the apex and
      // land, 1" back, on the base ledge
      for (const s of [-1, 1]) {
        const v0 = vm + s * gh, v1 = vm;
        const bot = v => Ht(v) - T - 0.09, tp = v => Ht(v) + 0.05;
        trim.hexa([W(v0, bot(v0), -0.01), W(v1, bot(v1), -0.01), W(v1, bot(v1), 0.07), W(v0, bot(v0), 0.07)],
          [W(v0, tp(v0), -0.01), W(v1, tp(v1), -0.01), W(v1, tp(v1), 0.07), W(v0, tp(v0), 0.07)]);
      }
      // base ledge: a flashing-capped board along the skirt, proud of the rake boards and 2" past the hip
      // lines so it closes the corners where the rakes come down onto the hip planes; its foot sits in the metal
      const yb = b + T, base = yb + 0.28, L0 = vm - gh - 0.17, L1 = vm + gh + 0.17;
      trim.hexa([W(L0, yb - 0.13, -0.02), W(L1, yb - 0.13, -0.02), W(L1, yb - 0.13, 0.1), W(L0, yb - 0.13, 0.1)],
        [W(L0, base, -0.02), W(L1, base, -0.02), W(L1, base, 0.1), W(L0, base, 0.1)]);
      // flashing cap over the ledge, sloped out to shed water: 1/2" drip past the face
      trim.hexa([W(L0 - 0.02, base, -0.02), W(L1 + 0.02, base, -0.02), W(L1 + 0.02, base - 0.03, 0.14), W(L0 - 0.02, base - 0.03, 0.14)],
        [W(L0 - 0.02, base + 0.035, -0.02), W(L1 + 0.02, base + 0.035, -0.02), W(L1 + 0.02, base + 0.005, 0.14), W(L0 - 0.02, base + 0.005, 0.14)]);
      // the opening: from the base trim up to the rake boards' underside, the vent set 3" back
      const ya = apexC - 0.09, wv = y => Math.max(0, (ya - y) / p);
      if (ya - base < 0.4) return;
      const D0 = -0.02, D1 = -0.42, DJ = -0.01;   // jambs start at the rake boards' back face, the sill at the ledge's
      // frame returns (jambs) along the rakes and the sill
      for (const s of [-1, 1]) {
        const q0 = [vm + s * wv(base), base], q1 = [vm, ya];
        // one face each, facing down into the opening (see quadToward)
        const Wd = (dv, dy, dd) => C.alongX ? [n * dd, dy, dv] : [dv, dy, n * dd];
        quadToward(frame, W(q0[0], q0[1], DJ), W(q1[0], q1[1], DJ), W(q1[0], q1[1], D1), W(q0[0], q0[1], D1), Wd(-s * p, -1, 0));
      }
      quadToward(frame, W(vm - wv(base), base, D0), W(vm + wv(base), base, D0), W(vm + wv(base), base, D1), W(vm - wv(base), base, D1), [0, 1, 0]);
      const A0 = W(vm - wv(base) - 0.1, base - 0.05, D1 - 0.05), A1 = W(vm + wv(base) + 0.1, base - 0.05, D1 - 0.05), A2 = W(vm, ya + 0.1, D1 - 0.05);
      if (dot(cross([A1[0] - A0[0], A1[1] - A0[1], A1[2] - A0[2]], [A2[0] - A0[0], A2[1] - A0[1], A2[2] - A0[2]]), C.alongX ? [n, 0, 0] : [0, 0, n]) >= 0) cavity.tri(A0, A1, A2);
      else cavity.tri(A0, A2, A1);
      // fixed louver blades, 2" on centre, 2 1/2" deep, tipped 40 deg so rain runs out
      const pitch = 0.165, dep = 0.21, th = 0.03, ang = 40 * Math.PI / 180;
      const cy = Math.cos(ang), sy = Math.sin(ang);
      for (let y = base + 0.1; y < ya - 0.06; y += pitch) {
        const w = wv(y + dep * sy / 2) + 0.03;
        if (w < 0.1) break;
        const dc = -0.2;
        // blade section: depth along d tipped down toward the outside, thickness across it
        const sec = [[-dep / 2, -th / 2], [dep / 2, -th / 2], [dep / 2, th / 2], [-dep / 2, th / 2]].map(([q, r]) => [dc + q * cy - r * sy, y - q * sy - r * cy]);
        const A = sec.map(([d, yy]) => W(vm - w, yy, d)), B = sec.map(([d, yy]) => W(vm + w, yy, d));
        blades.hexa(A, B);
      }
      // vertical stiles every ~20"
      for (let v = 0; v < gh; v += 1.65) for (const s of v ? [-1, 1] : [1]) {
        const vv = vm + s * v, top = ya - p * v - 0.02;
        if (top - base < 0.25) continue;
        blades.hexa([W(vv - 0.04, base, -0.08), W(vv + 0.04, base, -0.08), W(vv + 0.04, base, -0.36), W(vv - 0.04, base, -0.36)],
          [W(vv - 0.04, top, -0.08), W(vv + 0.04, top, -0.08), W(vv + 0.04, top, -0.36), W(vv - 0.04, top, -0.36)]);
      }
    });
    for (const [acc, m] of [[trim, mat('fascia')], [frame, mat('fascia')], [blades, LOUVER_M()], [cavity, CAVITY_M()]]) { const me = acc.mesh(m); if (me) g.add(me); }
  }

  // ------------------------------------------------------------------------------ roof openings
  // A rectangle cut through the roof (over a garden shower): cedar-lined well, metal curb, and a slatted
  // cedar hatch of 2x6s on edge running down the slope (rain and leaves run off between them), 4" on
  // centre, their tops level with the curb and their ends bearing on it, so the opening reads from the
  // street as a deliberate cedar grille. The lining is one face, wound into the well: a second coincident
  // face behind it shadowed it black in Cycles.
  #opening(g, R, h) {
    const [x0, y0, x1, y1] = h, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, T = ROOF_T;
    const faces = this.#faces(R), f = faces.find(f => inConvex(f.pts, cx, cy));
    if (!f) return;
    const H = (x, y) => evalP(f.L, x, y), well = new Acc(), slats = new Acc(), curb = new Acc();
    const C = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
    // the lining runs from the ceiling below (the hip's, which can drop under a Dutch gable) up to the metal
    const Hip = R.companion ? R.parent : R, low = (x, y) => Math.min(H(x, y), ceilingOf(Hip, x, y) ?? H(x, y)) - 0.02;
    for (let i = 0; i < 4; i++) {
      const A = C[i], B = C[(i + 1) % 4];
      for (let j = 0; j < 8; j++) {
        const t0 = j / 8, t1 = (j + 1) / 8, P0 = [A[0] + (B[0] - A[0]) * t0, A[1] + (B[1] - A[1]) * t0], P1 = [A[0] + (B[0] - A[0]) * t1, A[1] + (B[1] - A[1]) * t1];
        quadToward(well, [P0[0], low(...P0), P0[1]], [P1[0], low(...P1), P1[1]], [P1[0], H(...P1) + T + 0.01, P1[1]], [P0[0], H(...P0) + T + 0.01, P0[1]],
          [cx - (P0[0] + P1[0]) / 2, 0, cy - (P0[1] + P1[1]) / 2]);
      }
      // curb: a 2" turned-up metal lip around the cut
      const L = Math.hypot(B[0] - A[0], B[1] - A[1]), ex = (B[0] - A[0]) / L, ey = (B[1] - A[1]) / L;
      const A3 = [A[0] - ex * 0.08, H(...A) + T, A[1] - ey * 0.08], B3 = [B[0] + ex * 0.08, H(...B) + T, B[1] + ey * 0.08];
      let ox = ey, oy = -ex; if ((A[0] - cx) * ox + (A[1] - cy) * oy < 0) { ox = -ox; oy = -oy; }
      curb.sweep([[0, -0.02], [0.08, -0.02], [0.08, 0.16], [0, 0.16]], A3, B3, [ox, 0, oy], [0, 1, 0]);
    }
    const ux = -f.dir[1], uy = f.dir[0], dx = f.dir[0], dy = f.dir[1];
    const ts = C.map(([x, y]) => x * ux + y * uy), ss = C.map(([x, y]) => x * dx + y * dy);
    const t0 = Math.min(...ts), t1 = Math.max(...ts), s0 = Math.min(...ss), s1 = Math.max(...ss);
    const n3 = nrm([-f.L[0], 1, -f.L[1]]), u3 = [ux, 0, uy];
    const nb = Math.max(2, Math.round((t1 - t0) / 0.333)), bay = (t1 - t0) / nb;
    for (let k = 0; k < nb; k++) {
      const t = t0 + (k + 0.5) * bay;
      // runs 2" past each edge onto the curb (ends never lie in the lining's plane)
      const P = s => { const x = t * ux + s * dx, y = t * uy + s * dy; return [x, H(x, y) + T + 0.16, y]; };
      slats.sweep([[-0.0625, 0], [0.0625, 0], [0.0625, -0.46], [-0.0625, -0.46]], P(s0 - 0.07), P(s1 + 0.07), u3, n3);
    }
    for (const [acc, m] of [[well, mat('woodBeam')], [slats, mat('woodBeam')], [curb, FLASH_M()]]) { const me = acc.mesh(m); if (me) g.add(me); }
  }

  // ------------------------------------------------------------------------------ downspouts
  // roof.downspouts: [[x, y]] building corners; the pipe drops from the gutter on the nearer eave,
  // goosenecks back to the wall and runs down beside the corner board to a kick-out at grade.
  #downspouts() {
    const acc = [];
    for (const R of this.list) for (const [cx0, cy0, along] of R.downspouts ?? []) {
      // snap to the roof's wall-line corner (the plan's corner can be off by a rounding)
      const cxp = Math.abs(cx0 - R.x0) < Math.abs(cx0 - R.x1) ? R.x0 : R.x1, cyp = Math.abs(cy0 - R.y0) < Math.abs(cy0 - R.y1) ? R.y0 : R.y1;
      // which eave: the wall the pipe runs down is the one the corner shares with `along` ('x' or 'y')
      const [X0, Y0, X1, Y1] = outline(R);
      const ny = Math.abs(cyp - R.y0) < Math.abs(cyp - R.y1) ? -1 : 1, nx = Math.abs(cxp - R.x0) < Math.abs(cxp - R.x1) ? -1 : 1;
      // the pipe sits on the wall facing n, 7" in from the corner along the wall
      const onX = along === 'x';
      const n = onX ? [0, ny] : [nx, 0], w = onX ? [-nx, 0] : [0, -ny];
      const wallOff = 0.25 + 0.17, gutOff = R.o + 0.07 + 0.22;
      const base = [cxp + w[0] * 0.6, cyp + w[1] * 0.6];
      const eaveC = ceilingOf(R, base[0] + n[0] * (R.o - 0.01), base[1] + n[1] * (R.o - 0.01));
      if (eaveC === null) continue;
      const yTop = eaveC + ROOF_T - 0.03 - 0.36, yGrade = this.grade;
      const pt = (off, y) => new THREE.Vector3(base[0] + n[0] * off, y, base[1] + n[1] * off);
      const path = new THREE.CurvePath();
      const p0 = pt(gutOff, yTop + 0.05), p1 = pt(gutOff, yTop - 0.3), p2 = pt(wallOff, yTop - 0.3 - (gutOff - wallOff)), p3 = pt(wallOff, yGrade + 0.55), p4 = pt(wallOff + 0.55, yGrade + 0.12);
      const bend = (a, b, c) => path.add(new THREE.QuadraticBezierCurve3(a, b, c));
      const lerp = (a, b, t) => a.clone().lerp(b, t);
      path.add(new THREE.LineCurve3(p0, lerp(p0, p1, 0.6)));
      bend(lerp(p0, p1, 0.6), p1, lerp(p1, p2, 0.25));
      path.add(new THREE.LineCurve3(lerp(p1, p2, 0.25), lerp(p1, p2, 0.75)));
      bend(lerp(p1, p2, 0.75), p2, lerp(p2, p3, 0.04));
      path.add(new THREE.LineCurve3(lerp(p2, p3, 0.04), lerp(p2, p3, 0.96)));
      bend(lerp(p2, p3, 0.96), p3, lerp(p3, p4, 0.5));
      path.add(new THREE.LineCurve3(lerp(p3, p4, 0.5), p4));
      const tube = new THREE.TubeGeometry(path, 120, 0.125, 14, false);
      acc.push(tube);
      // straps holding it to the wall, every ~5 ft
      for (let y = p3.y + 1.0; y < p2.y - 0.5; y += 5) {
        const s = new THREE.BoxGeometry(onX ? 0.3 : 0.06, 0.1, onX ? 0.06 : 0.3);
        s.translate(...pt(wallOff - 0.12, y).toArray());
        acc.push(s);
      }
    }
    if (!acc.length) return null;
    const g = new THREE.Group();
    for (const geo of acc) { const m = new THREE.Mesh(geo, GUTTER_M()); m.castShadow = m.receiveShadow = true; g.add(m); }
    return g;
  }
}
