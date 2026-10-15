// Walls: extruded outlines with real holes for openings, finished per side
// (lap siding outside, paint inside), topped to meet whatever roof is overhead.
import * as THREE from 'three';
import { mat, glow } from './materials.js';
import { inside } from './geom.js';


export function buildWalls(plan, roofs, colliders) {
  const group = new THREE.Group();
  const indoor = plan.rooms.filter(r => !r.outdoor && !r.label_only);
  for (const w of plan.walls) group.add(buildWall(w, plan, roofs, indoor, colliders));
  return group;
}

function buildWall(w, plan, roofs, indoor, colliders) {
  const [ax, ay] = w.a, [bx, by] = w.b;
  const L = Math.hypot(bx - ax, by - ay), ang = Math.atan2(by - ay, bx - ax);
  const T = w.t ?? 0.4, dx = Math.cos(ang), dy = Math.sin(ang), nx = -dy, ny = dx;
  const base = plan.grade ?? -0.6;
  const at = u => [ax + dx * u, ay + dy * u];
  const slat = w.finish === 'slat';
  const topAt = u => w.height ?? (roofs.ceilingAt(...at(Math.min(Math.max(u, 0), L))) - 0.02);
  const openings = [...(w.openings ?? [])].sort((p, q) => p.at - q.at);

  // Which side faces a room? Sampled along the wall, because one drawn wall can be
  // interior for part of its run (great room) and exterior for the rest (lanai).
  const indoorAt = (x, y) => indoor.some(r => inside([x, y], r.polygon));
  const classify = u => { const [mx, my] = at(u), o = T / 2 + 0.6; return [indoorAt(mx + nx * o, my + ny * o), indoorAt(mx - nx * o, my - ny * o)]; };
  const cuts = [-T / 2];
  let prev = classify(Math.min(0.25, L / 2));
  for (let u = 0.5; u < L - 0.25; u += 0.5) {
    const c = classify(u);
    if (c[0] === prev[0] && c[1] === prev[1]) continue;
    let cu = u - 0.25;
    const o = openings.find(o => cu > o.at - 0.2 && cu < o.at + o.width + 0.2);
    if (o) cu = cu - o.at < o.at + o.width - cu ? o.at - 0.2 : o.at + o.width + 0.2;
    if (cu > cuts[cuts.length - 1] + 0.3) cuts.push(cu);
    prev = c;
  }
  cuts.push(L + T / 2);

  const g = new THREE.Group();
  g.position.set(ax, 0, ay);
  g.rotation.y = -ang;
  const P = new Parts();
  const ends = [];

  for (let k = 0; k < cuts.length - 1; k++) {
    const u0 = cuts[k], u1 = cuts[k + 1];
    const [plusIn, minusIn] = classify(Math.min(Math.max((u0 + u1) / 2, 0.1), L - 0.1));
    if (k === 0) ends.push([u0, -1, ...classify(Math.min(0.3, L / 2))]);
    if (k === cuts.length - 2) ends.push([u1, 1, ...classify(Math.max(L - 0.3, L / 2))]);
    const shape = new THREE.Shape();
    shape.moveTo(u0, base); shape.lineTo(u1, base);
    const steps = Math.max(2, Math.ceil((u1 - u0) / 0.5));
    for (let j = steps; j >= 0; j--) { const u = u0 + (u1 - u0) * j / steps; shape.lineTo(u, topAt(u)); }
    shape.closePath();

    let cursor = u0;
    for (const o of openings.filter(o => o.at >= u0 - 0.01 && o.at + o.width <= u1 + 0.01)) {
      const x0 = o.at, x1 = o.at + o.width;
      const sill = o.sill ?? 0, head = Math.min(o.head ?? 8, topAt(o.at + o.width / 2) - 0.25);
      const yb = sill > 0 ? sill : 0;
      const hole = new THREE.Path();
      hole.moveTo(x0, yb); hole.lineTo(x0, head); hole.lineTo(x1, head); hole.lineTo(x1, yb); hole.closePath();
      shape.holes.push(hole);
      block(colliders, at, cursor, x0);
      dress(P, g, o, x0, x1, yb, head, T, plusIn, minusIn, colliders, at);
      cursor = x1;
    }
    block(colliders, at, cursor, u1);

    // 7 1/4" painted baseboard on the indoor faces, stopping at the casings of openings that reach the floor
    if (!slat) for (const sd of [1, -1]) {
      if (!((sd > 0 && plusIn) || (sd < 0 && minusIn))) continue;
      let from = Math.max(u0, 0);
      const stops = openings.filter(o => o.at >= u0 - 0.01 && o.at + o.width <= u1 + 0.01 && (o.sill ?? 0) <= 0.01)
        .map(o => [o.at - 0.3, o.at + o.width + 0.3]).concat([[Math.min(u1, L), Infinity]]);
      for (const [a0, a1] of stops) {
        if (a0 - from > 0.2) P.box(mat('trim'), a0 - from, 0.6, 0.05, (from + a0) / 2, 0.3, sd * (T / 2 + 0.025));
        from = Math.max(from, a1);
      }
    }

    const geo = new THREE.ExtrudeGeometry(shape, { depth: T, bevelEnabled: false, steps: 1 });
    geo.translate(0, 0, -T / 2);
    const outMat = slat ? mat('slats') : mat(w.outside ?? 'siding'), inMat = slat ? mat('slats') : mat(w.inside ?? plan.interiorWalls ?? 'batten');
    g.add(new THREE.Mesh(splitBySide(geo), [
      plusIn ? inMat : outMat,
      minusIn ? inMat : outMat,
      slat ? mat('slats') : (plusIn && minusIn ? mat('paint') : mat('trim')),
    ]));

    // exterior base: painted skirt between grade and floor
    if (!slat) for (const s of [1, -1]) {
      if ((s > 0 && plusIn) || (s < 0 && minusIn)) continue;
      const skirt = new THREE.Mesh(new THREE.BoxGeometry(u1 - u0, 0.53, 0.06), mat('trim'));
      skirt.position.set((u0 + u1) / 2, base + 0.28, s * (T / 2 + 0.03));
      g.add(skirt);
    }
  }
  // 5 1/2" white corner boards on the outdoor faces at both ends of the wall
  if (!slat) for (const [u, dir, pIn, mIn] of ends) for (const s of [1, -1]) {
    if ((s > 0 && pIn) || (s < 0 && mIn)) continue;
    const top = topAt(u) - 0.02;
    P.box(mat('trim'), 0.53, top - base, 0.07, u - dir * 0.23 + dir * 0.035, (base + top) / 2, s * (T / 2 + 0.035));
  }
  P.flush(g);
  g.traverse(o => { if (o.isMesh) { o.castShadow = !o.userData.noShadow; o.receiveShadow = true; } });
  return g;
}

