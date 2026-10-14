// Roofs. Each roof is a simple solid (hip, gable or shed) over a rectangle of wall lines.
// Where roofs overlap, the house is their union: the visible surface is the highest one.
// Overlapping parts are hidden per-pixel by a shader test against every other roof,
// which is what lets wings run into the main hip and form real valleys.
import * as THREE from 'three';
import { mat } from './materials.js';

export const ROOF_T = 0.6; // ceiling plane to metal surface, ft
const CELL = 0.4;         // grid used to cut hidden roof parts out of the geometry
const TYPE = { hip: 0, gableX: 1, gableY: 2, shed: 3 };

function norm(r) {
  const [x0, y0, x1, y1] = r.rect;
  const type = r.type === 'hip' ? TYPE.hip : r.type === 'shed' ? TYPE.shed : (r.ridge === 'y' ? TYPE.gableY : TYPE.gableX);
  return { ...r, x0: Math.min(x0, x1), y0: Math.min(y0, y1), x1: Math.max(x0, x1), y1: Math.max(y0, y1), t: type, o: r.overhang ?? 2, rk: r.rake ?? r.overhang ?? 2 };
}

// Ceiling height of one roof at (x, y), or null when the point is outside it.
function ceilingOf(R, plate, x, y) {
  const { x0, y0, x1, y1, o, rk, t } = R, p = R.pitch, h0 = R.plate ?? plate;
  if (t === TYPE.hip) {
    if (x < x0 - o || x > x1 + o || y < y0 - o || y > y1 + o) return null;
    return h0 + p * Math.min(x - x0, x1 - x, y - y0, y1 - y);
  }
  if (t === TYPE.gableX) {
    if (x < x0 - rk || x > x1 + rk || y < y0 - o || y > y1 + o) return null;
    return h0 + p * Math.min(y - y0, y1 - y);
  }
  if (t === TYPE.gableY) {
    if (y < y0 - rk || y > y1 + rk || x < x0 - o || x > x1 + o) return null;
    return h0 + p * Math.min(x - x0, x1 - x);
  }
  if (x < x0 - rk || x > x1 + rk || y < y0 - o || y > y1 + o) return null;
  return h0 + p * (y1 - y);
}

// Cut a convex polygon into CELL-sized pieces (each still convex).
function gridClip(poly) {
  const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]);
  const x0 = Math.floor(Math.min(...xs) / CELL) * CELL, x1 = Math.max(...xs), y0 = Math.floor(Math.min(...ys) / CELL) * CELL, y1 = Math.max(...ys);
  const out = [];
  for (let x = x0; x < x1; x += CELL) for (let y = y0; y < y1; y += CELL) {
    let p = poly;
    for (const [nx, ny, c] of [[1, 0, x], [-1, 0, -(x + CELL)], [0, 1, y], [0, -1, -(y + CELL)]]) {
      const q = [];
      for (let i = 0; i < p.length; i++) {
        const A = p[i], B = p[(i + 1) % p.length], da = A[0] * nx + A[1] * ny - c, db = B[0] * nx + B[1] * ny - c;
        if (da >= 0) q.push(A);
        if ((da >= 0) !== (db >= 0)) { const t = da / (da - db); q.push([A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t]); }
      }
      p = q; if (p.length < 3) break;
    }
    if (p.length >= 3) out.push(p);
  }
  return out;
}

export class Roofs {
  constructor(plan) {
    this.plate = plan.plate ?? 10;
    this.list = [];
    for (const r of plan.roofs ?? []) {
      const R = norm(r);
      this.list.push(R);
      if (R.t === TYPE.hip && R.gablet) {
        // Dutch hip: a short gable riding the ridge; its cut ends are the louvered gablets.
        const X0 = R.x0 - R.o, X1 = R.x1 + R.o, Y0 = R.y0 - R.o, Y1 = R.y1 + R.o, e = R.gablet;
        const alongX = X1 - X0 >= Y1 - Y0;
        const h = (alongX ? Y1 - Y0 : X1 - X0) / 2;
        const ra = (alongX ? X0 : Y0) + h, rb = (alongX ? X1 : Y1) - h;
        const C = alongX
          ? norm({ type: 'gable', ridge: 'x', rect: [ra - e, R.y0, rb + e, R.y1], pitch: R.pitch, overhang: R.o, rake: 0, plate: R.plate })
          : norm({ type: 'gable', ridge: 'y', rect: [R.x0, ra - e, R.x1, rb + e], pitch: R.pitch, overhang: R.o, rake: 0, plate: R.plate });
        C.companion = true; C.lift = 0.02; C.parent = R;
        this.list.push(C);
      }
    }
  }

