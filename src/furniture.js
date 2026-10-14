// Furniture built from primitives. Every item is centred on (x, y) in plan feet,
// w runs along its local x, d along its local depth, rot is degrees clockwise on the plan.
// Local -d/2 is the item's "back" (against the wall for sofas, beds, counters).
import * as THREE from '../vendor/three.module.js';
import { solid } from './materials.js';

const box = (g, w, h, d, x, y, z, color, rough = 0.8) => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), solid(color, rough));
  m.position.set(x, y, z);
  g.add(m);
  return m;
};

const BUILDERS = {
  sofa(g, { w, d, color }) {
    box(g, w, 1.4, d, 0, 0.7, 0, color);
    box(g, w, 1.4, 0.7, 0, 1.75, -d / 2 + 0.35, color);
    box(g, 0.6, 0.8, d, -w / 2 + 0.3, 1.6, 0, color);
    box(g, 0.6, 0.8, d, w / 2 - 0.3, 1.6, 0, color);
  },
  chair(g, { w = 2.5, d = 2.5, color }) {
    box(g, w, 1.4, d, 0, 0.7, 0, color);
    box(g, w, 1.2, 0.5, 0, 1.9, -d / 2 + 0.25, color);
  },
  rug(g, { w, d, color }) { box(g, w, 0.03, d, 0, 0.015, 0, color, 1); },
  table(g, { w, d, h = 2.5, color }) {
    box(g, w, 0.15, d, 0, h - 0.075, 0, color, 0.5);
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) box(g, 0.2, h - 0.15, 0.2, sx * (w / 2 - 0.3), (h - 0.15) / 2, sz * (d / 2 - 0.3), color);
  },
  dining(g, item) {
    BUILDERS.table(g, { ...item, h: 2.5 });
    const n = item.chairs ?? 6, side = Math.ceil(n / 2);
    for (let i = 0; i < n; i++) {
      const s = i < side ? -1 : 1, k = i % side;
      const c = new THREE.Group();
      BUILDERS.chair(c, { w: 1.5, d: 1.5, color: item.chairColor ?? item.color });
      c.scale.y = 0.75;
      c.position.set(-item.w / 2 + (k + 0.5) * item.w / side, 0, s * (item.d / 2 + 0.6));
      c.rotation.y = s < 0 ? 0 : Math.PI;
      g.add(c);
    }
  },
  island(g, { w, d, color, top = '#f2f0eb' }) {
    box(g, w - 0.2, 2.9, d - 0.4, 0, 1.45, 0, color, 0.6);
    box(g, w, 0.15, d, 0, 3.0, 0, top, 0.25);
  },
  counter(g, item) {
    BUILDERS.island(g, item);
    const uppers = item.uppers ?? true;
    if (uppers) box(g, item.w, 2.5, 1.1, 0, 6.25, -item.d / 2 + 0.55, item.upperColor ?? item.color, 0.6);
  },
  vanity(g, { w, d, color, top = '#f2f0eb' }) {
    box(g, w, 2.6, d, 0, 1.3, 0, color, 0.6);
    box(g, w + 0.1, 0.12, d + 0.1, 0, 2.66, 0, top, 0.25);
    box(g, w * 0.9, 3, 0.05, 0, 5, -d / 2 + 0.03, '#cfd8dc', 0.05);
  },
  bed(g, { w, d, color, frame = '#7a5a3c' }) {
    box(g, w, 1, d, 0, 0.5, 0, frame, 0.7);
    box(g, w - 0.2, 0.9, d - 0.3, 0, 1.45, 0.1, color, 0.95);
    box(g, w + 0.2, 3.5, 0.3, 0, 1.75, -d / 2 + 0.15, frame, 0.7);
    for (const s of [-1, 1]) box(g, w / 2 - 0.4, 0.5, 1.2, s * w / 4, 2.15, -d / 2 + 1.0, '#ffffff', 1);
  },
  lounger(g, { w, d, color }) {
    box(g, w, 1.1, d, 0, 0.55, 0, color);
    const back = box(g, w, 0.3, 2, 0, 1.6, -d / 2 + 0.9, color);
    back.rotation.x = -0.7;
  },
  cabinet(g, { w, d, h = 3, color }) { box(g, w, h, d, 0, h / 2, 0, color, 0.6); },
  tv(g, { w = 5, color = '#111' }) { box(g, w, w * 0.5625, 0.15, 0, 5, 0, color, 0.2); },
  plant(g, { w = 2, h = 5, color = '#4d6b3c' }) {
    box(g, w * 0.6, 1.2, w * 0.6, 0, 0.6, 0, '#8b7d6b');
    const leaves = new THREE.Mesh(new THREE.SphereGeometry(w / 2, 12, 10), solid(color, 1));
    leaves.position.y = h - w / 2; leaves.scale.y = (h - 1.2) / w;
    g.add(leaves);
  },
  pool(g, { w, d, color = '#3fa7c4' }) {
    box(g, w, 0.05, d, 0, 0.02, 0, color, 0.1);
  },
};

export function buildFurniture(item) {
  const g = new THREE.Group();
  (BUILDERS[item.type] ?? BUILDERS.cabinet)(g, { ...item, color: item.color ?? '#cccccc' });
  g.position.set(item.x, item.elevation ?? 0, item.y);
  g.rotation.y = -(item.rot ?? 0) * Math.PI / 180;
  return { mesh: g, blocks: !['rug', 'tv', 'pool'].includes(item.type) && item.blocks !== false };
}