// Rebuild the extrusion's groups as: 0 = +z cap, 1 = -z cap, 2 = everything else.
function splitBySide(geo) {
  const g = geo.index ? geo.toNonIndexed() : geo;
  const pos = g.attributes.position, nor = g.attributes.normal, uv = g.attributes.uv;
  const buckets = [[], [], []];
  for (let t = 0; t < pos.count; t += 3) {
    const nz = nor.getZ(t);
    buckets[nz > 0.9 ? 0 : nz < -0.9 ? 1 : 2].push(t);
  }
  const P = [], N = [], U = [], out = new THREE.BufferGeometry();
  let start = 0;
  buckets.forEach((tris, gi) => {
    for (const t of tris) for (let k = 0; k < 3; k++) {
      P.push(pos.getX(t + k), pos.getY(t + k), pos.getZ(t + k));
      N.push(nor.getX(t + k), nor.getY(t + k), nor.getZ(t + k));
      // caps: u along the wall, v up, in feet; sides keep a usable planar mapping
      if (gi < 2) U.push(pos.getX(t + k) * (gi === 0 ? 1 : -1), pos.getY(t + k));
      else U.push(pos.getX(t + k) + pos.getZ(t + k), pos.getY(t + k));
    }
    out.addGroup(start, tris.length * 3, gi);
    start += tris.length * 3;
  });
  out.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
  out.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2));
  return out;
}

function block(colliders, at, u0, u1) { if (u1 - u0 > 0.05) colliders.push({ a: at(u0), b: at(u1) }); }

// ---------------------------------------------------------------------------------- named finishes
// New finishes the Blender side matches by name (scripts/materials_bpy.py): until it has a recipe for
// one, the glTF colour / roughness / metalness below are used as they are.
const OWN = new Map();
function finish(name, color, roughness, metalness = 0, extra = {}) {
  if (!OWN.has(name)) OWN.set(name, new THREE.MeshStandardMaterial({ name, color, roughness, metalness, ...extra }));
  return OWN.get(name);
}
const M = {
  frame: () => mat('black'),                                             // dark bronze / black window and door frames
  glass: () => mat('glass'),
  trim: () => mat('trim'),                                               // white casings, sills, corner boards
  shutter: () => finish('shutterCedar', '#8a6040', 0.72),               // stained, lightly weathered cedar shutters
  carriage: () => mat('cedar'),                                          // carriage door stiles, rails and planks
  iron: () => finish('ironHardware', '#1c1c1d', 0.55, 0.6),             // strap hinges, pulls, shutter hinges and dogs
  sconce: () => finish('sconceBronze', '#262626', 0.4, 0.5),            // cylinder up/down wall lights
  lens: () => glow,                                                      // their frosted lenses (lit at night)
};