  // Interior ceiling height: highest roof over the point; the plate height if none.
  ceilingAt(x, y, fallback = this.plate) {
    let best = null;
    for (const R of this.list) { if (R.companion) continue; const c = ceilingOf(R, this.plate, x, y); if (c !== null && (best === null || c > best)) best = c; }
    return best ?? fallback;
  }
  covered(x, y) { return this.list.some(R => ceilingOf(R, this.plate, x, y) !== null); }

  // Is a point of roof `self` at height h buried in another roof? kind 0: outer surface, 1: ceiling.
  #hidden(self, x, y, h, kind) {
    for (const R of this.list) {
      if (R === self || R === self.parent || R.parent === self || (kind === 1 && R.companion)) continue;
      const c = ceilingOf(R, this.plate, x, y);
      if (c !== null && h < c + (R.lift ?? 0) + (kind === 0 ? ROOF_T : 0) - 0.04) return true;
    }
    // a companion gable only exists where it rises above its own hip
    if (self.companion) { const c = ceilingOf(self.parent, this.plate, x, y); if (c !== null && h < c + (kind === 0 ? ROOF_T : 0) + 0.005) return true; }
    return false;
  }

  build() {
    const group = new THREE.Group();
    this.list.forEach((R, i) => group.add(this.#buildOne(R, i)));
    return group;
  }

  #buildOne(R, index) {
    const g = new THREE.Group();
    const H = (x, y) => (ceilingOf(R, this.plate, x, y) ?? this.plate) + (R.lift ?? 0);
    const top = [], under = [];
    for (const f of this.#faces(R)) {
      for (const piece of gridClip(f.pts)) {
        const P = piece.map(([x, y]) => [x, y, H(x, y)]);
        if (P.every(([x, y, h]) => this.#hidden(R, x, y, h + ROOF_T, 0))) continue;
        top.push({ P: P.map(([x, y, h]) => [x, y, h + ROOF_T]), dir: f.dir });
        if (!R.companion && !P.every(([x, y, h]) => this.#hidden(R, x, y, h, 1))) under.push({ P, dir: f.dir, flip: true });
      }
    }
    g.add(this.#mesh(top, this.#roofMaterial(mat('roof'), index, 0)));
    g.add(this.#mesh(under, this.#roofMaterial(mat('soffit'), index, 1)));
    if (!R.companion) {
      const fascia = [];
      for (const [a, b] of this.#eaves(R)) {
        const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / CELL));
        for (let k = 0; k < n; k++) {
          const p = [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n], q = [a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n];
          const hp = H(...p), hq = H(...q);
          if (this.#hidden(R, ...p, hp + ROOF_T, 0) && this.#hidden(R, ...q, hq + ROOF_T, 0)) continue;
          fascia.push([[p[0], p[1], hp - 0.02], [q[0], q[1], hq - 0.02], [q[0], q[1], hq + ROOF_T + 0.08], [p[0], p[1], hp + ROOF_T + 0.08]]);
        }
      }
      g.add(this.#quadMesh(fascia, this.#roofMaterial(mat('fascia'), index, 0)));
      for (const [a, b] of this.#ridges(R)) this.#cap(g, a, b, H, R, index);
    } else {
      this.#gablets(g, R, H);
      for (const [a, b] of this.#ridges(R)) this.#cap(g, a, b, H, R, index);
    }
    g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    return g;
  }

  // Ridge / hip cap, cut into short pieces so buried parts can be dropped.
  #cap(g, a, b, H, R, index) {
    const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 2));
    for (let k = 0; k < n; k++) {
      const p = [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n], q = [a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n];
      const hp = H(...p) + ROOF_T, hq = H(...q) + ROOF_T;
      if (this.#hidden(R, ...p, hp + 0.1, 0) || this.#hidden(R, ...q, hq + 0.1, 0)) continue;
      const len = Math.hypot(q[0] - p[0], q[1] - p[1], hq - hp);
      const cap = new THREE.Mesh(new THREE.BoxGeometry(len, 0.14, 0.55), mat('fascia'));
      cap.position.set((p[0] + q[0]) / 2, (hp + hq) / 2 + 0.04, (p[1] + q[1]) / 2);
      cap.rotation.order = 'YZX';
      cap.rotation.y = -Math.atan2(q[1] - p[1], q[0] - p[0]);
      cap.rotation.z = Math.atan2(hq - hp, Math.hypot(q[0] - p[0], q[1] - p[1]));
      g.add(cap);
    }
  }

  // Louvered triangular vents where a Dutch hip's ridge gable is cut off.
  #gablets(g, C, H) {
    const P = C.parent, alongX = C.t === TYPE.gableX;
    const ends = alongX ? [C.x0, C.x1] : [C.y0, C.y1];
    const mid = alongX ? (C.y0 + C.y1) / 2 : (C.x0 + C.x1) / 2;
    for (const e of ends) {
      const at = (u, v) => alongX ? [e, v] : [v, e];
      const apex = H(...at(e, mid)) + ROOF_T;
      const base = (ceilingOf(P, this.plate, ...at(e, mid)) ?? this.plate) + ROOF_T;   // hip end plane under the gablet
      // it is a gablet only if the end sits on the hip's sloped end
      const half = (apex - base) / C.pitch;
      if (half < 0.5) continue;
      // a gablet buried inside another roof (e.g. a wing's inner end) is not built
      if (this.#hidden(C, ...at(e, mid), apex - 0.05, 0) || this.#hidden(P, ...at(e, mid), base + 0.05, 0)) continue;
      const shape = new THREE.Shape([new THREE.Vector2(-half, 0), new THREE.Vector2(half, 0), new THREE.Vector2(0, apex - base)]);
      const tri = new THREE.Mesh(new THREE.ShapeGeometry(shape), mat('louverWhite'));
      const [px, py] = at(e, mid);
      tri.position.set(px, base, py);
      tri.rotation.y = alongX ? Math.PI / 2 : 0;
      tri.material = mat('louverWhite');
      g.add(tri);
      // thin trim around the vent
      for (const s of [-1, 1]) {
        const len = Math.hypot(half, apex - base);
        const t = new THREE.Mesh(new THREE.BoxGeometry(len, 0.18, 0.12), mat('fascia'));
        const cx = s * half / 2, cy = (apex - base) / 2;
        t.position.set(alongX ? px : px + cx, base + cy, alongX ? py - cx : py);
        t.rotation.order = 'YXZ';
        t.rotation.y = alongX ? Math.PI / 2 : 0;
        t.rotation.z = -s * Math.atan2(apex - base, half);
        g.add(t);
      }
    }
  }

  // Plane polygons of a roof, each with its up-slope direction.
  #faces(R) {
    const { x0, y0, x1, y1, o, rk, t } = R;
    if (t === TYPE.hip) {
      const X0 = x0 - o, X1 = x1 + o, Y0 = y0 - o, Y1 = y1 + o, W = X1 - X0, D = Y1 - Y0;
      if (W >= D) {
        const h = D / 2, yc = (Y0 + Y1) / 2, ra = X0 + h, rb = X1 - h;
        return [
          { pts: [[X0, Y0], [X1, Y0], [rb, yc], [ra, yc]], dir: [0, 1] },
          { pts: [[X1, Y1], [X0, Y1], [ra, yc], [rb, yc]], dir: [0, -1] },
          { pts: [[X0, Y1], [X0, Y0], [ra, yc]], dir: [1, 0] },
          { pts: [[X1, Y0], [X1, Y1], [rb, yc]], dir: [-1, 0] },
        ];
      }
      const h = W / 2, xc = (X0 + X1) / 2, ra = Y0 + h, rb = Y1 - h;
      return [
        { pts: [[X0, Y1], [X0, Y0], [xc, ra], [xc, rb]], dir: [1, 0] },
        { pts: [[X1, Y0], [X1, Y1], [xc, rb], [xc, ra]], dir: [-1, 0] },
        { pts: [[X0, Y0], [X1, Y0], [xc, ra]], dir: [0, 1] },
        { pts: [[X1, Y1], [X0, Y1], [xc, rb]], dir: [0, -1] },
      ];
    }
    if (t === TYPE.gableX) {
      const X0 = x0 - rk, X1 = x1 + rk, Y0 = y0 - o, Y1 = y1 + o, yc = (y0 + y1) / 2;
      return [{ pts: [[X0, Y0], [X1, Y0], [X1, yc], [X0, yc]], dir: [0, 1] }, { pts: [[X1, Y1], [X0, Y1], [X0, yc], [X1, yc]], dir: [0, -1] }];
    }
    if (t === TYPE.gableY) {
      const Y0 = y0 - rk, Y1 = y1 + rk, X0 = x0 - o, X1 = x1 + o, xc = (x0 + x1) / 2;
      return [{ pts: [[X0, Y1], [X0, Y0], [xc, Y0], [xc, Y1]], dir: [1, 0] }, { pts: [[X1, Y0], [X1, Y1], [xc, Y1], [xc, Y0]], dir: [-1, 0] }];
    }
    return [{ pts: [[x0 - rk, y1 + o], [x1 + rk, y1 + o], [x1 + rk, y0 - o], [x0 - rk, y0 - o]], dir: [0, -1] }];
  }

  // Outer edges of the roof outline (fascia and rake boards).
  #eaves(R) {
    const { x0, y0, x1, y1, o, rk, t } = R;
    const ex = t === TYPE.hip ? o : (t === TYPE.gableY ? o : rk), ey = t === TYPE.hip ? o : (t === TYPE.gableY ? rk : o);
    const X0 = x0 - ex, X1 = x1 + ex, Y0 = y0 - ey, Y1 = y1 + ey;
    const corners = [[X0, Y0], [X1, Y0], [X1, Y1], [X0, Y1]];
    const edges = [];
    for (let i = 0; i < 4; i++) {
      const a = corners[i], b = corners[(i + 1) % 4];
      // split rake edges at the ridge so each half is a straight board
      if (t === TYPE.gableX && a[0] === b[0]) { const yc = (y0 + y1) / 2; edges.push([a, [a[0], yc]], [[a[0], yc], b]); }
      else if (t === TYPE.gableY && a[1] === b[1]) { const xc = (x0 + x1) / 2; edges.push([a, [xc, a[1]]], [[xc, a[1]], b]); }
      else edges.push([a, b]);
    }
    return edges;
  }

  #ridges(R) {
    const { x0, y0, x1, y1, o, rk, t } = R;
    if (t === TYPE.gableX) { const yc = (y0 + y1) / 2; return [[[x0 - rk, yc], [x1 + rk, yc]]]; }
    if (t === TYPE.gableY) { const xc = (x0 + x1) / 2; return [[[xc, y0 - rk], [xc, y1 + rk]]]; }
    if (t === TYPE.hip) {
      const X0 = x0 - o, X1 = x1 + o, Y0 = y0 - o, Y1 = y1 + o, W = X1 - X0, D = Y1 - Y0;
      if (W >= D) { const h = D / 2, yc = (Y0 + Y1) / 2, ra = X0 + h, rb = X1 - h; return [[[ra, yc], [rb, yc]], [[X0, Y0], [ra, yc]], [[X0, Y1], [ra, yc]], [[X1, Y0], [rb, yc]], [[X1, Y1], [rb, yc]]]; }
      const h = W / 2, xc = (X0 + X1) / 2, ra = Y0 + h, rb = Y1 - h; return [[[xc, ra], [xc, rb]], [[X0, Y0], [xc, ra]], [[X1, Y0], [xc, ra]], [[X0, Y1], [xc, rb]], [[X1, Y1], [xc, rb]]];
    }
    return [];
  }

  // Triangulated faces with UVs in feet: u along the eave, v up the slope.
  #mesh(faces, material) {
    const pos = [], uv = [], idx = [];
    for (const { P, dir, flip } of faces) {
      const base = pos.length / 3;
      const ux = -dir[1], uy = dir[0];
      for (const [x, y, h] of P) {
        pos.push(x, h, y);
        const along = x * ux + y * uy, up = Math.hypot(...[x * dir[0] + y * dir[1]]) * Math.sign(x * dir[0] + y * dir[1] || 1);
        uv.push(along, up * 1.118 + h * 0);
      }
      for (let k = 1; k < P.length - 1; k++) flip ? idx.push(base, base + k + 1, base + k) : idx.push(base, base + k, base + k + 1);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setIndex(idx);
    geo.computeVertexNormals();
    return new THREE.Mesh(geo, material);
  }

  #quadMesh(quads, material) {
    const pos = [], uv = [], idx = [];
    for (const q of quads) {
      const b = pos.length / 3, len = Math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1]);
      q.forEach(([x, y, h], k) => { pos.push(x, h, y); uv.push(k === 1 || k === 2 ? len : 0, k >= 2 ? 1 : 0); });
      idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setIndex(idx);
    geo.computeVertexNormals();
    const m = material.clone(); m.side = THREE.DoubleSide;
    m.onBeforeCompile = material.onBeforeCompile; m.customProgramCacheKey = material.customProgramCacheKey;
    return new THREE.Mesh(geo, m);
  }

  // Clone `base` and add the per-pixel union test. kind 0: outer surface, 1: ceiling.
  #roofMaterial(base, self, kind) {
    const m = base.clone();
    const n = this.list.length;
    const rects = this.list.map(R => new THREE.Vector4(R.x0, R.y0, R.x1, R.y1));
    const params = this.list.map(R => new THREE.Vector4(R.t, (R.plate ?? this.plate) + (R.lift ?? 0), R.pitch, R.o));
    const me = this.list[self];
    const extra = this.list.map(R => new THREE.Vector4(R.rk, (R === me.parent || R.parent === me) ? 1 : 0, R.companion ? 1 : 0, 0));
    while (rects.length < 12) { rects.push(new THREE.Vector4()); params.push(new THREE.Vector4()); extra.push(new THREE.Vector4()); }
    m.onBeforeCompile = shader => {
      Object.assign(shader.uniforms, {
        uRect: { value: rects }, uPar: { value: params }, uExt: { value: extra },
        uCount: { value: n }, uSelf: { value: self }, uKind: { value: kind }, uT: { value: ROOF_T },
      });
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vRoofWorld;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvRoofWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', `#include <common>
varying vec3 vRoofWorld;
uniform vec4 uRect[12]; uniform vec4 uPar[12]; uniform vec4 uExt[12];
uniform int uCount; uniform int uSelf; uniform int uKind; uniform float uT;
float roofC(int j, vec2 p, out bool inside) {
  vec4 r = uRect[j]; vec4 a = uPar[j]; float o = a.w; float rk = uExt[j].x; float d;
  if (a.x < 0.5) { inside = p.x > r.x - o && p.x < r.z + o && p.y > r.y - o && p.y < r.w + o; d = min(min(p.x - r.x, r.z - p.x), min(p.y - r.y, r.w - p.y)); }
  else if (a.x < 1.5) { inside = p.x > r.x - rk && p.x < r.z + rk && p.y > r.y - o && p.y < r.w + o; d = min(p.y - r.y, r.w - p.y); }
  else if (a.x < 2.5) { inside = p.y > r.y - rk && p.y < r.w + rk && p.x > r.x - o && p.x < r.z + o; d = min(p.x - r.x, r.z - p.x); }
  else { inside = p.x > r.x - rk && p.x < r.z + rk && p.y > r.y - o && p.y < r.w + o; d = r.w - p.y; }
  return a.y + a.z * d;
}`)
        .replace('void main() {', `void main() {
  for (int j = 0; j < 12; j++) {
    if (j >= uCount) break;
    if (j == uSelf || uExt[j].y > 0.5 || (uKind == 1 && uExt[j].z > 0.5)) continue;
    bool inside; float c = roofC(j, vRoofWorld.xz, inside);
    if (inside && vRoofWorld.y < c + (uKind == 0 ? uT : 0.0) - 0.04) discard;
  }`);
    };
    m.customProgramCacheKey = () => `roof-${self}-${kind}-${base.uuid}`;
    return m;
  }
}
