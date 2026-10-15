// Walls: extruded outlines with real holes for openings, finished per side
// (lap siding outside, paint inside), topped to meet whatever roof is overhead.
import * as THREE from 'three';
import { mat } from './materials.js';
import { inside } from './geom.js';

const FRAME = 0.17;   // black window frame face width, ft

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

  for (let k = 0; k < cuts.length - 1; k++) {
    const u0 = cuts[k], u1 = cuts[k + 1];
    const [plusIn, minusIn] = classify(Math.min(Math.max((u0 + u1) / 2, 0.1), L - 0.1));
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
      dress(g, o, x0, x1, yb, head, T, plusIn, minusIn, colliders, at);
      cursor = x1;
    }
    block(colliders, at, cursor, u1);

    const geo = new THREE.ExtrudeGeometry(shape, { depth: T, bevelEnabled: false, steps: 1 });
    geo.translate(0, 0, -T / 2);
    const outMat = slat ? mat('slats') : mat('siding'), inMat = slat ? mat('slats') : mat(w.inside ?? plan.interiorWalls ?? 'batten');
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
  g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
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

const box = (g, w, h, d, x, y, z, m) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); g.add(b); return b; };

// Frames, glass, doors and trim for one opening. Local frame: x along wall, y up, z through wall.
function frameRect(t, xa, xb, ya, yb, depth, z = 0) {
  const black = mat('black');
  box(t, xb - xa, FRAME, depth, (xa + xb) / 2, yb - FRAME / 2, z, black);
  box(t, xb - xa, FRAME, depth, (xa + xb) / 2, ya + FRAME / 2, z, black);
  box(t, FRAME, yb - ya, depth, xa + FRAME / 2, (ya + yb) / 2, z, black);
  box(t, FRAME, yb - ya, depth, xb - FRAME / 2, (ya + yb) / 2, z, black);
}
function pane(t, xa, xb, ya, yb, z = 0) {
  const p = new THREE.Mesh(new THREE.PlaneGeometry(Math.max(0.05, xb - xa - 2 * FRAME), Math.max(0.05, yb - ya - 2 * FRAME)), mat('glass'));
  p.position.set((xa + xb) / 2, (ya + yb) / 2, z); p.renderOrder = 2; p.castShadow = false; p.userData.noShadow = true; t.add(p);
}