// Boxes, cylinders and panes of one wall, merged into one mesh per material when the wall is done.
class Parts {
  constructor() { this.by = new Map(); }
  add(m, geo) { if (!this.by.has(m)) this.by.set(m, []); this.by.get(m).push(geo); return geo; }
  box(m, w, h, d, x, y, z, rx = 0, rz = 0) {
    if (w <= 0.001 || h <= 0.001 || d <= 0.001) return null;
    const g = new THREE.BoxGeometry(w, h, d);
    if (rx) g.rotateX(rx);
    if (rz) g.rotateZ(rz);
    g.translate(x, y, z);
    return this.add(m, g);
  }
  cyl(m, r, h, x, y, z, axis = 'y', seg = 14) {
    const g = new THREE.CylinderGeometry(r, r, h, seg);
    if (axis === 'z') g.rotateX(Math.PI / 2); else if (axis === 'x') g.rotateZ(Math.PI / 2);
    g.translate(x, y, z);
    return this.add(m, g);
  }
  pane(xa, xb, ya, yb, z) {
    if (xb - xa < 0.03 || yb - ya < 0.03) return;
    const g = new THREE.PlaneGeometry(xb - xa, yb - ya);
    g.translate((xa + xb) / 2, (ya + yb) / 2, z);
    this.add(M.glass(), g);
  }
  flush(group) {
    for (const [m, geos] of this.by) {
      const mesh = new THREE.Mesh(mergeGeos(geos), m);
      if (m === M.glass()) { mesh.renderOrder = 2; mesh.castShadow = false; mesh.userData.noShadow = true; }
      group.add(mesh);
    }
    this.by.clear();
  }
}
function mergeGeos(list) {
  const P = [], N = [], U = [];
  for (let g of list) {
    if (g.index) g = g.toNonIndexed();
    P.push(...g.attributes.position.array); N.push(...g.attributes.normal.array);
    if (g.attributes.uv) U.push(...g.attributes.uv.array); else U.push(...new Array(g.attributes.position.count * 2).fill(0));
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
  out.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2));
  return out;
}

