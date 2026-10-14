// Assembles a plan into a house: slabs and floors, flat ceilings, walls, roofs, posts, furniture.
import * as THREE from 'three';
import { mat } from './materials.js';
import { Roofs } from './roof.js';
import { buildWalls } from './walls.js';
import { buildFurniture } from './furniture.js';
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
    floor.receiveShadow = true;
    group.add(floor);
    if (typeof room.ceiling === 'number') {
      const c = new THREE.Mesh(new THREE.ShapeGeometry(shape), mat('paint'));
      c.rotation.x = Math.PI / 2; c.scale.y = -1; c.position.y = room.ceiling;
      c.material = mat('paint').clone(); c.material.side = THREE.DoubleSide;
      group.add(c);
      // a recessed can light per ~60 sq ft
      const xs = room.polygon.map(p => p[0]), ys = room.polygon.map(p => p[1]);
      const area = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
      const n = Math.max(1, Math.round(area / 60));
      for (let k = 0; k < n; k++) {
        const x = Math.min(...xs) + (Math.max(...xs) - Math.min(...xs)) * (k + 0.5) / n, y = (Math.min(...ys) + Math.max(...ys)) / 2;
        const can = new THREE.Mesh(new THREE.CircleGeometry(0.25, 20), mat('#f2efe9'));
        can.rotation.x = Math.PI / 2; can.position.set(x, room.ceiling - 0.01, y); group.add(can);
      }
    }
  }

  group.add(buildWalls(plan, roofs, colliders));
  group.add(roofs.build());

  // Lanai and entry: wood posts and a wood header beam on the open edges (back rendering).
  for (const [x, y] of plan.posts ?? []) {
    const top = roofs.ceilingAt(x, y) - 0.1;
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.8, top - grade, 0.8), mat('woodBeam'));
    post.position.set(x, (top + grade) / 2, y);
    group.add(post);
    colliders.push(...square(x, y, 0.4));
  }
  for (const b of plan.beams ?? []) {
    const [ax, ay] = b.a, [bx, by] = b.b, len = Math.hypot(bx - ax, by - ay);
    const top = roofs.ceilingAt((ax + bx) / 2, (ay + by) / 2);
    const beam = new THREE.Mesh(new THREE.BoxGeometry(len + 0.8, 1.1, 0.75), mat('woodBeam'));
    beam.position.set((ax + bx) / 2, top - 0.55, (ay + by) / 2);
    beam.rotation.y = -Math.atan2(by - ay, bx - ax);
    group.add(beam);
  }

  for (const item of plan.furniture ?? []) {
    const { mesh, blocks } = buildFurniture(item, { ceilingAt });
    group.add(mesh);
    if (blocks) colliders.push(...footprint(item));
  }

  group.traverse(o => { if (o.isMesh) { o.castShadow = !o.userData.noShadow && !o.material.transparent; o.receiveShadow = true; } });
  scene.add(group);
  return { group, colliders, roofs, ceilingAt };
}

function square(x, y, r) { return footprint({ x, y, w: 2 * r, d: 2 * r }); }

export function footprint({ x, y, w, d, rot = 0 }) {
  const r = rot * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
  const pts = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]].map(([u, v]) => [x + u * c - v * s, y + u * s + v * c]);
  return pts.map((p, i) => ({ a: p, b: pts[(i + 1) % 4] }));
}
