// Turns a plan JSON (units: feet, plan x -> world x, plan y -> world z) into a three.js scene.
import * as THREE from '../vendor/three.module.js';
import { materialFor, solid } from './materials.js';
import { buildFurniture } from './furniture.js';

const GLASS = new THREE.MeshPhysicalMaterial({ color: 0xcfe3ea, transparent: true, opacity: 0.18, roughness: 0.05, metalness: 0, side: THREE.DoubleSide });
const FRAME = solid('#2b2b2b', 0.5);

export function buildHouse(plan, scene) {
  const H = plan.wallHeight ?? 10;
  const T = plan.wallThickness ?? 0.5;
  const colliders = []; // 2D segments {a:[x,z], b:[x,z]} the walker cannot cross
  const group = new THREE.Group();

  for (const room of plan.rooms) group.add(buildRoom(room, H));

  for (const wall of plan.walls) {
    const wallColor = wall.color ?? adjacentRoomColor(plan, wall) ?? '#efe9df';
    group.add(buildWall(wall, H, T, wallColor, colliders));
  }

  for (const item of plan.furniture ?? []) {
    const { mesh, blocks } = buildFurniture(item);
    group.add(mesh);
    if (blocks) colliders.push(...boxSegments(item));
  }

  group.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  scene.add(group);
  return { colliders, bounds: planBounds(plan) };
}

function buildRoom(room, H) {
  const shape = new THREE.Shape(room.polygon.map(([x, y]) => new THREE.Vector2(x, -y)));
  const g = new THREE.Group();
  const floor = new THREE.Mesh(new THREE.ShapeGeometry(shape), materialFor(room.floor ?? 'oak'));
  floor.rotation.x = -Math.PI / 2;
  setPlanarUV(floor.geometry);
  g.add(floor);
  if (!room.outdoor) {
    const ceil = new THREE.Mesh(new THREE.ShapeGeometry(shape), solid(room.ceiling ?? '#f7f5f0', 0.95));
    ceil.rotation.x = Math.PI / 2;
    ceil.position.y = room.ceilingHeight ?? H;
    ceil.scale.y = -1; // undo the mirror from flipping the shape to face down
    g.add(ceil);
  }
  return g;
}

// Every opening splits the wall into: solid piers, a header above, and (for windows) a sill wall below.
function buildWall(wall, H, T, color, colliders) {
  const [ax, ay] = wall.a, [bx, by] = wall.b;
  const len = Math.hypot(bx - ax, by - ay);
  const angle = Math.atan2(by - ay, bx - ax);
  const height = wall.height ?? H;
  const mat = solid(color, 0.9);
  const g = new THREE.Group();
  g.position.set(ax, 0, ay);
  g.rotation.y = -angle;

  const piece = (x0, x1, y0, y1, m = mat) => {
    if (x1 - x0 < 0.01 || y1 - y0 < 0.01) return;
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(x1 - x0, y1 - y0, T), m);
    mesh.position.set((x0 + x1) / 2, (y0 + y1) / 2, 0);
    g.add(mesh);
  };
  const block = (x0, x1) => {
    const p = t => [ax + Math.cos(angle) * t, ay + Math.sin(angle) * t];
    colliders.push({ a: p(x0), b: p(x1) });
  };

  const openings = [...(wall.openings ?? [])].sort((p, q) => p.at - q.at);
  let cursor = -T / 2; // overlap corners by half a thickness so joints close
  for (const o of openings) {
    const x0 = o.at, x1 = o.at + o.width;
    piece(cursor, x0, 0, height); block(cursor, x0);
    const top = Math.min(o.height + (o.sill ?? 0), height);
    piece(x0, x1, top, height);
    if (o.type === 'window') {
      piece(x0, x1, 0, o.sill ?? 3); block(x0, x1);
      addGlass(g, x0, x1, o.sill ?? 3, top, T);
    } else if (o.type === 'slider') {
      addGlass(g, x0, x1, 0, top, T, true); // shown open: half the panels stacked
    } else if (o.type === 'door') {
      addDoor(g, x0, x1, top, T);
      // The open leaf sticks out perpendicular to the wall; make it solid too.
      const hx = ax + Math.cos(angle) * (x0 + 0.1), hy = ay + Math.sin(angle) * (x0 + 0.1);
      const w = x1 - x0, px = -Math.sin(angle), py = Math.cos(angle);
      colliders.push({ a: [hx + px * T / 2, hy + py * T / 2], b: [hx + px * (T / 2 + w), hy + py * (T / 2 + w)] });
    }
    cursor = x1;
  }
  piece(cursor, len + T / 2, 0, height); block(cursor, len + T / 2);
  return g;
}

function addGlass(g, x0, x1, y0, y1, T, open = false) {
  const w = x1 - x0;
  const panes = open ? Math.max(2, Math.round(w / 4)) : 1;
  const pw = w / panes;
  // An open slider stacks its panels into one pocket at the start of the opening.
  for (let i = 0; i < panes; i++) {
    const px = open ? x0 + pw / 2 + (i % 2) * 0.15 : x0 + pw * (i + 0.5);
    if (open && i > 0) continue;
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(pw - 0.15, y1 - y0 - 0.15), GLASS);
    glass.position.set(px, (y0 + y1) / 2, 0);
    glass.castShadow = false;
    g.add(glass);
  }
  const f = 0.12;
  for (const [x, y, w2, h2] of [[(x0 + x1) / 2, y1 - f / 2, w, f], [(x0 + x1) / 2, y0 + f / 2, w, f], [x0 + f / 2, (y0 + y1) / 2, f, y1 - y0], [x1 - f / 2, (y0 + y1) / 2, f, y1 - y0]]) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w2, h2, T * 0.4), FRAME);
    m.position.set(x, y, 0);
    g.add(m);
  }
}

function addDoor(g, x0, x1, top, T) {
  // Drawn swung open 90 degrees against the wall so it never blocks the doorway.
  const w = x1 - x0;
  const leaf = new THREE.Mesh(new THREE.BoxGeometry(0.15, top - 0.05, w), solid('#f4f2ec', 0.6));
  leaf.position.set(x0 + 0.1, top / 2, T / 2 + w / 2);
  g.add(leaf);
}

function boxSegments({ x, y, w, d, rot = 0 }) {
  const r = rot * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
  const pts = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]].map(([u, v]) => [x + u * c - v * s, y + u * s + v * c]);
  return pts.map((p, i) => ({ a: p, b: pts[(i + 1) % 4] }));
}

function setPlanarUV(geo) {
  const pos = geo.attributes.position, uv = geo.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, pos.getX(i), pos.getY(i));
}

function adjacentRoomColor(plan, wall) {
  const mid = [(wall.a[0] + wall.b[0]) / 2, (wall.a[1] + wall.b[1]) / 2];
  const nx = -(wall.b[1] - wall.a[1]), ny = wall.b[0] - wall.a[0], n = Math.hypot(nx, ny) || 1;
  for (const side of [1, -1]) {
    const p = [mid[0] + side * nx / n, mid[1] + side * ny / n];
    const room = plan.rooms.find(r => !r.outdoor && inside(p, r.polygon));
    if (room?.wall) return room.wall;
  }
  return null;
}

export function inside([x, y], poly) {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

function planBounds(plan) {
  const xs = [], ys = [];
  for (const r of plan.rooms) for (const [x, y] of r.polygon) { xs.push(x); ys.push(y); }
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}