// ---------------------------------------------------------------------------------- building blocks
// Local frame of an opening: x along the wall, y up, z through the wall (s = +1/-1 picks a face).
// A rectangular frame of four members (face width f, depth d) around [xa, xb] x [ya, yb] at depth z.
function rectFrame(P, m, xa, xb, ya, yb, f, d, z, bottom = f) {
  P.box(m, xb - xa, f, d, (xa + xb) / 2, yb - f / 2, z);
  P.box(m, xb - xa, bottom, d, (xa + xb) / 2, ya + bottom / 2, z);
  P.box(m, f, yb - ya - f - bottom, d, xa + f / 2, (ya + bottom + yb - f) / 2, z);
  P.box(m, f, yb - ya - f - bottom, d, xb - f / 2, (ya + bottom + yb - f) / 2, z);
}
// Simulated divided lites: 1 1/2" bars on both faces of the glass, cols x rows.
function muntins(P, xa, xb, ya, yb, z, cols, rows, bar = 0.125) {
  for (const s of [1, -1]) {
    for (let i = 1; i < cols; i++) P.box(M.frame(), bar, yb - ya, 0.045, xa + (xb - xa) * i / cols, (ya + yb) / 2, z + s * 0.035);
    for (let j = 1; j < rows; j++) P.box(M.frame(), xb - xa, bar, 0.045, (xa + xb) / 2, ya + (yb - ya) * j / rows, z + s * 0.035);
  }
}
// A glazed sash: frame members, the glass, optional grid.
function sash(P, xa, xb, ya, yb, z, o = {}) {
  const f = o.f ?? 0.19, d = o.d ?? 0.15, bottom = o.bottom ?? f;
  rectFrame(P, M.frame(), xa, xb, ya, yb, f, d, z, bottom);
  P.pane(xa + f - 0.02, xb - f + 0.02, ya + bottom - 0.02, yb - f + 0.02, z);
  if (o.grid) muntins(P, xa + f, xb - f, ya + bottom, yb - f, z, o.grid[0], o.grid[1]);
}
// Flat exterior casing (3 1/2"), head with a drip cap, sill with horns and an apron below windows.
function casingOut(P, x0, x1, yb, head, z, s, o = {}) {
  const c = o.casing ?? 0.29, t = 0.08, w = x1 - x0, h = head - yb, cx = (x0 + x1) / 2;
  P.box(M.trim(), w + 2 * c, c, t, cx, head + c / 2, z + s * t / 2);
  P.box(M.trim(), w + 2 * c + 0.12, 0.06, t + 0.1, cx, head + c + 0.03, z + s * (t + 0.1) / 2);      // drip cap
  const sillH = o.sill ? 0.12 : 0, y0 = yb - (o.sill ? 0 : 0);
  P.box(M.trim(), c, h, t, x0 - c / 2, y0 + h / 2, z + s * t / 2);
  P.box(M.trim(), c, h, t, x1 + c / 2, y0 + h / 2, z + s * t / 2);
  if (o.sill) {
    P.box(M.trim(), w + 2 * c + 0.25, sillH, 0.42, cx, yb - sillH / 2, z + s * (0.21 - 0.12));      // sloped sill nose
    P.box(M.trim(), w + 2 * c, 0.29, t, cx, yb - sillH - 0.145, z + s * t / 2);                    // apron
  }
}
// Interior flat casing and window stool (3 1/2" casing, painted).
function casingIn(P, x0, x1, yb, head, z, s, isWindow) {
  const c = 0.29, t = 0.06, w = x1 - x0, h = head - yb, cx = (x0 + x1) / 2;
  P.box(M.trim(), w + 2 * c, c, t, cx, head + c / 2, z + s * t / 2);
  P.box(M.trim(), c, h, t, x0 - c / 2, yb + h / 2, z + s * t / 2);
  P.box(M.trim(), c, h, t, x1 + c / 2, yb + h / 2, z + s * t / 2);
  if (isWindow && yb > 0.5) {
    P.box(M.trim(), w + 2 * c + 0.15, 0.08, 0.3, cx, yb - 0.04, z + s * 0.1);
    P.box(M.trim(), w + 2 * c, 0.25, t, cx, yb - 0.08 - 0.125, z + s * t / 2);
  }
}
// Louvre blades between two stiles, fixed at `deg` (tipped down toward the outside, s = outward side).
function blades(P, m, xa, xb, ya, yb, z, s, o = {}) {
  const dep = o.dep ?? 0.17, th = o.th ?? 0.03, pitch = o.pitch ?? 0.155, ang = (o.deg ?? 40) * Math.PI / 180;
  const n = Math.max(1, Math.floor((yb - ya) / pitch)), gap = (yb - ya - n * pitch) / 2;
  for (let k = 0; k < n; k++) P.box(m, xb - xa + 0.02, th, dep, (xa + xb) / 2, ya + gap + (k + 0.5) * pitch, z, s * ang);
}
// One louvered panel (shutter leaf or fixed louvre): stiles, top / bottom rails, a mid rail on tall leaves.
function louverPanel(P, m, xa, xb, ya, yb, z, s, o = {}) {
  const st = o.stile ?? 0.17, d = o.depth ?? 0.125, top = o.top ?? 0.25, bot = o.bottom ?? 0.33;
  // one solid per member (a second top rail laid over the frame's head made coincident faces that
  // shadowed each other and rendered as a black slot along the head)
  P.box(m, xb - xa, top, d, (xa + xb) / 2, yb - top / 2, z);
  P.box(m, xb - xa, bot, d, (xa + xb) / 2, ya + bot / 2, z);
  for (const x of [xa + st / 2, xb - st / 2]) P.box(m, st, yb - ya - top - bot, d, x, (ya + bot + yb - top) / 2, z);
  const tall = yb - ya > 5.2, mid = ya + (yb - ya) * 0.42;
  if (tall) {
    P.box(m, xb - xa - 2 * st, 0.25, d, (xa + xb) / 2, mid, z);
    blades(P, m, xa + st, xb - st, ya + bot, mid - 0.125, z, s, o);
    blades(P, m, xa + st, xb - st, mid + 0.125, yb - top, z, s, o);
  } else blades(P, m, xa + st, xb - st, ya + bot, yb - top, z, s, o);
}