function dress(g, o, x0, x1, yb, head, T, plusIn, minusIn, colliders, at) {
  const w = x1 - x0, h = head - yb, cx = (x0 + x1) / 2, cy = (yb + head) / 2;
  const outSide = !plusIn ? 1 : !minusIn ? -1 : 0;   // which face gets exterior trim and shutters
  const black = mat('black'), trim = mat('trim');
  const casing = () => {
    if (!outSide) return;
    const z = outSide * (T / 2 + 0.04), c = 0.33;
    box(g, w + 2 * c, c, 0.08, cx, head + c / 2, z, trim);
    box(g, c, h, 0.08, x0 - c / 2, cy, z, trim);
    box(g, c, h, 0.08, x1 + c / 2, cy, z, trim);
    if (o.type === 'window') box(g, w + 2 * c + 0.2, 0.12, 0.35, cx, yb - 0.06, outSide * (T / 2 + 0.12), trim);
  };

  switch (o.type) {
    case 'window': {
      // black casement units no wider than ~2.75 ft each, transom bar on tall units
      const n = Math.max(1, Math.round(w / 2.75)), lw = w / n;
      for (let k = 0; k < n; k++) {
        const xa = x0 + k * lw, xb = xa + lw;
        frameRect(g, xa, xb, yb, head, 0.22);
        if (h > 5.5) { const tb = head - h * 0.22; box(g, lw, FRAME * 0.8, 0.2, (xa + xb) / 2, tb, 0, black); pane(g, xa, xb, yb, tb); pane(g, xa, xb, tb, head); }
        else pane(g, xa, xb, yb, head);
      }
      casing();
      if (o.shutters && outSide) shutters(g, x0, x1, yb, head, outSide * (T / 2 + 0.1));
      colliders.push({ a: at(x0), b: at(x1) });
      break;
    }
    case 'slider': {
      // black multi-panel slider; the moving panels are stacked over the fixed half, so half is open
      const n = Math.max(1, Math.round(w / 8)), pw = (w / 2) / n;
      for (let k = 0; k < n; k++) {
        const fa = cx + k * pw, fb = fa + pw;
        frameRect(g, fa, fb, yb, head, 0.12, -0.1); pane(g, fa, fb, yb, head, -0.1);
        frameRect(g, fa + 0.15, fb + 0.15 > x1 ? x1 : fb, yb, head, 0.12, 0.1); pane(g, fa + 0.15, Math.min(fb, x1), yb, head, 0.1);
      }
      colliders.push({ a: at(cx), b: at(x1) });
      casing();
      break;
    }
    case 'pocket': {
      // stacking glass wall pushed into its pocket: only the head track and sill read
      box(g, w, FRAME, T * 0.9, cx, head - FRAME / 2, 0, black);
      box(g, w, 0.04, T * 0.9, cx, yb + 0.02, 0, black);
      break;
    }
    case 'pivot': {
      // oversized glass pivot door standing open, fixed glass sidelights either side
      const dw = Math.min(4.5, w * 0.45), da = cx - dw / 2, db = cx + dw / 2;
      frameRect(g, x0, da, yb, head, 0.2); pane(g, x0, da, yb, head);
      frameRect(g, db, x1, yb, head, 0.2); pane(g, db, x1, yb, head);
      colliders.push({ a: at(x0), b: at(da) }, { a: at(db), b: at(x1) });
      const leaf = new THREE.Group();
      frameRect(leaf, -dw / 2, dw / 2, yb, head - 0.02, 0.18);
      pane(leaf, -dw / 2, dw / 2, yb, head - 0.02);
      for (const s of [1, -1]) box(leaf, 0.07, 4, 0.07, dw / 2 - 0.55, 4, s * 0.22, black);
      leaf.position.set(cx, 0, 0);
      leaf.rotation.y = -1.25;
      g.add(leaf);
      casing();
      break;
    }
    case 'door': {
      // white shaker door(s) swung open against the wall on the indoor side
      const leaves = o.double ? 2 : 1, lw = w / leaves;
      const side = plusIn ? 1 : -1;
      const [p0x, p0y] = at(0), [p1x, p1y] = at(1), nX = -(p1y - p0y), nY = p1x - p0x;
      for (let k = 0; k < leaves; k++) {
        const hinge = k === 0 ? x0 : x1, dir = k === 0 ? 1 : -1;
        const leaf = new THREE.Group();
        box(leaf, lw - 0.05, h - 0.05, 0.15, dir * lw / 2, cy, 0, trim);
        for (const py of [yb + h * 0.28, yb + h * 0.7]) for (const s of [1, -1]) box(leaf, lw - 0.6, h * 0.36, 0.02, dir * lw / 2, py, s * 0.085, mat('#efeee9'));
        for (const s of [1, -1]) box(leaf, 0.05, 0.05, 0.3, dir * (lw - 0.3), 3.3, s * 0.15, black);
        leaf.position.set(hinge, 0, side * (T / 2 + 0.08));
        leaf.rotation.y = -dir * side * Math.PI / 2 * 0.97;
        g.add(leaf);
        const [hx, hy] = at(hinge);
        colliders.push({ a: [hx + nX * side * T / 2, hy + nY * side * T / 2], b: [hx + nX * side * (T / 2 + lw), hy + nY * side * (T / 2 + lw)] });
      }
      casingInside(g, o, x0, x1, yb, head, T, trim);
      break;
    }
    case 'gate': {
      const piv = new THREE.Group();
      const leaf = new THREE.Mesh(new THREE.BoxGeometry(w - 0.05, h - 0.1, 0.12), mat('slats'));
      leaf.position.set(w / 2, cy, 0); piv.add(leaf);
      piv.position.set(x0, 0, 0); g.add(piv);
      break;
    }
    case 'carriage': {
      // wood carriage door: vertical boards below, black-framed glass lites above
      const split = yb + h * 0.62;
      const wood = new THREE.Mesh(new THREE.BoxGeometry(w, split - yb, 0.25), mat('cedar'));
      wood.position.set(cx, (yb + split) / 2, 0); g.add(wood);
      for (let k = 1; k < Math.round(w / 0.6); k++) box(g, 0.04, split - yb - 0.1, 0.3, x0 + k * w / Math.round(w / 0.6), (yb + split) / 2, 0, mat('#6b4a2e'));
      box(g, w, 0.35, 0.3, cx, split, 0, mat('cedar'));
      const n = 4, lw = w / n;
      for (let k = 0; k < n; k++) { frameRect(g, x0 + k * lw, x0 + (k + 1) * lw, split + 0.17, head, 0.2); pane(g, x0 + k * lw, x0 + (k + 1) * lw, split + 0.17, head); }
      box(g, w, 0.3, 0.3, cx, head - 0.15, 0, mat('cedar'));
      casing();
      if (o.sconces && outSide) for (const sx of [x0 - 1.1, x1 + 1.1]) {
        // black cylinder wall sconces either side of the door (front rendering)
        const z = outSide * (T / 2 + 0.25);
        const c = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 1.2, 16), mat('black')); c.position.set(sx, 7.0, z); g.add(c);
        box(g, 0.3, 0.3, 0.3, sx, 7.0, z - outSide * 0.15, mat('black'));
      }
      colliders.push({ a: at(x0), b: at(x1) });
      break;
    }
    case 'louvered': {
      // fixed wood louvered shutter filling the opening
      const pnl = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.2), mat(o.white ? 'louverWhite' : 'louver'));
      pnl.position.set(cx, cy, 0); g.add(pnl);
      const fr = mat(o.white ? 'trim' : 'teak');
      for (const s of [x0 + 0.1, x1 - 0.1]) box(g, 0.2, h, 0.24, s, cy, 0, fr);
      box(g, 0.08, h, 0.22, cx, cy, 0, fr);
      casing();
      colliders.push({ a: at(x0), b: at(x1) });
      break;
    }
    case 'cased': casingInside(g, o, x0, x1, yb, head, T, trim); break;
    default: break;
  }
}

function casingInside(g, o, x0, x1, yb, head, T, trim) {
  const w = x1 - x0, c = 0.29;
  for (const s of [1, -1]) {
    const z = s * (T / 2 + 0.03);
    box(g, w + 2 * c, c, 0.06, (x0 + x1) / 2, head + c / 2, z, trim);
    box(g, c, head - yb, 0.06, x0 - c / 2, (yb + head) / 2, z, trim);
    box(g, c, head - yb, 0.06, x1 + c / 2, (yb + head) / 2, z, trim);
  }
}

// Louvered wood shutters standing open either side of a window.
function shutters(g, x0, x1, yb, head, z) {
  const w = (x1 - x0) / 2, h = head - yb, m = mat('louver');
  for (const [x, s] of [[x0 - 0.33 - w / 2 - 0.05, -1], [x1 + 0.33 + w / 2 + 0.05, 1]]) {
    const sh = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.1), m);
    sh.position.set(x, yb + h / 2, z + Math.sign(z) * 0.05);
    g.add(sh);
    box(g, w, 0.18, 0.12, x, yb + 0.09, z + Math.sign(z) * 0.06, m);
    box(g, w, 0.18, 0.12, x, head - 0.09, z + Math.sign(z) * 0.06, m);
  }
}
