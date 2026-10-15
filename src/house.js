// Assembles a plan into a house: slabs and floors, flat ceilings, walls, roofs, posts, furniture.
import * as THREE from 'three';
import { mat } from './materials.js';
import { Roofs } from './roof.js';
import { buildWalls } from './walls.js';
import { buildFurniture } from './furniture.js';
import { buildDetails } from './details.js';
import { inside } from './geom.js';

export function buildHouse(plan, scene) {
  const roofs = new Roofs(plan);
  const colliders = [];
  const group = new THREE.Group();
  const grade = plan.grade ?? -0.6;
  const rooms = plan.rooms.filter(r => !r.label_only);

  // Flat-ceiling rooms win over the vault for anything hung from the ceiling.
  const ceilingAt = (x, y) => {
    const r = rooms.find(r => typeof r.ceiling === 'number' && inside([x, y], r.polygon));
    return r ? r.ceiling : roofs.ceilingAt(x, y);
  };

  for (const room of rooms) {
    const shape = new THREE.Shape(room.polygon.map(([x, y]) => new THREE.Vector2(x, -y)));
    const top = room.floorLevel ?? 0;
    const slab = new THREE.ExtrudeGeometry(shape, { depth: top - grade, bevelEnabled: false });
    slab.rotateX(-Math.PI / 2);
    slab.translate(0, grade, 0);
    const floor = new THREE.Mesh(slab, [mat(room.floor ?? 'oak'), mat(room.outdoor ? 'coral' : 'trim')]);
    floor.receiveShadow = true; floor.userData.floor = true;   // model view (src/inspect.js) display classes
    group.add(floor);
    if (typeof room.ceiling === 'number') {
      const c = new THREE.Mesh(new THREE.ShapeGeometry(shape), mat('paint'));
      c.rotation.x = Math.PI / 2; c.scale.y = -1; c.position.y = room.ceiling;
      c.material = mat('paint').clone(); c.material.side = THREE.DoubleSide; c.userData.ceiling = true;
      group.add(c);
      // a recessed can light per ~60 sq ft
      const xs = room.polygon.map(p => p[0]), ys = room.polygon.map(p => p[1]);
      const area = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
      const n = Math.max(1, Math.round(area / 60));
      for (let k = 0; k < n; k++) {
        const x = Math.min(...xs) + (Math.max(...xs) - Math.min(...xs)) * (k + 0.5) / n, y = (Math.min(...ys) + Math.max(...ys)) / 2;
        const can = new THREE.Mesh(new THREE.CircleGeometry(0.25, 20), mat('#f2efe9'));
        can.rotation.x = Math.PI / 2; can.position.set(x, room.ceiling - 0.01, y); can.userData.ceiling = true; group.add(can);
      }
    }
  }

  const wallsG = buildWalls(plan, roofs, colliders), roofG = roofs.build();
  wallsG.userData.shell = roofG.userData.shell = true;
  group.add(wallsG, roofG);

  // Lanai and entry: rough-sawn cedar posts and header beams on the open edges (back rendering): 10x10 posts on
  // black steel stand-off bases, a 10x14 header whose ends run 12" past the posts, black iron knife plates with
  // round bolt washers at every post-to-beam joint. posts: [x, y, size?]; beams: { a, b, w?, h?, ext? } (ft).
  const timber = new Parts();
  const roomAt = (x, y) => plan.rooms.find(r => !r.label_only && !r.outdoor && inside([x, y], r.polygon));
  const beamOver = (x, y) => (plan.beams ?? []).find(b => {
    const [ax, ay] = b.a, [bx, by] = b.b, L = Math.hypot(bx - ax, by - ay), t = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (L * L);
    return t > -0.05 && t < 1.05 && Math.hypot(ax + (bx - ax) * t - x, ay + (by - ay) * t - y) < 0.3;
  });
  for (const [x, y, size = 0.833] of plan.posts ?? []) {
    const b = beamOver(x, y), bh = b ? (b.h ?? 1.167) : 0;
    const top = (b?.top ?? roofs.ceilingAt(x, y) - 0.1) - bh, foot = (plan.rooms.find(r => inside([x, y], r.polygon))?.floorLevel ?? 0);
    const base = foot + 0.125;                                           // 1 1/2" steel stand-off
    timber.box('woodBeam', size, top - base, size, x, (top + base) / 2, y);
    timber.box('iron', size + 0.08, 0.04, size + 0.08, x, foot + 0.02, y);              // base plate
    timber.box('iron', size * 0.5, 0.1, size * 0.5, x, foot + 0.08, y);                 // stand-off
    for (const [ux, uy] of [[1, 0], [0, 1]]) timber.box('iron', ux ? 0.02 : size * 0.55, 0.42, uy ? 0.02 : size * 0.55, x, foot + 0.25, y);  // base knife plates
    colliders.push(...square(x, y, size / 2));
  }
  for (const b of plan.beams ?? []) {
    const [ax, ay] = b.a, [bx, by] = b.b, len = Math.hypot(bx - ax, by - ay), ux = (bx - ax) / len, uy = (by - ay) / len;
    const bw = b.w ?? 0.833, bh = b.h ?? 1.167, ext = b.ext ?? 1.0;
    // ends run past the posts only into open air (not into a room's wall)
    const e0 = roomAt(ax - ux * (ext + 0.3), ay - uy * (ext + 0.3)) ? bw / 2 : ext, e1 = roomAt(bx + ux * (ext + 0.3), by + uy * (ext + 0.3)) ? bw / 2 : ext;
    const ceil = Math.min(roofs.ceilingAt(ax, ay), roofs.ceilingAt(bx, by), roofs.ceilingAt((ax + bx) / 2, (ay + by) / 2));
    // `top`: a dropped header (p5 lanai: the cedar beam hangs below the eave line, where a level eye sees it under the
    // gutter); a painted frieze board closes the gap up to the soffit, flush with the beam's outer face
    const top = b.top ?? ceil - 0.1;
    const mid = (e1 - e0) / 2, cx = (ax + bx) / 2 + ux * mid, cy = (ay + by) / 2 + uy * mid, L = len + e0 + e1;
    const rot = -Math.atan2(by - ay, bx - ax);
    timber.box(b.material ?? 'woodBeam', L, bh, bw, cx, top - bh / 2, cy, rot);
    if (b.frieze && ceil - top > 0.1) {
      const fs = b.frieze === true ? 1 : b.frieze, fz = 0.08, fo = bw / 2 - fz / 2 - 0.03;      // fs: which side is outside (+1: left of a->b)
      timber.box('trim', len, ceil - top + 0.02, fz, (ax + bx) / 2 - uy * fs * fo, (ceil + top) / 2, (ay + by) / 2 + ux * fs * fo, rot);
    }
    if (b.plates === false) continue;
    // bolted iron plates on both faces at each post, four 4" round washers with hex nuts
    for (const [px, py] of [[ax, ay], [bx, by]]) for (const sd of [1, -1]) {
      const nx = -uy * sd, ny = ux * sd, off = bw / 2 + 0.012;
      timber.box('iron', 0.62, bh + 0.75, 0.025, px + nx * off, top - (bh + 0.75) / 2, py + ny * off, rot);
      for (const [du, dv] of [[-0.17, -bh * 0.5], [0.17, -bh * 0.5], [-0.17, -bh - 0.4], [0.17, -bh - 0.4]]) {
        const qx = px + ux * du + nx * (off + 0.02), qy = py + uy * du + ny * (off + 0.02);
        timber.cyl('iron', 0.165, 0.025, qx, top + dv, qy, nx, ny);
        timber.cyl('iron', 0.06, 0.06, qx + nx * 0.03, top + dv, qy + ny * 0.03, nx, ny, 6);
      }
    }
  }
  const timberG = timber.mesh();
  timberG.userData.shell = true;
  timberG.traverse(o => { o.userData.shell = true; });
  group.add(timberG);

  for (const item of plan.furniture ?? []) {
    const { mesh, blocks } = buildFurniture(item, { ceilingAt });
    group.add(mesh);
    if (blocks) colliders.push(...footprint(item));
  }

  group.add(buildDetails(plan, { ceilingAt, grade, plan }));

  group.traverse(o => { if (o.isMesh) { o.castShadow = !o.userData.noShadow && !o.material.transparent; o.receiveShadow = true; } });
  scene.add(group);
  return { group, colliders, roofs, ceilingAt };
}