// ---------------------------------------------------------------------------------- openings
function dress(P, g, o, x0, x1, yb, head, T, plusIn, minusIn, colliders, at) {
  const w = x1 - x0, h = head - yb, cx = (x0 + x1) / 2, cy = (yb + head) / 2;
  const outSide = !plusIn ? 1 : !minusIn ? -1 : 0;   // which face gets exterior trim and shutters
  const inSide = plusIn ? 1 : minusIn ? -1 : 0;
  const s = outSide || 1;
  const faceOut = outSide * T / 2, faceIn = inSide * T / 2;
  // window / door frames sit toward the outside face, 3" face, 4 1/2" deep
  const zf = outSide ? outSide * (T / 2 - 0.2) : 0;
  const frame = (xa, xb, ya, yb2, f = 0.25, d = 0.36) => rectFrame(P, M.frame(), xa, xb, ya, yb2, f, d, zf, ya < 0.3 ? 0.08 : f);
  const outCasing = (sill) => { if (outSide) casingOut(P, x0, x1, yb, head, faceOut, outSide, { sill }); };
  const inCasing = (isWin) => { if (inSide) casingIn(P, x0, x1, yb, head, faceIn, inSide, isWin); };

  switch (o.type) {
    case 'window': {
      if (o.dh) {
        // double-hung, 1-over-1 (or gridded): the upper sash 1 1/2" outboard, a meeting rail at the middle
        frame(x0, x1, yb, head);
        const xa = x0 + 0.25, xb = x1 - 0.25, ya = yb + 0.25, yt = head - 0.25, mid = (ya + yt) / 2;
        sash(P, xa, xb, mid - 0.06, yt, zf + s * 0.07, { grid: o.grid, d: 0.13 });
        sash(P, xa, xb, ya, mid + 0.06, zf - s * 0.06, { grid: o.grid, d: 0.13, bottom: 0.27 });
        for (const k of [-1, 1]) P.box(M.frame(), 0.22, 0.05, 0.06, cx + k * w * 0.25, mid + 0.09, zf - s * 0.15);   // sash lifts
      } else {
        // casement units no wider than ~2.75 ft each, a transom bar on tall units
        const n = Math.max(1, Math.round(w / 2.75)), lw = w / n;
        for (let k = 0; k < n; k++) {
          const xa = x0 + k * lw, xb = xa + lw;
          frame(xa, xb, yb, head);
          const ia = xa + 0.25, ib = xb - 0.25, ya = yb + 0.25, yt = head - 0.25;
          if (h > 5.5) {
            const tb = head - h * 0.22;
            P.box(M.frame(), ib - ia, 0.2, 0.34, (ia + ib) / 2, tb, zf);
            sash(P, ia, ib, ya, tb - 0.1, zf + s * 0.05, { grid: o.grid ? [o.grid[0], Math.max(1, o.grid[1] - 1)] : null });
            sash(P, ia, ib, tb + 0.1, yt, zf + s * 0.05, { grid: o.grid ? [o.grid[0], 1] : null });
          } else sash(P, ia, ib, ya, yt, zf + s * 0.05, { grid: o.grid });
          if (outSide) P.box(M.iron(), 0.04, 0.35, 0.06, ib - 0.12, (ya + yt) / 2, zf - s * 0.13);   // crank / handle inside
        }
      }
      outCasing(true); inCasing(true);
      if (o.shutters && outSide) shutters(P, x0, x1, yb, head, faceOut, outSide);
      colliders.push({ a: at(x0), b: at(x1) });
      break;
    }
    case 'slider': {
      // multi-panel lift-and-slide: 2 1/2" stiles, 4" bottom rail, interlocks, panels on two tracks.
      // `open` (0..1): how far the operable panels are slid over the fixed ones.
      const n = o.panels ?? Math.max(2, Math.round(w / 3.2)), pw = w / n, rows = o.rows ?? 0, cols = o.cols ?? 1;
      const op = o.open ?? 0;
      P.box(M.frame(), w, 0.25, T * 0.8, cx, head - 0.125, zf * 0.5);              // head track
      P.box(M.frame(), w, 0.06, T * 0.8, cx, yb + 0.03, zf * 0.5);                 // flush sill track
      P.box(M.frame(), 0.2, h, T * 0.8, x0 + 0.1, cy, zf * 0.5);                   // jambs
      P.box(M.frame(), 0.2, h, T * 0.8, x1 - 0.1, cy, zf * 0.5);
      for (let k = 0; k < n; k++) {
        // fixed panels at the ends (outer track), operable panels toward the middle (inner track)
        const fixed = k === 0 || k === n - 1, track = fixed ? 1 : -1;
        let xa = x0 + 0.2 + k * (w - 0.4) / n, xb = xa + (w - 0.4) / n;
        if (!fixed && op) { const dir = k < n / 2 ? -1 : 1, d = op * (w - 0.4) / n; xa += dir * d; xb += dir * d; }
        const z = zf * 0.5 + s * track * 0.09;
        sash(P, xa - 0.03, xb + 0.03, yb + 0.06, head - 0.25, z, { f: 0.21, d: 0.14, bottom: 0.33, grid: rows ? [cols, rows] : null });
        if (!fixed) for (const q of [-1, 1]) P.box(M.iron(), 0.05, 0.9, 0.06, k < n / 2 ? xb - 0.12 : xa + 0.12, 3.4, z + q * 0.1);   // pulls
      }
      if (op) colliders.push({ a: at(x0), b: at(x0 + w * 0.25) }, { a: at(x1 - w * 0.25), b: at(x1) });
      else colliders.push({ a: at(x0), b: at(x1) });
      outCasing(false); inCasing(false);
      if (o.sconces && outSide) sconces(P, [x0 - 0.29 - 1.5, x1 + 0.29 + 1.5], 7.0, faceOut, outSide);
      break;
    }
    case 'pocket': {
      // stacking glass wall: `deployed` of `panels` panels drawn out across the opening, the rest stacked in
      // the pocket; a visible pocket jamb, head track and flush floor track; 3-row divided lites.
      const n = o.panels ?? Math.max(2, Math.round(w / 3)), pw = w / n, dep = o.deployed ?? 0, rows = o.rows ?? 0;
      P.box(M.frame(), w, 0.25, T * 0.9, cx, head - 0.125, 0);
      P.box(M.frame(), w, 0.04, T * 0.9, cx, yb + 0.02, 0);
      P.box(M.frame(), 0.25, h, T * 0.9, x0 + 0.125, cy, 0);                       // receiving jamb
      for (const k of [1, -1]) P.box(M.frame(), 0.12, h, 0.08, x1 - 0.06, cy, k * (T * 0.45 - 0.04));   // pocket jamb lips
      for (let k = 0; k < dep; k++) {
        const xa = x0 + 0.25 + k * pw - 0.02, xb = xa + pw + 0.04, z = ((k % 3) - 1) * 0.16;
        sash(P, xa, xb, yb + 0.04, head - 0.25, z, { f: 0.21, d: 0.14, bottom: 0.33, grid: rows ? [1, rows] : null });
      }
      if (dep) colliders.push({ a: at(x0), b: at(x0 + 0.25 + dep * pw) });
      break;
    }
    case 'pivot': {
      // oversized black steel-look glass pivot door standing ~40 deg open, fixed glass sidelights either side,
      // 3-row divided lites like the other glass walls
      const dw = Math.min(4.5, w * 0.45), da = cx - dw / 2, db = cx + dw / 2, rows = o.rows ?? 0;
      frame(x0, x1, yb, head);
      P.box(M.frame(), 0.25, h, 0.36, da - 0.125, cy, zf);
      P.box(M.frame(), 0.25, h, 0.36, db + 0.125, cy, zf);
      sash(P, x0 + 0.25, da - 0.25, yb + 0.08, head - 0.25, zf, { f: 0.08, d: 0.1, grid: rows ? [1, rows] : null });
      sash(P, db + 0.25, x1 - 0.25, yb + 0.08, head - 0.25, zf, { f: 0.08, d: 0.1, grid: rows ? [1, rows] : null });
      colliders.push({ a: at(x0), b: at(da) }, { a: at(db), b: at(x1) });
      const leaf = new THREE.Group(), L = new Parts(), pv = 0.9;      // pivot 11" in from the hinge-side edge
      sash(L, -pv, dw - pv, yb + 0.06, head - 0.06, 0, { f: 0.21, d: 0.2, bottom: 0.33, grid: rows ? [1, rows] : null });
      for (const q of [1, -1]) {
        L.cyl(M.iron(), 0.06, 4.2, dw - pv - 0.6, 4.1, q * 0.3, 'y', 10);                      // ladder pulls
        for (const y of [2.3, 5.9]) L.box(M.iron(), 0.05, 0.05, 0.2, dw - pv - 0.6, y, q * 0.16);
      }
      L.flush(leaf);
      leaf.position.set(da + pv, 0, zf);
      leaf.rotation.y = -0.7;
      g.add(leaf);
      outCasing(false); inCasing(false);
      break;
    }
    case 'door': {
      // white shaker door(s) swung open against the wall on the indoor side
      const leaves = o.double ? 2 : 1, lw = w / leaves;
      const side = plusIn ? 1 : -1;
      const [p0x, p0y] = at(0), [p1x, p1y] = at(1), nX = -(p1y - p0y), nY = p1x - p0x;
      for (let k = 0; k < leaves; k++) {
        const hinge = k === 0 ? x0 : x1, dir = k === 0 ? 1 : -1;
        const leaf = new THREE.Group(), L = new Parts();
        L.box(M.trim(), lw - 0.05, h - 0.05, 0.15, dir * lw / 2, cy, 0);
        for (const py of [yb + h * 0.28, yb + h * 0.7]) for (const q of [1, -1]) L.box(mat('#efeee9'), lw - 0.6, h * 0.36, 0.02, dir * lw / 2, py, q * 0.085);
        for (const q of [1, -1]) { L.box(M.frame(), 0.05, 0.05, 0.3, dir * (lw - 0.3), 3.3, q * 0.15); L.box(M.frame(), 0.36, 0.05, 0.05, dir * (lw - 0.42), 3.3, q * 0.29); }
        for (const y of [0.9, 3.6, 6.3]) L.box(M.frame(), 0.06, 0.35, 0.16, dir * 0.0, y, 0);  // hinges
        L.flush(leaf);
        leaf.position.set(hinge, 0, side * (T / 2 + 0.08));
        leaf.rotation.y = -dir * side * Math.PI / 2 * 0.97;
        g.add(leaf);
        const [hx, hy] = at(hinge);
        colliders.push({ a: [hx + nX * side * T / 2, hy + nY * side * T / 2], b: [hx + nX * side * (T / 2 + lw), hy + nY * side * (T / 2 + lw)] });
      }
      casingBoth(P, x0, x1, yb, head, T);
      break;
    }
    case 'gate': {
      const piv = new THREE.Group();
      const leaf = new THREE.Mesh(new THREE.BoxGeometry(w - 0.05, h - 0.1, 0.12), mat('slats'));
      leaf.position.set(w / 2, cy, 0); piv.add(leaf);
      piv.position.set(x0, 0, 0); g.add(piv);
      break;
    }
    case 'carriage': carriage(P, o, x0, x1, yb, head, T, outSide, colliders, at); break;
    case 'louvered': {
      // fixed louvered shutter assembly filling the opening (white on the pavilion fronts), set in 5" flat
      // trim, with a black-framed window behind it as on the real thing
      const m = o.white ? M.trim() : M.shutter(), z = outSide * (T / 2 - 0.1);
      louverPanel(P, m, x0, x1, yb, head, z, s, { stile: 0.21, depth: 0.15, top: 0.3, bottom: 0.4, deg: 45, dep: 0.21, pitch: 0.17 });
      rectFrame(P, M.frame(), x0, x1, yb, head, 0.2, 0.15, -outSide * 0.08);
      P.pane(x0 + 0.2, x1 - 0.2, yb + 0.2, head - 0.2, -outSide * 0.08);
      if (outSide) {
        const c = 0.42, t = 0.08;
        P.box(M.trim(), w + 2 * c, c, t, cx, head + c / 2, faceOut + outSide * t / 2);
        for (const xx of [x0 - c / 2, x1 + c / 2]) P.box(M.trim(), c, h, t, xx, cy, faceOut + outSide * t / 2);   // jambs stand on the sill
        P.box(M.trim(), w + 2 * c + 0.2, 0.12, 0.35, cx, yb - 0.06, faceOut + outSide * 0.12);
      }
      inCasing(true);
      colliders.push({ a: at(x0), b: at(x1) });
      break;
    }
    case 'cased': casingBoth(P, x0, x1, yb, head, T); break;
    default: break;
  }
}

function casingBoth(P, x0, x1, yb, head, T) {
  for (const s of [1, -1]) casingIn(P, x0, x1, yb, head, s * T / 2, s, false);
}

// Louvered cedar shutters standing open either side of a window: stiles and rails, blades 2" deep at
// ~1 7/8" pitch tipped 40 deg, a mid rail, two black strap hinges and a shutter dog each.
function shutters(P, x0, x1, yb, head, face, s) {
  const c = 0.29, sw = (x1 - x0) / 2 + 0.06, t = 0.125, z = face + s * (t / 2 + 0.03), m = M.shutter();
  for (const [xa, side] of [[x0 - c - 0.04 - sw, -1], [x1 + c + 0.04, 1]]) {
    const xb = xa + sw;
    louverPanel(P, m, xa, xb, yb, head, z, s, { depth: t });
    const hx = side < 0 ? xb : xa;                      // hinge edge, next to the casing
    for (const y of [yb + 0.75, head - 0.75]) {
      P.box(M.iron(), 0.75, 0.1, 0.02, hx - side * -0.3, y, z + s * (t / 2 + 0.01));
      P.cyl(M.iron(), 0.035, 0.12, hx + side * -0.02, y, z, 'y', 8);
    }
    const dx = side < 0 ? xa - 0.2 : xb + 0.2;         // shutter dog holding it open
    P.box(M.iron(), 0.06, 0.28, 0.05, dx, yb + 0.45, face + s * 0.06, 0, side * 0.6);
  }
}