// Merged boxes and discs per material (posts, beams, their iron).
const IRON = () => (IRON.m ??= new THREE.MeshStandardMaterial({ name: 'ironHardware', color: '#1c1c1d', roughness: 0.55, metalness: 0.6 }));
class Parts {
  constructor() { this.by = new Map(); }
  add(name, g) { if (!this.by.has(name)) this.by.set(name, []); this.by.get(name).push(g); }
  box(name, w, h, d, x, y, z, rotY = 0) { const g = new THREE.BoxGeometry(w, h, d); if (rotY) g.rotateY(rotY); g.translate(x, y, z); this.add(name, g); }
  cyl(name, r, h, x, y, z, nx, nz, seg = 16) {
    const g = new THREE.CylinderGeometry(r, r, h, seg);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(nx, 0, nz).normalize()));
    g.translate(x, y, z); this.add(name, g);
  }
  mesh() {
    const grp = new THREE.Group();
    for (const [name, list] of this.by) {
      const P = [], N = [], U = [];
      for (let g of list) { g = g.index ? g.toNonIndexed() : g; P.push(...g.attributes.position.array); N.push(...g.attributes.normal.array); U.push(...g.attributes.uv.array); }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
      geo.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
      geo.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2));
      grp.add(new THREE.Mesh(geo, name === 'iron' ? IRON() : mat(name)));
    }
    return grp;
  }
}

function square(x, y, r) { return footprint({ x, y, w: 2 * r, d: 2 * r }); }

export function footprint({ x, y, w, d, rot = 0 }) {
  const r = rot * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
  const pts = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]].map(([u, v]) => [x + u * c - v * s, y + u * s + v * c]);
  return pts.map((p, i) => ({ a: p, b: pts[(i + 1) % 4] }));
}