// Cedar carriage door (front rendering): 6" stiles, 6"/8" rails, a top row of 4 lites split by 2" mullions,
// a lock rail, then two tiers of V-groove plank panels recessed 3/4" between 3 intermediate stiles and a rail;
// black strap hinges with bolt heads, two pull handles, white casing and black cylinder sconces either side.
function carriage(P, o, x0, x1, yb, head, T, outSide, colliders, at) {
  const w = x1 - x0, h = head - yb, cx = (x0 + x1) / 2, s = outSide || 1;
  const zc = outSide * (T / 2 - 0.32), d = 0.15, face = zc + s * d / 2, W = M.carriage();
  const gap = 0.04, xa = x0 + gap, xb = x1 - gap, ya = yb + 0.03, yt = head - gap;
  const st = 0.5, top = 0.5, bot = 0.67, lock = 0.5, lite = 1.35, cols = 4;
  const yl1 = yt - top, yl0 = yl1 - lite, ylock = yl0 - lock, ymid = ya + bot + (ylock - ya - bot) * 0.5;
  rectFrame(P, M.frame(), x0, x1, yb, head, 0.07, 0.05, zc - s * 0.1);     // dark stop seen through the 1/2" gap
  // perimeter stiles and rails
  P.box(W, st, yt - ya, d, xa + st / 2, (ya + yt) / 2, zc);
  P.box(W, st, yt - ya, d, xb - st / 2, (ya + yt) / 2, zc);
  P.box(W, xb - xa - 2 * st, top, d, cx, yt - top / 2, zc);
  P.box(W, xb - xa - 2 * st, bot, d, cx, ya + bot / 2, zc);
  P.box(W, xb - xa - 2 * st, lock, d, cx, ylock + lock / 2, zc);
  P.box(W, xb - xa - 2 * st, 0.42, d, cx, ymid, zc);                        // intermediate rail
  const ia = xa + st, ib = xb - st, mull = 0.17, mstile = 0.42;
  // lites: 4 across, 2" mullions, glass set back, a thin black glazing bead
  const lw = (ib - ia - (cols - 1) * mull) / cols;
  for (let k = 0; k < cols; k++) {
    const la = ia + k * (lw + mull), lb = la + lw;
    if (k) P.box(W, mull, lite, d, la - mull / 2, (yl0 + yl1) / 2, zc);
    P.pane(la, lb, yl0, yl1, zc - s * 0.02);
    rectFrame(P, M.frame(), la, lb, yl0, yl1, 0.03, 0.04, zc + s * 0.01);
  }
  // plank panels: two tiers, 4 columns (3 intermediate stiles), boards 5 1/2" with V-grooves, 3/4" recessed
  const pw = (ib - ia - (cols - 1) * mstile) / cols;
  for (const [pa, pb] of [[ya + bot, ymid - 0.21], [ymid + 0.21, ylock]]) {
    for (let k = 0; k < cols; k++) {
      const qa = ia + k * (pw + mstile), qb = qa + pw;
      if (k) P.box(W, mstile, pb - pa, d, qa - mstile / 2, (pa + pb) / 2, zc);
      const nb = Math.max(1, Math.round(pw / 0.458)), bw = pw / nb;
      for (let j = 0; j < nb; j++) P.box(W, bw - 0.025, pb - pa, d * 0.5, qa + (j + 0.5) * bw, (pa + pb) / 2, zc - s * 0.0625);
      P.box(M.frame(), pw, pb - pa, 0.02, (qa + qb) / 2, (pa + pb) / 2, zc - s * 0.11);    // dark behind the V-grooves
    }
  }
  // strap hinges (3 per side) with bolt heads, two pull handles
  for (const side of [-1, 1]) {
    const ex = side < 0 ? xa : xb;
    for (const y of [ya + 1.1, (ya + yt) / 2 - 0.4, yl0 - 0.25]) {
      P.box(M.iron(), 1.6, 0.16, 0.025, ex - side * 0.8, y, face + s * 0.012);
      P.box(M.iron(), 0.28, 0.28, 0.025, ex - side * 0.12, y, face + s * 0.012);
      for (const bx of [0.25, 0.75, 1.3]) P.cyl(M.iron(), 0.028, 0.03, ex - side * bx, y, face + s * 0.035, 'z', 8);
    }
  }
  for (const side of [-1, 1]) {
    const hx = cx + side * 0.45;
    P.cyl(M.iron(), 0.04, 1.05, hx, 3.8, face + s * 0.2, 'y', 10);
    for (const y of [3.35, 4.25]) P.box(M.iron(), 0.06, 0.06, 0.2, hx, y, face + s * 0.1);
  }
  // white casing with a drip cap
  if (outSide) {
    const c = 0.29, t = 0.08, fo = outSide * T / 2;
    P.box(M.trim(), w + 2 * c, c, t, cx, head + c / 2, fo + s * t / 2);
    P.box(M.trim(), w + 2 * c + 0.12, 0.06, t + 0.1, cx, head + c + 0.03, fo + s * (t + 0.1) / 2);
    for (const xx of [x0 - c / 2, x1 + c / 2]) P.box(M.trim(), c, h, t, xx, (yb + head) / 2, fo + s * t / 2);
    if (o.sconces) sconces(P, [x0 - c - 1.1, x1 + c + 1.1], 7.2, fo, outSide);
  }
  colliders.push({ a: at(x0), b: at(x1) });
}

// Black cylinder up/down sconces (14" x 5"), wall plate and arm, frosted lenses top and bottom.
function sconces(P, xs, y, face, s) {
  for (const x of xs) {
    const z = face + s * 0.33;
    P.box(M.sconce(), 0.33, 0.5, 0.04, x, y, face + s * 0.02);
    P.box(M.sconce(), 0.12, 0.12, 0.22, x, y, face + s * 0.14);
    P.cyl(M.sconce(), 0.21, 1.17, x, y, z, 'y', 20);
    for (const q of [-1, 1]) P.cyl(M.lens(), 0.18, 0.02, x, y + q * 0.585, z, 'y', 20);
  }
}
